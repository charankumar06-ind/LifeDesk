# LifeDesk — MCP-Ready Productivity Assistant

A local-first productivity prototype built for the wHACKiest 2026 ideathon.
It combines a calendar, task manager, conflict-aware daily planner and an
approval-gated workflow engine behind a deterministic command interpreter.

**This build is Demo Mode — Local Data.** It does not claim to use an LLM, and
it is not connected to any MCP server or external OAuth provider yet.

- Frontend: React 18 + TypeScript + Vite + Tailwind CSS 4 + Lucide icons
- Backend: Python + FastAPI + SQLite (standard library `sqlite3`)
- No API keys, no external services, no OAuth.

---

## Quick start (Windows 11)

Two terminals from the project root.

### 1. Backend (port 8000)

```powershell
cd backend
python -m venv .venv            # first time only
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The SQLite database `backend/lifedesk.db` is created and seeded on first start
with meaningful demo data (events, tasks, reminders, workflows and activity).

API docs: <http://127.0.0.1:8000/docs>

### 2. Frontend (port 5173)

```powershell
cd frontend
npm install                    # first time only
npm run dev
```

Open <http://127.0.0.1:5173>. The Vite dev server proxies `/api` to the backend.

Optional single-port mode: run `npm run build`, restart the backend, then open
<http://127.0.0.1:8000> — FastAPI serves the built SPA.

### Tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
```

14 tests cover task/event CRUD, validation, the full demo acceptance flow,
rejection, duplicate-execution protection, planner de-duplication, read-only
commands, reminders, settings and activity logging. Tests use an isolated
temporary database.

---

## Demo script (acceptance test)

1. Open the **Command Center**.
2. Run:
   `Plan my day. I have two pending assignments and need a two-hour Python study session.`
3. LifeDesk interprets the intent deterministically, reads local tasks and
   calendar events, and shows the workflow steps, rationale, conflict findings
   and a proposed timeline. **No data has been written yet.**
4. Review the actions. Approve all (or individually), then click
   **Execute approved**.
5. Open **Calendar** — the approved focus blocks and the two-hour Python study
   session are now real events.
6. Open **Activity** — successful `create_event` operations from
   `local-calendar`, each labelled *Local simulation*, plus the workflow
   execution record.
7. Try executing again: the backend returns `409` and blocks duplicate
   execution.

Restart the backend and the data is still there.

---

## Architecture

```
frontend/src
  pages/            Dashboard · CommandCenter · Calendar · Tasks · Planner
                    Approvals · Activity · Settings
  components/       Layout, WorkflowView, UI primitives, Toast, Settings
  lib/              typed API client, formatting, hooks, types

backend/app
  main.py           FastAPI app, CORS, lifespan (init + seed)
  db.py             schema + SQLite connections
  domain.py         provider-agnostic Pydantic models
  providers/
    base.py         CalendarProvider / TaskProvider / ReminderProvider ABCs
    local_*.py      SQLite implementations (Demo Mode)
    registry.py     the single composition root that selects providers
    mcp_adapter.py  MCP boundary — interfaces + documented tool mapping
  services/
    intent.py       deterministic command parsing
    ai.py           AIProvider abstraction (deterministic default)
    planner.py      conflict-aware scheduling algorithm (pure functions)
    workflows.py    command -> plan -> proposed actions (writes nothing)
    execution.py    approval decisions + guarded execution + activity
    activity.py     execution log
    settings.py     validated preferences
  routers/          thin HTTP layer over services/providers
```

### Key invariants

- **Providers are interchangeable.** The workflow engine and API only depend on
  the abstract interfaces in `providers/base.py`. Swapping providers is a change
  in `providers/registry.py`, not in the UI or planner.
- **Planning is read-only.** `services/workflows.py` persists proposals only.
  Writes happen exclusively in `services/execution.py` after approval.
- **Duplicate protection.** Actions carry a unique idempotency key; execution
  claims each action with `UPDATE ... WHERE status = 'approved'`, and a workflow
  whose status is no longer `pending_approval` cannot execute again.
- **Truthful AI labelling.** The interpreter is rule-based. Every workflow
  stores `ai_mode = deterministic`, `llm_used = false`, and the UI displays
  "Deterministic interpreter · no LLM".

### API surface

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/dashboard` | Today's events, tasks, reminders, stats, activity |
| POST | `/api/commands` | Interpret + plan a natural-language command |
| GET | `/api/workflows` · `/api/workflows/{id}` | Workflow history |
| GET | `/api/approvals` | Pending + archived workflows |
| POST | `/api/approvals/{id}/decision` | Approve/reject all actions |
| POST | `/api/approvals/{id}/actions/{actionId}/decision` | Decide one action |
| POST | `/api/approvals/{id}/execute` | Execute approved actions (once) |
| GET/POST | `/api/events`, PATCH/DELETE `/api/events/{id}` | Calendar CRUD |
| GET/POST | `/api/tasks`, PATCH/DELETE `/api/tasks/{id}` | Task CRUD |
| GET | `/api/planner/day?date=` | Conflict-aware day plan |
| POST | `/api/planner/propose` | Send a plan to approvals |
| GET | `/api/activity` · `/api/activity/summary` | Execution history |
| GET | `/api/settings`, PUT `/api/settings` | Preferences |
| GET | `/api/system` | Provider, AI and integration status |

---

## What gets replaced / extended during the 24-hour hackathon

Nothing in the frontend or workflow engine needs a redesign. The replacement
points are deliberately isolated:

| Component | Current prototype | Hackathon work |
| --- | --- | --- |
| `providers/mcp_adapter.py` | Interfaces + documented mapping; `build_mcp_services()` raises `ProviderNotConfigured` | Implement MCP client with the official Python SDK; map MCP tools to `domain.py` models |
| `providers/registry.py` | `build_local_services()` | Add `build_mcp_services()` wiring; select via `LIFEDESK_PROVIDER_MODE=mcp` |
| Calendar/Task providers | SQLite `Local*Provider` classes | New `McpCalendarProvider` / `McpTaskProvider`; local providers remain the offline fallback |
| `services/ai.py` | `DeterministicAIProvider` | Implement `LLMProvider.interpret()` behind the same `AIProvider` interface; set `LIFEDESK_AI_PROVIDER=llm`; keep deterministic fallback |
| Reminders | Local SQLite provider + dashboard list | Optional notifications MCP tool; add a dedicated reminder screen if needed |
| Activity `simulated` flag | Always `true` for local providers | Derive from provider kind (`local` vs `mcp`); the flag already flows through the DB, API and UI |
| Settings → Integrations | Static status from `/api/system` | Live connection health from MCP clients and OAuth providers |
| Auth/multi-user | Single local workspace | Add user scoping to `user_id` columns and provider credentials; out of scope for the ideathon prototype |
| External calendar sync | Local calendar only | Google/Outlook OAuth adapter implementing `CalendarProvider` |

Deliberately **not** implemented now: real MCP servers, OAuth flows, hosted
LLM calls, accounts, and third-party sync. The prototype is honest about this
in the UI, the `/api/system` payload, and this document.

---

## Known limitations

- Times are stored and displayed in machine-local time; there is no timezone
  model yet.
- The planner is a greedy allocator with buffers, not an optimiser; it does not
  move existing events to resolve overlaps (it flags them instead).
- The calendar week view expands events beyond the 07:00–22:00 grid window to
  the grid edges; events outside that window are only accessible from the
  dashboard/API.
- No authentication — intended for a single local user on a trusted machine.
