# Palio Bot — Overview for Claude

Natural-language management of Palio (medieval festival) data. Users talk
to an LLM agent that edits JSON files through JSONPath tools; writes go
through immediately (write-through) and are recorded as git commits in a
repo inside `data/`. CLI, Telegram bot, and a FastAPI server (serving a
React frontend) all share the same `System`.

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
`docs/refactor/01_core_service_split.md` (Phase 1, core split) and
`docs/refactor/03_history_and_rollback.md` (Phase 2, git history).

```
palio-core (python -m palio_bot.core, port 8000)
 ├─ FastAPI: /api/files/*, legacy /api/{palio,leaderboard,palio_games_status}
 ├─ Sessions: acquire → PUT (write-through + git commit) → commit (squash)
 ├─ Event bus: WS /events (file_changed, session_*)
 ├─ History layer: git repo in data/ (HistoryService, pygit2)
 │     • per-PUT commits during a session
 │     • commit = squash + move `refs/palio/last_save`
 │     • lazy daily tag at festival-day rollover (cutoff 05:00 Europe/Rome)
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

There is no in-memory staging. Every PUT writes atomically to disk and
produces a git commit; `commit()` only squashes those commits into one
and moves the public-visible `refs/palio/last_save` ref.

### Read paths (public vs editor)

| Reader              | Source                                  |
|---------------------|-----------------------------------------|
| Edit webapp (auth)  | working tree (HEAD = live state)        |
| Public webapp       | `refs/palio/last_save` (last saved)     |
| Agent / CLI         | working tree (HEAD)                     |

Branching happens in `core/routes/files.py` via `is_authenticated`
(from `core/auth.py`). In dev mode (no `PALIO_CORE_TOKEN` and no
Firebase configured) both anonymous and authed callers read the working
tree — backward-compatible.

## Session lifecycle

1. First message → `System._create_session()` → adapter-local UUID + core
   `POST /api/sessions` → `RemoteFileStore.rebind(session_id)`.
2. Agent loop: LLM → tool call → `MultiJSONEditorTool.save` → core
   `PUT /api/sessions/{id}/files/{name}` (with optional `tool` param) →
   `LocalFileStore.write_atomic` (atomic os.replace) +
   `HistoryService.record_write` (git commit) → result back to LLM.
3. Conversation persists to `data/session.json` (adapter-side) each turn.
4. `/close` or `/save` → `CoreClient.commit(session_id)` →
   `HistoryService.finalize_save` squashes per-PUT commits since
   `last_save` into one, moves the `last_save` ref, lazy-tags the
   previous festival day if rolled over.
5. `/cancel` → `CoreClient.discard(session_id)` →
   `HistoryService.revert_session_files` restores every touched file to
   its `last_save` state and commits a `cancel session <id>` marker.

### Agent rollback tools

The agent has two tools scoped to the current session (commits between
`refs/palio/last_save` and HEAD):

- `json_history(file_name, limit=10)` — numbered list, 1 = most recent,
  with the tool name attached.
- `json_revert(file_name, n_steps)` — undo the last `n_steps` writes.

Beyond `last_save` (= previous saved states) the agent has no access;
those are reachable only via the manual webapp rollback UI (not yet
implemented; see `docs/refactor/03_history_and_rollback.md`).

## Commit message format

Every git commit uses the canonical identity `palio-core <noreply@palio>`;
the real human/source goes into trailers (parsable with
`git interpret-trailers`):

```
update palio_games_status.json

source: agent|webapp|cli
committer: <telegram user id> | <auth user> | <os user>
tool: json_set|json_merge|...|manual
session: <session_id>
files: palio_games_status.json
```

## Events

Single unified WS bus. Core owns the broker (`core/stream.py`); adapters
connect via `core_client/stream_client.py` (`StreamClient`), which exposes
the same `add_consumer/put_event/start_processing` surface, round-tripping
every event through `WS /events`. Reconnect is exponential backoff capped
at a 30 s budget; on exhaustion the adapter hard-fails.

Event types (Pydantic discriminated union in `stream/events.py`):
- Agent-side: `UserMessageEvent`, `AgentUpdateEvent`, `ToolUseEvent`,
  `ToolResultEvent`, `AgentCompleteEvent`, `AgentCancelledEvent`, `ErrorEvent`
- Core-side: `FileChangedEvent`, `SessionStartedEvent`,
  `SessionCommittedEvent`, `SessionDiscardedEvent`

`file_changed` fires at each PUT (write-through), not at commit.
`session_committed` fires at the save (squash).

Consumers: `cli/cli_consumer.py`, `telegram_bot/telegram_consumer.py`,
`eval/recorder.py::EvalRecorder`.

## Eval harness (`src/palio_bot/eval/`)

- `runner.py` — boots a dedicated `CoreProcess` per scenario, calls
  `admin_reset(seeds_dir)` at start (and on each step in `reset` mode),
  drives `System.send_message()`, diffs canonical files against expected,
  optionally calls the LLM judge.
- `judge.py` — OpenRouter call that rates `passed_criteria` /
  `failed_criteria`.
- `recorder.py` — `EvalRecorder` consumer attached to the unified bus per
  step.
- `patch.py` — applies JSONPath patches to compute expected state.
- Scenarios live in `tests/scenarios/<name>/` with `scenario.json` +
  `seeds/`. Each step may set `"save_after": false` to keep the core
  session alive into the next step — needed when the next step needs
  to `json_revert` something the current step did (otherwise the save
  resets `last_save` and the revert scope is empty).

`admin/reset` (used between scenarios) replaces canonical files with
seeds AND calls `HistoryService.snap_workdir` to anchor `last_save` at
the new working tree — without this anchor a subsequent
`json_revert(n=all)` would walk past the reset boundary into pre-reset
state.

## File structure

```
src/palio_bot/
├── __main__.py                    # CLI entry
├── config.py                      # Pydantic Settings (adapter)
├── container.py                   # DI — builds CoreClient, Agent, System
├── system.py                      # Session coordinator (agent orchestration)
├── file_store.py                  # FileStore protocol + DirectFileStore
├── leaderboard_updater.py         # Compute/write helper (no longer auto-run on commit)
├── core/                          # palio-core service
│   ├── app.py, __main__.py, config.py
│   ├── session_service.py, session_store.py
│   ├── file_store_local.py, history.py, stream.py, registry_factory.py
│   ├── auth.py                    # bearer + Firebase verification
│   └── routes/  (files, sessions, admin, events_ws, editor, leaderboard)
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

data/                              # Runtime state — managed git repo
├── .git/                          # history layer (auto-created on first core boot)
├── .gitignore                     # ignores session.json, *_tmp.json, archived years
├── palio.json
├── palio_games_status.json
├── leaderboard.json
├── session.json                   # adapter conversation persistence (gitignored)
└── <year>/…                       # archived years served by /api/*/{year} (gitignored)

tests/                             # pytest suite (unit + integration)
├── core/                          # core-side: HistoryService, sessions, reads, …
├── tools/                         # MultiJSONEditorTool unit tests
├── leaderboard/                   # leaderboard updater unit tests
├── scenarios/                     # Eval scenarios (NOT unit tests)
└── …
docs/                              # TODO, refactor plans, audit/
website/                           # React frontend (types generated from FastAPI)
docker/                            # Dockerfiles + compose
scripts/                           # restore.sh, run_all_evals.sh, build_results_viewer.py
results/                           # Per-model eval result JSONs + viewer HTML
```

## CLI commands

`/close` save · `/cancel` discard · `/status` · `/stop` interrupt current run · `/quit`

## Notes for edits

- Tool error messages are Italian (user-facing). Keep log/exception text in
  English.
- `Tool.call()` in `agent/models.py` pre-validates required parameters
  against `parameters_schema["required"]` and returns a structured
  `ToolResult` error to the LLM if any are missing — avoids opaque
  Python `TypeError` reaching the model.
- `session.json` and `*.backup_*.json` are gitignored (project root and
  inside `data/`).
- CORS for core is restricted to localhost dev ports; override via
  `CORS_ALLOWED_ORIGINS=...` (comma-separated).
- Year-scoped API routes (`/api/palio/{year}`, etc.) are bounded
  `1900..2100` and read directly from `data/<year>/` (no history layer).
- `PALIO_CORE_URL` (default `http://localhost:8000`) is the single source
  of truth for both adapter target and core listen port. Override with
  `PALIO_CORE_URL=...` or `python -m palio_bot.core --port N` (the flag
  rewrites the URL in-process).
- Importing `palio_bot.core.app` runs `create_app()` at module load
  (FastAPI convention for uvicorn). That call calls
  `HistoryService.init_repo()` on the default `data/`, which creates
  `data/.git/` with a seed commit. This is intentional in production
  but appears as a side effect during test imports.
