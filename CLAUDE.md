# Palio Bot — Overview for Claude

Natural-language management of Palio (medieval festival) data. Users talk to an
LLM agent that edits JSON files through JSONPath tools; changes are staged in a
per-session temp copy and committed on `/close`. CLI, Telegram bot, and a
FastAPI server (serving a React frontend) all share the same `System`.

## Running

```bash
python -m palio_bot                   # interactive CLI (entry: cli/cli.py)
python -m palio_bot.telegram_bot      # Telegram bot
python -m palio_bot.api.api_server    # FastAPI + React build
python -m palio_bot.eval --scenario tests/scenarios/<name> --model <slug>
```

`.env` drives `Config` (`config.py`). Required: `OPENROUTER_API_KEY` when
`LLM_PROVIDER=openrouter` (the default).

## Architecture

```
Container (DI)
 ├─ LLM client            llm_clients/chat_client.py (OpenAI-compat → OpenRouter / llama.cpp)
 │                        llm_clients/ollama_client.py (Ollama native)
 ├─ FileRegistry          tools/file_registry.py — registered files with optional Pydantic validators
 ├─ FileManager           file_manager.py — copy-on-write temp lifecycle for safety-copy files
 ├─ Tools                 tools/multi_json_editor_tool.py — view / set_field / merge /
 │                        delete_field / append / insert_at / remove_at / undo, per-file
 ├─ Stream                stream/stream.py — async event bus
 ├─ Agent                 agent/agent.py — tool-call loop, emits events
 └─ System                system.py — session coordinator (Producer of events)
```

### Registered files

The container registers three files in `FileRegistry`:

| name                 | source path                          | editable | safety copy |
|----------------------|--------------------------------------|----------|-------------|
| `palio`              | `data/palio.json`                    | no       | no          |
| `palio_games_status` | `data/palio_games_status.json`       | yes      | yes         |
| `leaderboard`        | `data/leaderboard.json`              | yes      | yes         |

`palio` is read-only context. The other two are edited via their `_tmp.json`
copies and committed on save.

## Session lifecycle

1. First message → `System.send_message()` starts a session. `FileManager.start_session()`
   copies every safety-copy file to `<name>_tmp.json`.
2. Agent loop: LLM → tool call → `MultiJSONEditorTool` mutates the `_tmp.json`
   → result fed back → repeat until the LLM replies with text only.
3. Session state (messages, tool calls) persisted to `data/session.json` after
   each turn so the conversation survives restarts.
4. `/close` → `FileManager.commit()` copies every modified `_tmp.json` back to
   its canonical path, then the leaderboard is recomputed
   (`leaderboard_updater.py`).
5. `/cancel` → `FileManager.discard()` removes temp files and the session.

## Events

`UserMessageEvent`, `AgentUpdateEvent`, `ToolUseEvent`, `ToolResultEvent`,
`AgentCompleteEvent`, `ErrorEvent`, `CancellationEvent`. Consumers
(`cli/cli_consumer.py`, `telegram_bot/telegram_consumer.py`, the WebSocket
endpoint in the API server) receive the stream and render in real time.

## Eval harness (`src/palio_bot/eval/`)

- `runner.py` — loads a scenario folder, seeds `data/` (wiped + repopulated per
  step), drives `System.send_message()` through each prompt, diffs the final
  files against expected, and optionally calls the LLM judge.
- `judge.py` — OpenRouter call that rates `passed_criteria` / `failed_criteria`
  against a rubric.
- `recorder.py` — subscribes to the event stream per step.
- `patch.py` — applies JSONPath patches to compute expected state.
- Scenarios live in `tests/scenarios/<name>/` with `scenario.json` + `seeds/`.

## File structure

```
src/palio_bot/
├── __main__.py                    # CLI entry
├── config.py                      # Pydantic Settings
├── container.py                   # DI
├── system.py                      # Session coordinator
├── file_manager.py                # Temp-file lifecycle
├── leaderboard_updater.py         # Leaderboard recompute on commit
├── agent/
│   ├── agent.py, models.py, system_prompt.py
├── llm_clients/
│   ├── base_client.py, chat_client.py, ollama_client.py
├── tools/
│   ├── file_registry.py, multi_json_editor_tool.py
├── stream/
│   ├── stream.py, events.py, interfaces.py
├── models/                        # Pydantic validators for registered files
│   ├── palio_models.py, game_status_models.py, leaderboard_models.py, helpers.py
├── cli/
│   ├── cli.py, cli_consumer.py
├── telegram_bot/
│   ├── telegram_bot.py, telegram_consumer.py
├── api/
│   └── api_server.py              # FastAPI + static React + WebSocket
├── eval/
│   ├── runner.py, judge.py, recorder.py, patch.py, __main__.py
├── services/
│   └── audio_transcription.py     # Whisper via Groq
└── utils/
    └── api_logger.py

data/                              # Runtime state (mostly gitignored)
├── palio.json
├── palio_games_status.json, palio_games_status_tmp.json
├── leaderboard.json, leaderboard_tmp.json
├── session.json
└── <year>/…                       # archived years served by /api/*/{year}

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
- `session.json`, `*_tmp.json`, and `*.backup_*.json` are gitignored; don't
  commit them.
- CORS for the API server is restricted to localhost dev ports; override via
  `CORS_ALLOWED_ORIGINS=...` (comma-separated).
- Year-scoped API routes (`/api/palio/{year}`, etc.) are bounded `1900..2100`.
