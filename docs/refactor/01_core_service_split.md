# Core/Client Split — `palio-core`

## Goal
Extract a slim **core service** that is the single writer of `data/*.json`
and the single broker for session events. CLI, Telegram, and the web editor
become thin clients over HTTP + WS. The agent (LLM, prompts, tools) lives in
each adapter — **not** in core.

## Why
Three processes today each build their own `System` via `container.py`. Files
on disk are the only sync point, so web edits can't notify a running bot, two
processes can clobber each other's commits, and adding a fourth surface means
duplicating the full stack.

## Architecture
```
palio-core (always up)
 ├─ exclusive writer for data/*.json
 ├─ HTTP: read, session-staged write, commit
 ├─ WS /events: pub/sub fanout
 └─ NO LLM, NO agent, NO tools
     ▲            ▲              ▲
  telegram-bot   cli-agent    web-editor
  (agent+LLM)   (agent+LLM)    (no agent)
```

## API (essentials)
- `GET  /api/files/{file}` → content + ETag.
- `GET  /api/schema/{file}` → Pydantic-derived JSON Schema (for the editor).
- `POST /api/sessions` → `{session_id}` (body: `label`).
- `POST /api/sessions/{id}/acquire/{file}` → locks file, returns content.
  Second acquirer gets `409`.
- `PUT  /api/sessions/{id}/files/{file}` → staged write, Pydantic-validated.
- `POST /api/sessions/{id}/commit` → atomic promote to canonical, recompute
  leaderboard, emit `file_changed`, release locks.
- `POST /api/sessions/{id}/discard` → drop staged, release locks.
- `WS   /events` → `file_changed`, `session_*`, `lock_*`, plus adapter-
  published `user_message`/`agent_update`/`tool_*`. Bearer-token auth.

## Lock model
One session per file. Acquire on-demand, release on commit/discard/idle-5min.
Commit is atomic **per session** (all touched files together) — matches
today's `/close`.

## Reuse
- `FileRegistry`, validators, `leaderboard_updater.py` → moved into core as-is.
- `FileManager` logic → absorbed into core's session/file store.
- `Agent` + `MultiJSONEditorTool` → unchanged; tool gets a
  `RemoteFileRegistry` shim that flushes to core per tool call.

## Effort
- Core extraction (FastAPI + session store + event bus): 1d
- `CoreClient` + remote-registry shim: 0.5d
- CLI adapter rewire: 0.5d
- Telegram adapter rewire: 1d
- Retire standalone `api_server`, fold read routes into core: 0.5d
- Integration + eval harness reroute: 0.5d
- **Total: ~4 days**

## Migration order
1. Stand up core on a new port with reads + event bus only.
2. Add session/staged-write endpoints; test with `curl`.
3. Write `CoreClient`.
4. **Migrate eval harness first** — regression net before touching live adapters.
5. CLI.
6. Telegram.
7. Retire standalone `api_server`; React frontend points at core.

Each step is independently shippable — at every commit one full stack works.

## Disruption
Moderate. The agent loop is untouched (the hard part). Mostly plumbing:
`container.py`, `FileManager` → `CoreClient`, tool's registry becomes remote.
Main risks: eval harness breaking mid-migration; `_tmp.json` semantics moving
server-side; `session.json` resumability across core restarts becomes a no-op
(acceptable behavior change).

## Deployment
Dev: `uvicorn palio_bot_core.app:app`. Adapters hit `localhost:8000`. Prod:
systemd unit per process, shared `data/` volume only mounted into core. Token
via `.env`.

## Open questions
1. **PUT payload**: full-document or patch list? → **full-document**, simpler.
2. **Core restart during staged session**: lose staged edits? → **yes**,
   adapters reconnect and re-acquire.
3. **Tool flush cadence**: per tool call or per turn? → **per tool call**,
   matches today's immediate validation feedback.
4. **Telegram multi-chat**: one session per `chat_id`? → **yes**, label
   `telegram:<chat_id>`.

## Non-goals
Horizontal scaling, DB backend, generic plugin system.
