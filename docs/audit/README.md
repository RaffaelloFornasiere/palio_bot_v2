# Repo Audit — 2026-04-20

Scope: Python source under `src/palio_bot/`, tests, scripts, docker, top-level docs. Frontend only skimmed.

## Index

- [01-bugs.md](01-bugs.md) — logic bugs and error-handling defects
- [02-resources-async.md](02-resources-async.md) — leaks, fire-and-forget tasks, cleanup races
- [03-security.md](03-security.md) — auth, CORS, input validation, key handling
- [04-organization.md](04-organization.md) — dead code, duplication, tangled responsibilities
- [05-repo-hygiene.md](05-repo-hygiene.md) — stale docs, committed temp files, gitignore gaps
- [06-tests-eval.md](06-tests-eval.md) — test coverage gaps and eval-harness issues

## Verified quick wins (do first)
1. Stop tracking `data/*_tmp.json` and `data/*.backup_*.json` (see 05).
2. Delete empty dir `src/palio_bot/tools/core/`.
3. Fix typo `config.leader_board_file_path` in `cli/cli.py` (see 01).
4. Restrict CORS `allow_origins=["*"]` in `api/api_server.py:28`.
5. Archive/delete the 6 obsolete planning `.md` files at repo root (see 05).
