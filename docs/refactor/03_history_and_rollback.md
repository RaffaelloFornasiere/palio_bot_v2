# History & Rollback — Git-backed `data/`

## How it works

`data/` becomes a git repo. **Every write commits, every save squashes
the session and moves a mutable ref; one immutable tag per festival
day.** No more in-memory staging in core — the working tree is the
canonical state.

### Layout

```
data/
├── .git/              # new
├── .gitignore         # ignore session.json, *.backup_*, archived years
├── palio.json
├── palio_games_status.json
├── leaderboard.json
└── session.json       # ignored
```

`.gitignore`:
```
session.json
*.backup_*.json
/[0-9][0-9][0-9][0-9]/
```

### Write path (any source: agent tool, webapp edit, CLI)

1. Acquire file lock (`lock_manager`, unchanged).
2. Atomic write to disk (`os.replace`, unchanged).
3. `git add <file> && git commit -m "<source>:<session_id_short> <summary>"`.
4. Release lock.
5. Emit `FileChangedEvent`.

Summary is mechanical: diff before/after, format first 1–3 changed
JSONPaths as `set X to V` / `add X` / `remove X`.

### Save = squash + move `last_save` ref (+ maybe a daily tag)

On `SessionService.commit` (i.e. `/close`, webapp Save, CLI `/save`):

1. Recompute leaderboard if `palio_games_status.json` was touched in this
   session, write the new file (which produces one more per-write commit).
2. **Squash all session commits into one**: `git reset --soft <last_save>`
   then a single `git commit -m "<aggregated summary>"`. The aggregated
   summary lists the top-level changed paths across the session.
3. Move the mutable ref `refs/palio/last_save` to the new HEAD. This ref
   is what the public webapp reads.
4. **Lazy daily tag**: before moving `last_save`, check the committer
   date of its previous value. If `festival_day(prev_last_save) !=
   festival_day(now)`, create `tag <YYYY-MM-DD>` on the previous
   `last_save` SHA, where `festival_day(ts)` = `(ts - 5h)` truncated to
   calendar date in `Europe/Rome`. The 05:00 cutoff means activity up
   to 04:59 stays in yesterday's festival day.
5. Emit `SessionCommittedEvent`.

No scheduler. The daily tag materialises naturally at the first save of
a new festival day. If a day has no saves, no tag is created (nothing
to mark).

The reflog still contains the per-tool-call commits for a while
(`git reflog` default expiry is 90 days), so they remain accessible for
debugging even after the squash.

### Read paths

| Reader              | Source                          |
|---------------------|---------------------------------|
| Edit webapp (auth)  | working tree (HEAD)             |
| Public webapp       | `refs/palio/last_save`          |
| Agent (read tools)  | working tree (HEAD)             |
| CLI                 | working tree (HEAD)             |

Public reads use `git show last_save:<file>` via `pygit2` or subprocess,
cached in-memory keyed by `last_save` SHA (invalidated when the ref
moves).

### `/cancel`

`git checkout last_save -- <files-touched-by-session>` + a single
commit `cancel session <id>`. Files the session never touched are
untouched. Deterministic, no LLM.

A new session needs to know "files touched" — tracked in the existing
`_dirty[session_id]` set, which now persists not as staged content but
as a plain set of file names.

### Agent rollback tools

`json_undo` and `_last_content` are removed. Two new tools:

```
json_history(file_name, limit=10) -> ToolResult
# Numbered list, 1 = most recent. Scope: commits between `last_save`
# and HEAD, i.e. within the current session only. Format:
#   1 (most recent) — set palio_games_status[...].status to "completed"   [30s ago]
#   2              — set leaderboard.divisions[...].Villa to 52           [1m ago]
# If no commits since `last_save`: returns
#   "Nessuna modifica da annullare nella sessione corrente."

json_revert(file_name, n_steps) -> ToolResult
# Reverts the last `n_steps` commits of `file_name` within the current
# session. Refuses to cross the `last_save` boundary.
# Implementation: pick the Nth commit back (only those touching file_name),
# `git checkout <that_commit>^ -- <file_name>`, commit "revert N step(s)".
# Returns the resulting diff summary.
```

Hard scope: **agent can only see/revert within its own session**
(commits between `last_save` and HEAD). Anything past `last_save` is
reachable only via the manual webapp rollback UI.

### Manual rollback (edit webapp)

New router `core/routes/history.py`:

- `GET  /api/history/{file}?limit=N` → two-tier list:
  1. **Daily tags** touching `file` (festival-day checkpoints), newest
     first, with timestamp and tag name.
  2. **Saves within today's festival day** (commits between yesterday's
     tag and `last_save` that touched `file`), if any.
- `GET  /api/history/{file}/diff?ref=<tag-or-sha>` → unified diff vs
  current.
- `POST /api/history/{file}/rollback` body `{ref}` → `git checkout
  <ref> -- <file>` + commit `rollback <file> to <ref>`. The rollback
  itself is a normal commit, so it can be undone too.

The edit webapp shows a History panel per file driven by these endpoints.
The public webapp doesn't get any UI for this.

## What changes

### New files

- `src/palio_bot/core/history.py`
  - `HistoryService`: `init_repo()`, `record_write(file, source, committer, tool, summary)`,
    `finalise_save(session_id, dirty_files) -> SquashResult`,
    `list_session_commits(file, limit)`, `list_history(file, limit)`
    (returns daily tags + intra-day saves), `revert_steps(file, n_steps)`,
    `rollback_to_ref(file, ref)`, `read_at_ref(file, ref)`. All
    mutating operations acquire a single `asyncio.Lock` (`_repo_lock`)
    that serialises git plumbing regardless of which file-level lock
    is held.
- `src/palio_bot/core/routes/history.py` — the 3 endpoints above.
- `data/.gitignore`.
- `tests/scenarios/11_history_rollback/` — multi-step revert eval.

### Modified

- `src/palio_bot/core/file_store_local.py::write_atomic` — after `os.replace`,
  call `HistoryService.record_write`.
- `src/palio_bot/core/session_service.py`
  - `acquire`: no longer copies canonical into staged; just records the
    file in `_dirty`.
  - `stage` (PUT staged content): becomes `write` — calls
    `file_store.write_atomic` directly (no separate staging buffer).
  - `commit`: drops the "write_atomic loop" (already done per-call);
    runs leaderboard recompute if needed, calls `HistoryService.tag_save`.
  - `discard`: calls `HistoryService.revert_session(session_id, files)`
    instead of dropping in-memory state.
- `src/palio_bot/core/session_store.py` — `staged` field removed, only
  `dirty_files: set[str]` remains.
- `src/palio_bot/core/routes/files.py` — public read route switches to
  `HistoryService.read_at_ref(file, "refs/palio/last_save")`. Edit/auth
  read route keeps reading the working tree.
- `src/palio_bot/core/app.py` — register history router, init repo at
  startup.
- `src/palio_bot/tools/multi_json_editor_tool.py` — remove
  `_last_content`, remove `json_undo`, add `json_history` and
  `json_revert` wired to new core endpoints (via `CoreClient`).
- `src/palio_bot/core_client/client.py` — add `history(file)`,
  `revert(file, n_steps)`.
- `src/palio_bot/agent/system_prompt.py` — document the two tools.
- `website/` — History panel in the edit UI; public site needs to switch
  its data source to the tag-scoped endpoint.
- `CLAUDE.md` — note the git history layer, the read-path split
  between public (`last_save`) and edit (HEAD), and the festival-day
  cutoff (05:00 Europe/Rome).

## Commit message format

Header is the one-line semantic summary surfaced by `json_history`:
```
set palio_games_status[G02].divisions.masculine.results.Villa to 52
```

Body uses git trailers (`Key: value`, parsable with `git interpret-trailers`):
- `source: agent|webapp|cli` — required.
- `committer: <id>` — Telegram user id/username for the bot,
  authenticated user for the webapp, OS user for CLI. Lets `git log
  --grep="committer: alice"` work for accountability.
- `tool: json_set|json_append_array|...|manual` — tool name (or
  `manual` for webapp direct edits).

Git itself is the committer identity (`palio-core <noreply@palio>`);
human identity lives in the `committer:` trailer.

## Concurrency

Two scopes, both needed:

- **Per-file lock** (`lock_manager`, existing): prevents two sessions
  from acquiring the same file. Application-level state correctness.
- **Repo-level mutex** (`HistoryService._repo_lock`, new): a single
  `asyncio.Lock` serialises *all* git operations against the data repo.
  Needed because `.git/index` and refs are global to the repo and not
  safe for concurrent writers within a single process. Cheap (one
  await), and gives a free defensive boundary against any future code
  path that bypasses the per-file lock.

## Stale-session UX (separate)

When a session has been idle for a long time, or when another save lands
in a file that the open session has touched, prompt the user via the WS
event bus to either close or discard. This is an application-level
concern handled by adapters (`telegram_bot`, `cli`, webapp). The
history layer itself doesn't drive these prompts.

## Open questions / follow-ups

- **Drop `base_versions`?** It is core's optimistic-concurrency check:
  on `acquire` it records the canonical file hash; on `commit` it
  re-reads and rejects if the hash changed. With per-write commits the
  staging window goes away and the lock manager + repo-level mutex
  already prevent the conflict — recommend removing it.
- **`git gc` cadence.** App runs ~2 weeks/year. Auto-gc default
  threshold (6700 loose objects) won't trigger naturally. Add a single
  `git gc --auto` call at core startup so loose objects get packed
  occasionally. Functionally optional — disk impact is negligible.
- **Session persistence (separate feature, not part of this refactor).**
  Sessions today are lost after `/close`. Worth persisting the full
  transcript (user messages, agent updates, tool calls + results,
  errors) to disk for eval scenario seeding and training datasets.
  Tracked in `docs/TODO.md §3`. When it exists, this layer can add
  `session: <id>` to the commit trailer as a back-reference.
