# Tests & Eval Harness

## Test-suite gaps

- No tests for `src/palio_bot/eval/` — the harness that validates the whole system is itself unvalidated. Priority targets:
  - `judge.py`: malformed JSON response, missing `choices[0].message`, `failed_criteria` is a string instead of a list, HTTP 4xx/5xx.
  - `patch.py`: empty patch, conflicting patch, missing target path.
  - `runner.py`: `_write_seed` boundary (reject paths outside tmp root), teardown after forced cancellation, scenario with no judge step.
  - `recorder.py`: event received after `complete` fires, cancellation mid-step.
- No tests for `api/api_server.py` — year path handling, WebSocket disconnect, error responses.
- No tests for `telegram_bot/` — at least mock the bot and exercise authorization + cancel.
- No tests for `leaderboard_updater.py` computation paths. This is pure logic and should be trivial to cover; currently a liability.

## Existing tests

- `tests/scenarios/` is the eval harness input, not unit tests.
- Staged deletion of `04_scatolone_rounds/seeds/*.json` removes the inputs for the only "rounds" scenario (see 05). If intentional, also remove scenario.json; if not, restore.
- `tests/conftest.py` — review fixture scopes; any `session`-scoped fixture writing to `data/` leaks state between tests.

## Eval harness behavioural issues

- **Judge reliability**: any transient 429/5xx from OpenRouter currently returns `passed=False` — a flaky run is indistinguishable from a real regression. Add retries (2-3 with backoff), and emit a distinct "judge_error" verdict so CI can tell the difference.
- **Determinism**: judge model is pinned but prompt is rebuilt each run; if the criteria JSON changes, old runs can't be re-scored. Snapshot the judge prompt alongside the recorded trace.
- **Timeouts**: 5 s event wait (see 02) is too short for real LLMs; make it scenario-configurable.
- **Scoring signal**: `failed_criteria` coercion silently drops non-list shapes. Log a warning when the judge returns an unexpected schema.
- **Artifacts**: `results/` should include the exact scenario + seed hash + model version for reproducibility. Unclear whether it currently does.
