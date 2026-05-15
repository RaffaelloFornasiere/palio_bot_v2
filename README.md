# Palio Bot

Natural-language management of Palio (medieval festival) data. Users talk
in Italian to an LLM agent; the agent edits JSON state files (games,
leaderboard) through structured JSONPath tools.

Three surfaces share the same backend:

- **CLI** (`python -m palio_bot`) — terminal interaction with rich output.
- **Telegram bot** (`python -m palio_bot.telegram_bot`) — text and audio
  messages (transcribed via Whisper/Groq).
- **React webapp** — public read-only view (leaderboard/games) plus a
  manual editor authenticated via Google sign-in (Firebase).

## Architecture

Two tiers:

- **`palio-core`** (`python -m palio_bot.core`): FastAPI service on port
  8000. The single writer of `data/*.json`. Exposes REST for read/write,
  WebSocket for events, and serves the React build at `/`.
- **Adapter** (CLI, Telegram, eval): thin clients over HTTP/WS. Each
  adapter hosts its own agent loop and conversation.

Every agent edit goes through `palio-core` as a "session": acquire →
PUT (write-through to disk + git commit) → commit (squash the
session's commits + tag the day if the festival-day boundary rolled).

`data/` is a self-managed git repository (the history layer). Every
write produces a commit; every save squashes the session and moves the
public-visible `refs/palio/last_save` ref. The public webapp reads from
`last_save`; the authenticated editor reads the working tree (live
in-progress state).

Full design notes: `docs/refactor/01_core_service_split.md` (core/adapter
split) and `docs/refactor/03_history_and_rollback.md` (git history layer).

## Requirements

- Python 3.11+
- Node 18+ (for the frontend)
- `git` binary on PATH (for ad-hoc inspection of `data/.git/`; the
  Python layer uses pygit2 with bundled libgit2, no shell-out)

## Setup

```bash
# 1. Backend
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Configuration
cp .env.example .env   # if present, else create empty .env
# edit .env with at least OPENROUTER_API_KEY

# 3. Frontend (optional, dev mode)
cd website && npm install && npm run dev
# production: npm run build → palio-core serves the static build at /
```

## Configuration (`.env`)

| Variable | Meaning | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (default LLM provider) | — (required) |
| `OPENROUTER_MODEL` | Model slug | `anthropic/claude-3.5-haiku` |
| `LLM_PROVIDER` | `openrouter` or `ollama` | `openrouter` |
| `PALIO_CORE_URL` | Core URL (single source of truth for host:port) | `http://localhost:8000` |
| `PALIO_CORE_TOKEN` | Bearer token required for state-mutating endpoints | — (auth disabled in dev) |
| `FIREBASE_CONFIG_PATH` | Firebase web config JSON for editor Google sign-in | `website/firebase-config.json` |
| `EDITOR_ALLOWED_EMAILS` | Allowlist of Google emails for the editor (comma-separated) | — |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | — (if using Telegram) |
| `ALLOWED_USER_ID` | Authorized user ID (Telegram) | — |
| `ALLOWED_CHAT_ID` | Restrict the bot to a single chat/group; updates from any other chat (DMs included) are dropped | — (no chat restriction) |
| `GROQ_API_KEY` | Groq API key for Whisper (Telegram audio) | — (if receiving audio) |
| `CORS_ALLOWED_ORIGINS` | CORS allow-list (comma-separated) | localhost dev ports |

## Run

```bash
# Start palio-core (always required)
python -m palio_bot.core

# In a separate shell, pick an adapter:
python -m palio_bot                  # interactive CLI
python -m palio_bot.telegram_bot     # Telegram bot
```

The React frontend in dev mode runs separately (`npm run dev` inside
`website/`, port 5173). In production `palio-core` serves the built
static assets at `/`.

## Adapter commands

CLI (`python -m palio_bot`):
- `/close` — save the session (squash + tag).
- `/cancel` — discard the session (restore files to the last save).
- `/status` — show state.
- `/stop` — interrupt the current run.
- `/quit` — exit.

Telegram (`python -m palio_bot.telegram_bot`):
- `/start` — start the bot (shows your user ID if `ALLOWED_USER_ID` is unset).
- `/status` `/close` `/cancel` `/stop` — same as CLI.
- `/save` — save the session without closing it.
- `/games_status` — show game state.
- `/leaderboard` — preview the recomputed leaderboard and apply it with an
  inline confirm button (goes straight through core, no agent session).
- `/mode` — toggle the render mode between **verbose** (thinking, tool
  calls, token counts) and **simple** (a "working…" placeholder replaced
  by the agent's final reply; `<thinking>` blocks and code fences stripped).
  The setting is shared per chat and persisted to
  `data/telegram_settings.json` (gitignored); it takes effect on the next
  run without restarting.
- Audio messages: auto-transcribed via Whisper (Groq).

## Agent tools

The agent edits JSON via JSONPath. All tools live in
`src/palio_bot/tools/multi_json_editor_tool.py`:

| Tool | Effect |
|---|---|
| `json_view` | Read a subtree at the given path. |
| `json_set` | Set a value at the path. |
| `json_merge` | Deep-merge a partial object into the subtree. |
| `json_delete` | Delete the key / element at the path. |
| `json_append` | Append to an array. |
| `json_insert` | Insert into an array at a specific index. |
| `json_remove` | Remove an array element by index. |
| `json_history` | Numbered list of edits made in the current session. |
| `json_revert` | Undo the last N edits in the current session. |

Undo is scoped to the current session: once the user runs `/close`
(save), that session's edits become "saved state" and the agent can no
longer roll them back. Cross-save rollback is delegated to the editor
webapp (UI not yet implemented; see
`docs/refactor/03_history_and_rollback.md`).

## Managed JSON files

Three files in `data/`:

| File | Content | Agent-editable |
|---|---|---|
| `palio.json` | Palio definition (villages, games, rules) | no (read-only) |
| `palio_games_status.json` | Game state (scores, status, bonuses, penalties) | yes |
| `leaderboard.json` | Overall ranking | yes (but normally computed) |

The leaderboard is derived data from the previous two files. Recomputation
runs via `POST /api/leaderboard/apply` (with preview via
`POST /api/leaderboard/preview`). `apply` writes through the git history
layer and advances `refs/palio/last_save`, so the recomputed leaderboard
is immediately visible to the public (anonymous) read path.

Archived past years live in `data/<YYYY>/` and are served read-only from
`/api/{file}/{year}` (e.g. `/api/palio/2024`).

## Eval harness

```bash
scripts/run_all_evals.sh <model_slug> [<model_slug> ...]
# e.g. scripts/run_all_evals.sh openai/gpt-5.4-mini google/gemma-4-31b-it
```

Spins up a dedicated `palio-core` per scenario on a temp directory,
runs every step, diffs the canonical files against the expected state,
optionally calls the LLM judge for qualitative criteria. Per-model
output lands in `results/<model>/<scenario>.json`.

Scenarios live under `tests/scenarios/<name>/`:
- `scenario.json` — step definitions, prompts, expected changes, judge config.
- `seeds/*.json` — initial state (copied into the temp dir before each run).

Relevant per-scenario / per-step flags:
- `reset_between_steps: bool` (default `false`) — when `true`, each step
  starts with a new container and fresh seeds.
- `save_after: bool` per step (default `true`) — when `false`, the eval
  does NOT close the core session after the step, so the next step's
  `json_revert` can still see what the current step did.

Results can be browsed by opening `results/index.html` (built by
`scripts/build_results_viewer.py`).

## Test suite

```bash
pytest                       # full suite (unit + integration)
pytest tests/core/           # core only (HistoryService, sessions, read split, …)
pytest tests/tools/          # MultiJSONEditorTool
pytest tests/leaderboard/    # leaderboard updater
```

The eval scenarios under `tests/scenarios/` are NOT collected by pytest;
they run through `scripts/run_all_evals.sh`.

## Repository layout

```
src/palio_bot/        # Python code
├── core/             # palio-core (FastAPI + history layer)
├── core_client/      # HTTP / WS clients for the adapters
├── agent/            # agent loop + system prompt
├── llm_clients/      # provider adapters (openrouter, ollama)
├── tools/            # MultiJSONEditorTool + FileRegistry
├── cli/              # CLI entry point
├── telegram_bot/     # Telegram bot
├── eval/             # runner + judge + recorder
├── models/           # Pydantic validators for the JSON files
└── stream/           # event types

data/                 # runtime state + git history repo
tests/                # pytest suite + eval scenarios
website/              # React frontend (Vite + types generated from OpenAPI)
docs/                 # refactor plans + TODO + audit
docker/               # Dockerfile + compose
scripts/              # restore, eval runner, viewer builder
results/              # per-model eval output
```

## Tech stack

- **Backend**: Python 3.11+, FastAPI, Pydantic, pygit2.
- **Frontend**: React, TypeScript, Vite, types auto-generated from
  OpenAPI.
- **LLM**: OpenRouter (default) or Ollama (local). Provider adapters in
  `llm_clients/`. Default model: `anthropic/claude-3.5-haiku`.
- **Audio**: Whisper via Groq (Telegram voice messages).
- **Editor auth**: Firebase Google sign-in + email allowlist.

## Internal documentation

- `CLAUDE.md` — technical overview for AI assistants working in the repo.
- `docs/refactor/01_core_service_split.md` — core/adapter split design.
- `docs/refactor/02_web_editor.md` — web editor design.
- `docs/refactor/03_history_and_rollback.md` — git history layer design.
- `docs/TODO.md` — outstanding work.
