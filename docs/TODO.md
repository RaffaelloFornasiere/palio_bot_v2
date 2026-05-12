# TODO — Outstanding Fixes

Tracks changes discovered during the refactor that are not yet addressed.

## 1. Persist sessions to disk

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
