# Repo Hygiene

## Tracked files that shouldn't be in git

Verified via `git ls-files`:

- `data/leaderboard_tmp.json`
- `data/leaderboard.backup_20260419_161258.json`
- `data/palio_games_status.backup_20260419_161258.json`
- `data/2024/palio_games_status.backup_20260419_190644.json`

`.gitignore` already lists `session.json`, `palio_games_status_tmp.json`, `backups/`, `.env`, but misses:

- `data/**/*.backup_*.json`
- `data/**/*_tmp.json`
- `results/` (eval output — check whether outputs are being tracked)
- `logs/`
- `.pytest_cache/`
- `.DS_Store` (lives in `src/palio_bot/.DS_Store` and `src/palio_bot/__pycache__/` area — confirm untracked)

Action: `git rm --cached` the four files above, then expand `.gitignore`.

## Stale top-level documentation

These planning docs pre-date current code and contradict it:

- `EVAL_PLAN.md` — eval harness now exists under `src/palio_bot/eval/`.
- `REFACTOR_PLAN.md` — branch is already `refactor`; unclear what's live.
- `MULTI_FILE_IMPLEMENTATION.md` — describes an abandoned naming scheme (see 04).
- `detailed_implementation_analysis.md` — stale snapshot.
- `leaderboard_editing_plan.md` — no matching code.
- `TODO.md` — verify freshness; if live, fine.

Recommendation: `docs/archive/` or delete. Keep only README + CLAUDE.md at root (and update CLAUDE.md — currently wrong, see 04).

## IDE / build artifacts

- `.idea/` is tracked? check; should be gitignored.
- `.DS_Store` files exist under `src/`. Add `**/.DS_Store` to ignore if not already.
- `uv.lock` is tracked (correct).

## Uncommitted state at audit time

Working tree has:
- modified `eval/recorder.py`, `eval/runner.py`, `tests/scenarios/01_simple_reads/scenario.json`
- staged deletions of `tests/scenarios/04_scatolone_rounds/seeds/*.json`
- new untracked `eval/judge.py`

Verify the seed deletions are intentional before committing — scenario 04 was the "rounds" scenario per CLAUDE.md and losing its seeds silently breaks that test.
