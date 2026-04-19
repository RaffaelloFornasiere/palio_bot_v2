# Refactor Plan

**Goal:** Move to OpenRouter, fix tool bugs, reduce ~4,370 LOC → ~3,000.

## Scope summary

| Area | Current | Target |
|---|---|---|
| LLM providers | Anthropic + LlamaCPP + Ollama (3 clients, 736 LOC) | OpenAI-compatible client only (OpenRouter, LlamaCPP, Ollama share it) |
| Tools | `json_editor` + `multi_json_editor` + `text_editor` (1,753 LOC) | Single `multi_json_editor` (cleaned) + drop `json_editor` and `text_editor` |
| Multi-file architecture | FileRegistry + copy-on-write temps + atomic commit | **Keep as-is** (solid) |
| Session concept | Transaction boundary for file changes | **Keep as-is** |
| Agent loop | Custom (167 LOC) | **Keep as-is** |
| Event stream | Async queue (214 LOC) | **Keep as-is** |
| Message model | Custom Pydantic abstraction (350 LOC) | Provider SDK types directly |
| Tests | 1 integration script | Pytest for tools + agent loop |

## Decisions (already made)

- **No OpenAI Agents SDK.** Locks to OpenAI ecosystem; defeats OpenRouter flexibility.
- **No RFC 6902 JSON Patch.** Token savings don't justify array-index pitfalls at our file sizes.
- **No `str_replace` / text editor for JSON.** Brittle on repeated values.
- **No domain-only tools.** Flexibility of JSON editor matters. Hybrid stays open as future option.
- **Keep session + multi-file architecture.** Registry + temps + atomic commit is well designed.

## Tool fixes (inside `multi_json_editor_tool.py`)

Actual bugs to fix, not rewrite from scratch:

1. **`set_field` uses manual path parsing** (lines 181–226) — breaks on anything beyond `$.a.b[0]`. Rewrite using `jsonpath_ng` like the other methods.
2. **`delete_field` `clean_arrays` side effect** (lines 288–298) — walks the whole tree pruning `None`s from unrelated arrays. Remove; scope cleanup to the deleted path's parent.
3. **Dead `system=None` param** — delete, unused.
4. **Add `merge(file, path, partial)`** — deep-merge so LLM doesn't need to re-emit unchanged fields on subtree edits.
5. **Add view-before-edit guardrail** — per-session set of viewed paths; writes require an ancestor viewed. Invalidate on write.
6. **Keep `insert_at` / `remove_at`** for now (you may want them; drop only if unused in practice).

Pydantic validation is already wired via `registry.validate_content`. Don't re-add.
Leaderboard recalc is already not coupled inside the editor. Don't re-decouple.

## Execution order

1. **Project scaffolding — uv + src layout.**
   - Create `pyproject.toml` (PEP 621 metadata, dependencies from `requirements.txt`).
   - Move `palio_bot/` → `src/palio_bot/`.
   - Delete `setup.py`, `requirements.txt`, `palio_bot.egg-info/`.
   - `uv lock` → commit `uv.lock`.
   - Update Dockerfiles (`COPY` paths, switch to `uv sync`).
   - Imports already use absolute `palio_bot.*` paths — verify nothing breaks.
   - `python -m palio_bot` entry point still works via editable install.
2. **Tests** — pytest for `multi_json_editor_tool` + `agent.run()` loop. Baseline before touching anything else.
3. **OpenRouter swap** — extend `LlamaCPPClient` with `base_url` + auth header; delete `anthropic_client.py`; update config.
4. **Tool cleanup** — fix the 5 bugs in `multi_json_editor_tool`; delete `json_editor_tool.py` and `text_editor_tool.py` (both superseded).
5. **Delete custom Message model** — migrate agent + client to provider SDK types once on one provider family.
6. **Extract `FileManager`** from `System` — move session/temp/backup plumbing out; `System` keeps conversation + lifecycle.
7. **Config → Pydantic `BaseSettings`** with `Literal` provider enum.

Steps 1–4 are the bulk of the value. Stop and re-evaluate after step 4.

## Out of scope

- Streaming LLM responses.
- Domain-specific tools (`record_match_result` etc.) — revisit if JSON editor proves unreliable.
- Multi-level undo.
- Retry logic for transient LLM failures.
- Trio migration (ecosystem blocker: python-telegram-bot is asyncio-only).
