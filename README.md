# LifeDesk — MCP-Ready Productivity Assistant

A local-first productivity prototype built for the wHACKiest 2026 ideathon.
It combines a calendar, task manager, conflict-aware daily planner and an
approval-gated workflow engine behind a deterministic command interpreter.

**By default this build is Demo Mode — Local Data.** An optional MCP provider
mode connects to a bundled reference MCP server (or a compatible external
bridge). It still does not use an LLM and never handles OAuth itself.

- Frontend: React 18 + TypeScript + Vite + Tailwind CSS 4 + Lucide icons
- Backend: Python + FastAPI + SQLite (standard library `sqlite3`)
- Providers: local SQLite (default) or MCP over stdio/streamable HTTP
- No API keys needed for the demo or the bundled reference server
- Email is sent for real in MCP mode once SMTP credentials are configured

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

**First visit:** LifeDesk is locked by default. Create the single owner password
and profile name (defaults to **Ari Mensha**) on the setup screen, then sign in.
No workspace data is served until the session cookie is valid. See
[Login and safety](#login-and-safety).

Optional single-port mode: run `npm run build`, restart the backend, then open
<http://127.0.0.1:8000> — FastAPI serves the built SPA.

### Tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
```

The backend suite (54 tests) covers authentication (mandatory gate, first-run
setup, profile-name capture, hashing, login throttling, session revocation,
logout), task/event CRUD,
validation, the full demo acceptance flow, rejection, duplicate-execution
protection, planner de-duplication, read-only commands, reminders, email parsing
and local-mode refusal, daily briefing, weekly review, free-time search, task
completion, reminder dismissal, automation readiness, settings, activity
logging, MCP tool mapping, MCP startup fallback, live `/api/system` status and a
real stdio MCP handshake. Tests use an isolated temporary database.

---

## Login and safety

LifeDesk now **fails closed**. Every `/api` route except the auth handshake and
`/api/health` returns `401` without a valid session, so the React app cannot
render workspace data before sign-in.

- **First run:** `/api/auth/status` reports `configured: false` and the app shows
  a setup screen. The owner username defaults to `owner`, the profile name to
  **Ari Mensha**, and the password must be at least 8 characters. Setup can run
  only once.
- **Profile name:** the setup name is written to `settings.display_name`. The
  greeting, sidebar, mobile header, avatar initials and dashboard all read it
  live; editing **Display name** in Settings updates them immediately. Only the
  exact old seeded placeholder (`Ari Mensah`) is migrated at startup.
- **Storage:** passwords are hashed with PBKDF2-HMAC-SHA256 (240,000 iterations,
  random salt). Plain-text passwords are never stored or returned.
- **Sessions:** random 256-bit tokens; only their SHA-256 hash is stored in
  `auth_sessions`. The browser gets an HttpOnly, SameSite=Lax cookie that expires
  after 7 days by default. Logout deletes the server-side session, so replaying
  the old cookie fails.
- **Throttling:** five failed logins per username per five minutes return `429`.
- **Reset:** delete `backend/lifedesk.db` to erase the account **and all data**,
  then create a new password on the next start.

Optional bootstrap for deployments/CI (otherwise use the setup screen):

```powershell
$env:LIFEDESK_AUTH_USER = "owner"
$env:LIFEDESK_AUTH_PASSWORD = "a-strong-password"
# Optional: $env:LIFEDESK_SESSION_DAYS = "7"
# Optional: $env:LIFEDESK_COOKIE_SECURE = "1"   # HTTPS deployments only
```

The bootstrap password is hashed on first startup; you can remove the variable
afterward. It is never written to the database in plain text.

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

### Sending email through MCP

1. Configure SMTP for the MCP server (see the email setup section below).
2. In the **Command Center**, run:
   `Send mail to vishnuvardhan7219@gmail.com saying HI`
3. Approve the proposed `send_email` action, then **Execute approved**.
4. The MCP server's `mail_send` tool delivers the message over SMTP. Activity
   records the call as an external MCP operation, not a local simulation.

Approval alone sends nothing, and local/demo mode refuses to send rather than
pretending delivery.

### Automation catalog

Open **Automations** in the sidebar. The page lists 16 automations grouped by
daily planning, focus, tasks, reminders, communication, research and files.
Every status is computed by `GET /api/automations` from the live provider
boundary, not hardcoded in the UI:

- **Ready** — the active provider exposes the tools the command needs.
- **Needs setup** — the capability is implemented but needs credentials or an
  optional MCP tool (email is the current example).
- **Paused** — an MCP call is failing; no local fallback is active.
- **Roadmap** — a planned external MCP integration (web research, weather,
  Slack/Teams, Drive search), clearly labelled as not wired yet.

With local providers the catalog reports **11 of 16 ready (69%)** and 12
implemented; configuring SMTP raises it to 12 of 16. Clicking **Open command**
loads the example into the Command Center. All writes still go through the same
approval gate.

New commands in this build:

| Command | Type | What happens |
| --- | --- | --- |
| `Give me my daily briefing` | Read-only | Today's events, open/overdue tasks, pending reminders, next event |
| `Review my week` | Read-only | Seven-day completions, created tasks, busy minutes, open work |
| `Find a free 90-minute slot tomorrow` | Read-only | Conflict-free gaps inside the working window |
| `Complete task review lecture notes` | Approval-gated | Matches an open task by title and marks it done |
| `Dismiss the reminder about course form` | Approval-gated | Matches a pending reminder and dismisses it |

---

## Architecture

```
frontend/src
  pages/            Login · Dashboard · CommandCenter · Automations · Calendar
                    Tasks · Planner · Approvals · Activity · Settings
  components/       AuthProvider, Layout, WorkflowView, UI primitives, Toast
  lib/              typed API client, formatting, hooks, types

backend/app
  main.py           FastAPI app, CORS, lifespan (init + auth bootstrap + seed)
  security.py       PBKDF2 password hashes, sessions, login throttling
  routers/auth.py   status, setup, login, logout, me
  db.py             schema + SQLite connections
  domain.py         provider-agnostic Pydantic models
  providers/
    base.py         CalendarProvider / TaskProvider / ReminderProvider / MailProvider ABCs
    local_*.py      SQLite implementations (Demo Mode)
    registry.py     the single composition root that selects providers
    mcp_client.py   official Python MCP SDK bridge (stdio + streamable HTTP)
    mcp_adapter.py  MCP providers, tool contract, startup probe + runtime status
  services/
    intent.py       deterministic command parsing
    ai.py           AIProvider abstraction (deterministic default)
    planner.py      conflict-aware scheduling algorithm (pure functions)
    workflows.py    command -> plan -> proposed actions (writes nothing)
    execution.py    approval decisions + guarded execution + activity
    activity.py     execution log
    settings.py     validated preferences
  routers/          thin HTTP layer over services/providers
mcp_server/         bundled reference MCP server (stdio; SMTP only for mail_send)
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
| GET | `/api/auth/status` | Public: setup/configured + current session state |
| POST | `/api/auth/setup` | First-run owner account (only when unconfigured) |
| POST | `/api/auth/login` · `/api/auth/logout` | Create / revoke the session cookie |
| GET | `/api/auth/me` | Current signed-in owner |
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
| GET | `/api/system` | Provider mode, MCP connection/fallback, AI and integration status |
| GET | `/api/automations` | Automation catalog with provider-derived readiness and summary |

---

## MCP provider mode

Provider mode is a composition switch. Routes, the workflow engine, approvals
and the UI are unchanged; only `providers/registry.py` chooses local or MCP
implementations.

### Bundled reference server (no credentials)

The repository includes `backend/mcp_server/server.py`, a real MCP server that
exposes the calendar, task, reminder and email tools. Calendar/task/reminder data
lives in the same `backend/lifedesk.db`, which makes switching modes easy to
demo. Email is the exception: `mail_send` delivers over SMTP using the server's
`LIFEDESK_SMTP_*` environment variables. The backend spawns the server over
stdio; you do not start it in a second terminal.

```powershell
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:LIFEDESK_PROVIDER_MODE = "mcp"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check the connection and the active mode:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/system
```

A healthy response has `provider_mode: "mcp"`, `mcp.status: "connected"` and
the discovered tool list. The Settings screen shows the same status. Set
`LIFEDESK_PROVIDER_MODE=local` and restart to return to SQLite providers.

### Configuration

Copy `backend/.env.example` to `backend/.env` if you prefer a file, then start
uvicorn with `--env-file .env`. `.env` is git-ignored.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LIFEDESK_PROVIDER_MODE` | `local` | `local` or `mcp` |
| `LIFEDESK_MCP_TRANSPORT` | `stdio` | `stdio` or `http` (streamable HTTP) |
| `LIFEDESK_MCP_COMMAND` | current Python interpreter | stdio server executable |
| `LIFEDESK_MCP_ARGS` | `["-m","mcp_server.server"]` | JSON array of stdio arguments |
| `LIFEDESK_MCP_CWD` | `backend/` | working directory for the stdio server |
| `LIFEDESK_MCP_ENV` | `{}` | JSON object of extra env variables for the stdio server (credentials belong here) |
| `LIFEDESK_MCP_URL` | empty | streamable HTTP endpoint for an external bridge |
| `LIFEDESK_MCP_HEADERS` | `{}` | JSON object of HTTP headers (for example a bearer token) |
| `LIFEDESK_MCP_LABEL` | reference label | non-secret name shown in status |
| `LIFEDESK_MCP_TIMEOUT` | `15` | seconds for a handshake/tool call |
| `LIFEDESK_MCP_FALLBACK` | `local` | `local` falls back on startup failure; `error` fails startup |
| `LIFEDESK_SMTP_HOST` | `smtp.gmail.com` | SMTP host used by the MCP server's `mail_send` |
| `LIFEDESK_SMTP_PORT` | `587` | SMTP port (`465` enables implicit TLS) |
| `LIFEDESK_SMTP_USER` | empty | SMTP login; required for real delivery |
| `LIFEDESK_SMTP_PASSWORD` | empty | SMTP password or Gmail App Password; never commit it |
| `LIFEDESK_SMTP_FROM` | same as user | From address |
| `LIFEDESK_SMTP_STARTTLS` | `1` | `0` disables STARTTLS (plain port 25/2525) |
| `LIFEDESK_SMTP_SSL` | `0` | `1` forces implicit TLS |

### Failure behavior

- **Startup:** the backend calls `tools/list` and requires the 13
  calendar/task/reminder tools in the contract below. `mail_send` is optional:
  a server without it still starts, reports email as unavailable in
  `/api/system` and Settings, and keeps every non-mail provider working. If the server is missing, times out, or is incomplete, the
  default `local` fallback starts the app on SQLite providers and reports
  `provider_mode: "local-fallback"`, `mcp.status: "error"` and the reason in
  Settings. With `LIFEDESK_MCP_FALLBACK=error`, startup fails instead.
- **Runtime:** provider errors surface as HTTP 503 and degrade the reported
  health: `/api/system` (and the Settings, sidebar and dashboard status) shows
  `mcp.status: "error"` with the last failure, while `provider_mode` stays
  `mcp`. There is deliberately no automatic write fallback, because silently
  switching stores mid-session could create data in the wrong place. The next
  successful MCP call restores `mcp.status: "connected"`; every request opens a
  fresh MCP session, so a restarted server recovers without restarting FastAPI.

### External auth and setup you must provide

LifeDesk does not implement Google/Outlook OAuth and never stores provider
credentials in its database. An external bridge owns that flow:

- **HTTP bridge:** run an MCP server that implements the tool contract, then set
  `LIFEDESK_MCP_URL` and, if it requires authentication,
  `LIFEDESK_MCP_HEADERS` (for example
  `{"Authorization":"Bearer ..."}`). Keep tokens in the environment or
  `.env`, never in the repository or a status label.
- **Stdio bridge:** set `LIFEDESK_MCP_COMMAND`, `LIFEDESK_MCP_ARGS` and
  `LIFEDESK_MCP_ENV` with whatever credentials the bridge needs.
- **Google Calendar example:** create a Google Cloud project, enable the Google
  Calendar API, configure an OAuth consent screen, create an OAuth client
  (client ID and secret), and obtain a refresh token with the calendar scope.
  Those values belong to the bridge, not to LifeDesk. The bridge maps Google's
  event objects to the fields below (ISO-8601 local datetimes, `id`, `title`,
  `description`, `start_at`, `end_at`, `location`, `kind`, `source`).
- **Outlook/Microsoft 365** needs the equivalent Azure app registration,
  delegated `Calendars.ReadWrite` permission and a refresh token, again handled
  by the bridge.
- **Email (Gmail example):** enable 2-Step Verification on the Google account,
  create a 16-character **App Password**, then put it in `backend/.env` as
  `LIFEDESK_SMTP_USER` / `LIFEDESK_SMTP_PASSWORD` and start the backend with
  `--env-file .env`. Gmail rejects account passwords for SMTP. The bundled
  server reads these variables directly; in an external stdio bridge pass them
  through `LIFEDESK_MCP_ENV`. LifeDesk never stores or displays the password,
  and `mail_status` only reports whether credentials are present.

Arbitrary MCP servers do **not** work without an adapter: the provider expects
the exact tool names and JSON shapes below. If your bridge exposes different
names (for example `list_events`), add a thin translation layer in the bridge
rather than changing the workflow engine.

### Tool contract

| Tool | Arguments | Returns |
| --- | --- | --- |
| `calendar_list_events` | `start`, `end` (ISO) | `{events: [...]}` |
| `calendar_get_event` | `event_id` | `{event: {...} | null}` |
| `calendar_create_event` | `title`, `start_at`, `end_at`, `description`, `location`, `kind`, `source` | `{event: {...}}` |
| `calendar_update_event` | `event_id`, `fields` | `{event: {...} | null}` |
| `calendar_delete_event` | `event_id` | `{deleted: bool}` |
| `tasks_list` | optional `status`, `priority`, `search` | `{tasks: [...]}` |
| `tasks_get` | `task_id` | `{task: {...} | null}` |
| `tasks_create` | task fields | `{task: {...}}` |
| `tasks_update` | `task_id`, `fields` | `{task: {...} | null}` |
| `tasks_delete` | `task_id` | `{deleted: bool}` |
| `reminders_list` | optional `status` | `{reminders: [...]}` |
| `reminders_create` | `title`, `remind_at`, `note` | `{reminder: {...}}` |
| `reminders_dismiss` | `reminder_id` | `{reminder: {...} | null}` |
| `mail_send` (optional) | `to` (list), `subject`, `body` | `{sent, message_id, to, subject, server}` |
| `mail_status` (optional) | none | `{configured, transport, host, from}` |
| `lifedesk_status` | none | server/storage diagnostics |

The bundled server is the executable reference for this contract.

---

## Extension points after the prototype

Nothing in the frontend or workflow engine needs a redesign. The replacement
points are deliberately isolated:

| Component | Current prototype | Next step |
| --- | --- | --- |
| `providers/mcp_adapter.py` | Real MCP providers, required-tool probe and bundled reference server | Point at an external bridge; add provider-specific field mapping there |
| `providers/registry.py` | Selects local or MCP providers; startup fallback to local | Add per-service provider selection if calendar and tasks live in different servers |
| Calendar/Task providers | SQLite `Local*Provider` classes plus the reference MCP server | Google/Outlook bridge implementing the same tool contract |
| `services/ai.py` | `DeterministicAIProvider` | Implement `LLMProvider.interpret()` behind the same `AIProvider` interface; set `LIFEDESK_AI_PROVIDER=llm`; keep deterministic fallback |
| Reminders | Local SQLite provider + dashboard list | Optional notifications MCP tool; add a dedicated reminder screen if needed |
| Email | `MailProvider` with MCP `mail_send` over SMTP; local mode refuses to send | Add attachments, CC/BCC, or swap SMTP for a provider API inside the MCP server |
| Activity `simulated` flag | Derived from provider kind (`local` vs `mcp`) | Add per-tool provenance and external-server labels |
| Settings → Integrations | Live MCP status and fallback reason from `/api/system` | Add OAuth connection health for an external bridge |
| Auth/multi-user | Single local workspace | Add user scoping to `user_id` columns and provider credentials; out of scope for the ideathon prototype |
| External calendar sync | Local calendar only | Google/Outlook OAuth adapter implementing `CalendarProvider` |

Deliberately **not** implemented now: OAuth flows, hosted LLM calls, accounts,
and third-party sync. The bundled MCP reference server is local; an external
Google/Outlook bridge is not shipped. The prototype is honest about this in the
UI, the `/api/system` payload, and this document.

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
- The bundled MCP server is a reference implementation over the same SQLite
  database, not a Google/Outlook sync. External MCP servers must implement the
  documented tool contract and own their OAuth credentials.
- Email delivery needs both the optional `mail_send` tool and SMTP credentials
  on the MCP server. Without either, the `send_email` action fails visibly while
  the other providers keep working; local mode never simulates delivery.
- Each MCP tool call opens a fresh session (simple failure isolation, but more
  overhead than a persistent connection).
