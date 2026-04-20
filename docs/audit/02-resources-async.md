# Resource Leaks & Async Correctness

## Fire-and-forget tasks

- **`telegram_bot/telegram_bot.py:~480, 484`** — `asyncio.create_task(...)` with no reference stored. Task can be GC'd mid-flight; any exception is silently dropped. Either `await` or keep the reference in `self.running_tasks` and discard on completion.
- **`telegram_bot/telegram_bot.py:~321-327`** — cancel-then-await pattern catches `CancelledError` with bare `pass`, no cleanup and no logging. If the task owns resources, they leak.

## Stream / background loops

- **`stream/stream.py:~50-53`** — `start_processing()` checks `_processing_task is None or .done()` without a lock; two concurrent callers can spawn two processors. Trivial race but real.
- **`stream/stream.py` shutdown** — sentinel-based stop in `stop_processing()` has no timeout/`wait_for`. If a consumer hangs, shutdown hangs forever.

## Eval harness

- **`eval/runner.py` teardown** — doesn't `await` the stream-processing task after `stop_processing()`. Background task may outlive the scenario.
- **`eval/runner.py:~179`** — `asyncio.wait_for(recorder.complete.wait(), timeout=5.0)` — 5 s is too aggressive for real LLM runs. Make it per-scenario configurable, default much higher.
- **`eval/recorder.py:~28-75`** — single `asyncio.Event` reused across steps via `reset_step()`. If a prior step's producer is still draining, `clear()` on the shared event creates ordering hazards. A fresh recorder per step is safer.
- **`eval/runner.py:~250`** — `shutil.rmtree(tmp_root, ignore_errors=True)` in `finally` hides leaks. Log, don't silence.

## File handles

- **`leaderboard_updater.py`** — inconsistent use of `open()` vs. `with open()` across the file. Audit every `open(` call here and convert all to context managers.

## HTTP clients

- **`llm_clients/*`, `eval/judge.py`** — check whether the HTTP client (httpx/requests) is instantiated per call vs. reused. If per-call with `requests`, each call leaves a connection in TIME_WAIT under load. Prefer a module-level client closed at shutdown. (Not fully verified — worth a pass.)
