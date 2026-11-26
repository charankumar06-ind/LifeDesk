"""Local-mode email provider.

There is no local SMTP transport in this prototype: local mode stores calendar,
task and reminder data in SQLite, but email must leave the machine. Reporting a
simulated send as delivered would be dishonest, so execution fails with an
actionable message instead.
"""

from __future__ import annotations

from ..domain import EmailMessage
from .base import MailProvider, ProviderError, ProviderInfo


class LocalMailProvider(MailProvider):
    info = ProviderInfo(
        key="local-mail",
        label="Local Mail (not sending)",
        kind="local",
        transport="none",
        status="not_configured",
        note=(
            "Local mode does not deliver email. Switch LIFEDESK_PROVIDER_MODE to mcp "
            "and configure SMTP on the MCP server to send mail."
        ),
    )

    def send_email(self, message: EmailMessage) -> dict:
        raise ProviderError(
            "Local mode cannot send email. Set LIFEDESK_PROVIDER_MODE=mcp, configure "
            "LIFEDESK_SMTP_USER and LIFEDESK_SMTP_PASSWORD for the MCP server, then retry."
        )
