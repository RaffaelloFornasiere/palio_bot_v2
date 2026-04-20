# Bugs & Error Handling

## Bugs

- **`cli/cli.py:117`** — references `config.leader_board_file_path`; the attribute in `config.py:37` is `leaderboard_file_path` (no extra underscore). Will `AttributeError` when hit.
- **`models/game_status_models.py:35`** — `Field(default=[], ...)` uses a mutable list default. Use `default_factory=list`.
- **`models/game_status_models.py:73`** — field typed `Optional[List[GameRound]]` but declared `default_factory=dict`. Wrong default type.
- **`models/helpers.py:1`** — wildcard import with bad form: `from game_status_models import *` (not relative). Breaks when package is installed; relies on sys.path shape. Also makes `Union`/typing symbols implicit.
- **`telegram_bot/telegram_bot.py:23`** — `config: Optional[Config] = Config()` — default arg constructs a shared `Config` at import time. Switch to `None` and construct inside.
- **`llm_clients/chat_client.py:152-165`** — inner `if context:` block is nested inside an outer one with the same condition; inner branch is unreachable or dead.
- **`llm_clients/chat_client.py:250-269`** — JSON parse wrapped in bare `except json.JSONDecodeError: pass`; malformed content silently becomes empty `TextContent`. At minimum log a warning.
- **`eval/judge.py:138-149`** — assumes `r.json()["choices"][0]["message"]` structure and assumes `verdict` is a dict. Any missing key → outer `except` returns `passed=False`, hiding the real cause. Also `list(verdict.get("failed_criteria") or [])` will `TypeError` if the key is a string.
- **`eval/runner.py` (`_write_seed`, ~L34-54)** — deletes every file in `data_dir` before writing seeds. If `data_dir` is ever misrouted (config bug, relative path), this nukes real data. Add assertion that `data_dir` is under the temp root.
- **`tools/multi_json_editor_tool.py`** — all user-facing error messages are in Italian mixed with code. Harmless functionally but unsearchable and blocks any i18n; more importantly it couples language to logic.

## Broad/swallowed exceptions

- **`system.py:163-179`** — `except Exception` around session handling re-raises but logs without distinguishing error class; makes triage harder.
- **`utils/api_logger.py` (error path)** — logs full exception `__dict__`, which for some HTTP client errors contains request headers incl. `Authorization`. Redact or log only `type(e).__name__` + message.
- **`eval/runner.py` teardown (~L128-138)** — `except Exception: pass` silently hides teardown failures. At least `logger.exception`.
- **`leaderboard_updater.py` (multiple)** — several `except Exception as e: logger.error(...); raise` blocks add no information beyond the original traceback. Either catch specific types or drop the wrapper.
