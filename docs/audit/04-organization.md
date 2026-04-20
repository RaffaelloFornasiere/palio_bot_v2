# Disorganization & Code Quality

## Dead / stray code

- **`src/palio_bot/tools/core/`** — empty directory, no `__init__.py`. Delete.
- **`test_multi_file.py`** and **`example_multi_file_usage.py`** at repo root — ad-hoc experiments, not wired into tests or docs. Move to `scripts/` or delete.
- **`commands.txt`** at repo root — loose scratchpad. Either promote to `Makefile`/`justfile` or remove.
- **`tools/` has both `json_editor_tool.py` references in CLAUDE.md and `multi_json_editor_tool.py` in code** — CLAUDE.md is out of sync with the actual module name.
- **`llm_clients/`** has `chat_client.py` + `ollama_client.py` + `base_client.py`. CLAUDE.md still describes `llamacpp_client.py` + `anthropic_client.py`. Names drifted; doc lies.

## Duplication / tangled responsibilities

- **`system.py` + `container.py` + `file_manager.py`** — session lifecycle, file backup/restore, and DI are smeared across all three. `file_manager` and `system` both reach into the same JSON files; pick one owner.
- **`leaderboard_updater.py`** is ~500 lines doing load + compute + persist + ranking. Split compute from I/O; the compute half becomes unit-testable without touching disk.
- **`multi_json_editor_tool.py`** has implicit coupling to file registry state (`_last_content`, `_viewed_paths`) with no locking and no documented lifecycle. If the tool instance ever outlives a session, state bleeds. If it doesn't, the state is unnecessary.

## Naming / API drift

- Config attribute is `leaderboard_file_path`; at least one caller spells it `leader_board_file_path` (see 01).
- `CLAUDE.md` describes components (LlamaCPP/Anthropic clients, `json_editor_tool`, `palio_updated.json` flow) that no longer match the code. Either rewrite CLAUDE.md now or delete the out-of-date sections — wrong docs are worse than none.

## Error-message style

- **`multi_json_editor_tool.py`** mixes Italian error strings into Python logic. Separate UI text (Italian, ok) from internal log/exception text (English). Makes grep/stack-trace triage much easier.

## Type hints / consistency

- **`leaderboard_updater.py`** — large helpers return `dict` with no `TypedDict`/Pydantic model, yet the codebase already uses Pydantic for similar shapes in `models/`. Convergent style would help.
- **`agent/agent.py`** — tool dispatch catches all exceptions from `tool.function(...)` without checking that the function is callable or that arguments match the declared schema. An invariant check at registration time would catch bad tools earlier.
