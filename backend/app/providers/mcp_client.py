"""Synchronous bridge to the official Python MCP SDK.

FastAPI routes in this project are synchronous, while the MCP client API is
async. A single daemon event loop owns every MCP session; calls are submitted to
it with `asyncio.run_coroutine_threadsafe`.

Each call opens its own MCP session. That is slower than holding a session open,
but it makes failures isolated and lets the backend recover when a server is
restarted without restarting FastAPI.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from urllib.parse import urlsplit, urlunsplit
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, AsyncIterator, Mapping

from .base import ProviderError


@dataclass(frozen=True)
class McpSettings:
    transport: str
    command: str = ""
    args: tuple[str, ...] = ()
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    timeout: float = 15.0
    label: str = "MCP server"

    def endpoint_label(self) -> str:
        if self.transport == "http":
            if not self.url:
                return "streamable HTTP endpoint"
            # Never echo query strings or userinfo: they commonly carry tokens.
            parts = urlsplit(self.url)
            host = parts.hostname or ""
            if parts.port:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme, host, parts.path, "", ""))
        return self.label


_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=loop.run_forever,
                name="lifedesk-mcp",
                daemon=True,
            )
            thread.start()
            _loop = loop
        return _loop


class McpClient:
    """Small, typed wrapper around `mcp.ClientSession`."""

    def __init__(self, settings: McpSettings):
        self.settings = settings

    def probe(self) -> list[str]:
        """Initialize a session and return the tool names the server exposes."""
        try:
            return self._run(self._list_tools())
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Could not connect to the MCP server: {exc}") from exc

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a tool and return its JSON payload."""
        try:
            return self._run(self._call_tool(name, arguments or {}))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"MCP tool '{name}' failed: {exc}") from exc

    def _run(self, coroutine):
        loop = _get_loop()
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=self.settings.timeout + 10)
        except FutureTimeoutError as exc:
            future.cancel()
            raise ProviderError(
                f"The MCP server did not answer within {self.settings.timeout:g} seconds."
            ) from exc

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[Any]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ProviderError(
                "The 'mcp' package is not installed. Run pip install -r requirements.txt."
            ) from exc

        timeout = timedelta(seconds=max(1.0, self.settings.timeout))
        if self.settings.transport == "stdio":
            if not self.settings.command:
                raise ProviderError("No MCP stdio command is configured.")
            env = {**os.environ, **dict(self.settings.env)}
            if self.settings.cwd:
                env.setdefault("PYTHONPATH", self.settings.cwd)
            params = StdioServerParameters(
                command=self.settings.command,
                args=list(self.settings.args),
                env=env,
                cwd=self.settings.cwd,
            )
            async with stdio_client(params, errlog=sys.stderr) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                    await session.initialize()
                    yield session
            return

        if self.settings.transport == "http":
            if not self.settings.url:
                raise ProviderError("No MCP HTTP URL is configured.")
            try:
                from mcp.client.streamable_http import streamablehttp_client
            except ImportError as exc:  # pragma: no cover - dependency is declared
                raise ProviderError("The streamable HTTP MCP transport is unavailable.") from exc
            async with streamablehttp_client(
                self.settings.url,
                headers=dict(self.settings.headers) or None,
                timeout=max(1.0, self.settings.timeout),
            ) as (read, write, _get_session_id):
                async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                    await session.initialize()
                    yield session
            return

        raise ProviderError(
            f"Unknown MCP transport '{self.settings.transport}'. Use 'stdio' or 'http'."
        )

    async def _list_tools(self) -> list[str]:
        async with self._session() as session:
            async with asyncio.timeout(max(1.0, self.settings.timeout)):
                result = await session.list_tools()
        return [tool.name for tool in result.tools]

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with self._session() as session:
            async with asyncio.timeout(max(1.0, self.settings.timeout)):
                result = await session.call_tool(name, arguments)

        if getattr(result, "isError", False):
            message = _text_content(result) or f"MCP tool '{name}' returned an error."
            raise ProviderError(message)

        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict) and structured:
            # FastMCP may wrap a non-object return in {"result": ...}.
            if set(structured) == {"result"} and isinstance(structured["result"], (dict, list)):
                return structured["result"] if isinstance(structured["result"], dict) else {"result": structured["result"]}
            return structured

        raw = _text_content(result)
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise ProviderError(f"MCP tool '{name}' returned non-JSON output.") from exc
        if not isinstance(payload, dict):
            return {"result": payload}
        return payload


def _text_content(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()
