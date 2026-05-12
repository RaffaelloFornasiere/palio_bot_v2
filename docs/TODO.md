# TODO — Outstanding Fixes

Tracks changes discovered during the refactor that are not yet addressed.

## 1. Reorganize `data/` by year (including current)

**Current state:**
```
data/
├── 2024/                              # archived year
│   ├── palio.json
│   ├── leaderboard.json
│   └── palio_games_status.json
├── palio.json                         # current year at root
├── leaderboard.json
├── palio_games_status.json
├── *_tmp.json                         # session temp files
└── session.json
```

**Target state:**
```
data/
├── 2024/
│   ├── palio.json
│   ├── leaderboard.json
│   └── palio_games_status.json
├── 2025/                              # current year also lives here
│   ├── palio.json
│   ├── leaderboard.json
│   ├── palio_games_status.json
│   └── *_tmp.json                     # temps scoped to the year
└── session.json                        # global; ok at root
```

**What changes:**
- **File layout:** move root `palio.json` / `leaderboard.json` / `palio_games_status.json` into `data/<current_year>/`.
- **Config:** `Config` paths become year-aware. Introduce `current_year: int` (auto-detected as max of `int(name)` folders under `data/` at startup, overridable via env). Paths become `data/{current_year}/palio.json` etc.
- **API:**
  - `/api/years` scans for all year dirs (unchanged logic, but current year now appears).
  - `/api/palio`, `/api/leaderboard`, `/api/palio_games_status` resolve to the latest year by default.
  - `/api/palio/{year}` keeps working for explicit years.
  - Consider deprecating the bare endpoints and requiring `{year}` everywhere — cleaner but a breaking change for the frontend.
- **Frontend:** the `YearContext` / `YearSelector` in `website/src/contexts/` and `website/src/components/` should default to the latest year from `/api/years` rather than assuming "current = root". Check that calling `/api/palio/{latest}` works after the move.
- **FileManager:** should resolve temp paths inside the current-year dir.
- **Scripts:** `scripts/restore_games_status.py` and `scripts/restore.sh` reference root paths — need updating.

**Migration:**
1. Create `data/2026/` (or whichever is current).
2. Move root `palio.json` + `leaderboard.json` + `palio_games_status.json` into it.
3. Remove root `*_tmp.json` files (they'll be recreated under the year dir).
4. Adjust `Config` and `FileRegistry` registration in `container.py`.
5. Run tests; smoke-test CLI end-to-end (open session → edit → close → confirm commits inside `data/<year>/`).

**Default-year rule:** latest is `max(int(name) for name in data/* if name.isdigit())`. If `data/` contains no year dirs, fail fast with a clear error.

## 2. Rename `MultiJSONEditorTool`

The name suggests "a tool that edits multiple JSON files at once." It actually does the opposite: one tool instance exposes a single editor that targets *one of several registered files* per call (via a `file_name` argument). The "multi" refers to the registry it can reach, not to the edit scope.

**Rename candidates:**
- `RegisteredFileEditor` (preferred — names what it actually is: an editor over the `FileRegistry`)
- `JSONFileEditor`
- `RegistryJSONEditor`

**Scope:** rename the class, the module (`tools/multi_json_editor_tool.py`), all imports, and any prompt/docstring references. Check `agent/system_prompt.py` and eval scenarios for hardcoded tool-name strings before renaming — tool names are surfaced to the LLM.

## 3. Persist sessions to disk

Today `/close` ends the session and the transcript is gone. Persist each session as a self-contained record so it can be replayed for evals and used as training data.

**What to capture per session:**
- session id, start/end timestamps, source (cli/telegram/webapp), committer (telegram user / auth user / os user), model used.
- ordered turn log: user message → agent updates → tool calls (name + args) → tool results → final agent message.
- final outcome: committed (with tag name) / cancelled.
- pointer to the git commit/tag that materialised the save, if any.

**Layout suggestion:**
```
data/sessions/<YYYY-MM-DD>/<session_id>.json
```
Gitignored from the `data/` history repo (would create noise) but kept on disk; separate periodic export to an eval/training bucket if needed.

**Useful for:** seeding eval scenarios from real interactions, fine-tuning datasets, debugging "why did the agent do X" after the fact. Once this exists, the history layer (see `docs/refactor/03_history_and_rollback.md`) can add `session: <id>` to commit trailers as a back-reference.
