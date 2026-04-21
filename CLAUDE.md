# Palio Bot — Overview for Claude

Natural-language management of Palio (medieval festival) data. Users talk to an
LLM agent that edits JSON files through JSONPath tools; changes are staged in a
per-session temp copy and committed on `/close`. CLI, Telegram bot, and a
FastAPI server (serving a React frontend) all share the same `System`.

## Running

```bash
python -m palio_bot.core              # palio-core (file authority + event bus + FastAPI + React)
python -m palio_bot                   # interactive CLI (entry: cli/cli.py) — needs core running
python -m palio_bot.telegram_bot      # Telegram bot — needs core running
python -m palio_bot.eval --scenario tests/scenarios/<name> --model <slug>   # runner boots its own core
```

`.env` drives `Config` (`config.py`). Required: `OPENROUTER_API_KEY` when
`LLM_PROVIDER=openrouter` (the default).

## Architecture

Two tiers: **palio-core** owns `data/*.json` and serves HTTP/WS; **adapters**
(CLI, Telegram, eval) are thin clients. Full design:
`docs/refactor/01_core_service_split.md`.

```
palio-core (python -m palio_bot.core, port 8000)
 ├─ FastAPI: /api/files/*, legacy /api/{palio,leaderboard,palio_games_status}
 ├─ Sessions: acquire → PUT → commit/discard, per-file locks
 ├─ Event bus: WS /events (file_changed, lock_acquired, session_*)
 ├─ Leaderboard auto-recompute on commit
 └─ Serves React build at /

Adapter (CLI, Telegram, eval runner)
 ├─ CoreClient (httpx) + RemoteFileStore (session-bound)
 ├─ FileRegistry (local) — for config metadata (allow_edit, validators)
 ├─ Tools (multi_json_editor_tool) — uses RemoteFileStore
 ├─ Stream (local) — renders agent events to the surface
 ├─ Agent + LLM client
 └─ System — agent orchestration, session lifecycle via CoreClient
```

### Registered files

The container registers three files:

| name                 | source path                    | agent-editable |
|----------------------|--------------------------------|----------------|
| `palio`              | `data/palio.json`              | no             |
| `palio_games_status` | `data/palio_games_status.json` | yes            |
| `leaderboard`        | `data/leaderboard.json`        | yes            |

Staging lives inside core per session; canonical files only change on commit.

## Session lifecycle

1. First message → `System._create_session()` → adapter-local UUID + core
   `POST /api/sessions` → `RemoteFileStore.rebind(session_id)`.
2. Agent loop: LLM → tool call → `MultiJSONEditorTool.load/save` → core
   acquires (lock) + PUTs staged content → result back to LLM.
3. Conversation persists to `data/session.json` (adapter-side) each turn.
4. `/close` or `/save` → `CoreClient.commit(session_id)` → core atomically
   writes canonical files, recomputes leaderboard, emits `file_changed`,
   releases locks.
5. `/cancel` → `CoreClient.discard(session_id)` → staged content dropped.

## Events

Single unified WS bus. Core owns the broker (`core/stream.py`); adapters
connect via `core_client/stream_client.py` (`StreamClient`), which exposes
the same `add_consumer/put_event/start_processing` surface as before but
round-trips every event through `WS /events`. Producers publish — their
own events come back through the socket and are dispatched to local
consumers (pure loopback, no short-circuit). Reconnect is exponential
backoff capped at a 30 s budget; on exhaustion the adapter hard-fails.

Event types (Pydantic discriminated union in `stream/events.py`):
- Agent-side: `UserMessageEvent`, `AgentUpdateEvent`, `ToolUseEvent`,
  `ToolResultEvent`, `AgentCompleteEvent`, `AgentCancelledEvent`, `ErrorEvent`
- Core-side: `FileChangedEvent`, `LockAcquiredEvent`, `LockReleasedEvent`,
  `SessionStartedEvent`, `SessionCommittedEvent`, `SessionDiscardedEvent`

Consumers: `cli/cli_consumer.py`, `telegram_bot/telegram_consumer.py`,
`eval/recorder.py::EvalRecorder`.

## Eval harness (`src/palio_bot/eval/`)

- `runner.py` — boots a dedicated `CoreProcess` per scenario, calls
  `admin_reset(seeds_dir)` between steps, drives `System.send_message()`,
  diffs canonical files against expected, optionally calls the LLM judge.
- `judge.py` — OpenRouter call that rates `passed_criteria` / `failed_criteria`.
- `recorder.py` — `EvalRecorder` consumer attached to the unified bus per step.
- `patch.py` — applies JSONPath patches to compute expected state.
- Scenarios live in `tests/scenarios/<name>/` with `scenario.json` + `seeds/`.

## File structure

```
src/palio_bot/
├── __main__.py                    # CLI entry
├── config.py                      # Pydantic Settings (adapter)
├── container.py                   # DI — builds CoreClient, Agent, System
├── system.py                      # Session coordinator (agent orchestration)
├── file_store.py                  # FileStore protocol + DirectFileStore
├── leaderboard_updater.py         # Called by core on commit
├── core/                          # palio-core service
│   ├── app.py, __main__.py, config.py
│   ├── session_service.py, session_store.py, lock_manager.py
│   ├── file_store_local.py, stream.py, registry_factory.py
│   └── routes/  (files, sessions, admin, events_ws)
├── core_client/                   # HTTP + WS + subprocess helpers
│   ├── client.py, file_store_remote.py, stream_client.py, subprocess.py
├── agent/
│   ├── agent.py, models.py, system_prompt.py
├── llm_clients/
│   ├── base_client.py, chat_client.py, ollama_client.py
├── tools/
│   ├── file_registry.py, multi_json_editor_tool.py
├── stream/
│   ├── events.py, interfaces.py
├── models/                        # Pydantic validators for registered files
│   ├── palio_models.py, game_status_models.py, leaderboard_models.py
├── cli/
│   ├── cli.py, cli_consumer.py
├── telegram_bot/
│   ├── telegram_bot.py, telegram_consumer.py
├── eval/
│   ├── runner.py, judge.py, recorder.py, patch.py, __main__.py
├── services/
│   └── audio_transcription.py     # Whisper via Groq
└── utils/
    └── api_logger.py

data/                              # Runtime state (mostly gitignored)
├── palio.json
├── palio_games_status.json
├── leaderboard.json
├── session.json                    # adapter conversation persistence
└── <year>/…                        # archived years served by /api/*/{year}

tests/scenarios/                   # Eval scenarios (NOT unit tests)
docs/                              # TODO, REFACTOR_PLAN, EVAL_PLAN, audit/
website/                           # React frontend (types generated from FastAPI)
docker/                            # Dockerfiles + compose
scripts/                           # restore.sh, restore_games_status.py
```

## CLI commands

`/close` save · `/cancel` discard · `/status` · `/stop` interrupt current run · `/quit`

## Notes for edits

- Tool error messages are Italian (user-facing). Keep log/exception text in
  English.
- `session.json` and `*.backup_*.json` are gitignored; don't commit them.
  (`*_tmp.json` no longer exists — staging lives inside core's memory.)
- CORS for core is restricted to localhost dev ports; override via
  `CORS_ALLOWED_ORIGINS=...` (comma-separated).
- Year-scoped API routes (`/api/palio/{year}`, etc.) are bounded `1900..2100`.
- `PALIO_CORE_URL` (default `http://localhost:8000`) points adapters at core.
- `PALIO_CORE_PORT` sets core's listen port; defaults to `8000`.
