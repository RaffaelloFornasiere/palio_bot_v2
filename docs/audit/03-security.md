# Security

## Verified

- **`.env` is gitignored and has no commit history** — not leaked via git. Keep it that way.

## Real issues

- **`api/api_server.py:28`** — `allow_origins=["*"]` with `allow_credentials=True`-style setups is dangerous. Restrict to the known frontend origin(s).
- **`api/api_server.py` (year endpoints, ~L133/153/173)** — `DATA_DIR_PATH / str(year) / "palio.json"`. If `year` is a `str` from the path and not constrained, this is a path-traversal vector (`../`, absolute paths). Type it as `int` in the route signature AND add a bounds check (e.g. `1900 ≤ year ≤ 2100`). Also confirm the resolved path is inside `DATA_DIR_PATH` before reading.
- **`api/api_server.py`** — no auth on any endpoint, no rate limiting, no request logging. Fine if strictly local; risky if exposed.
- **WebSocket endpoint** — verify disconnect cleanup: on client disconnect, are subscribers detached from the stream? If not, consumer list grows unbounded.
- **`telegram_bot/telegram_bot.py`** — `ALLOWED_USER_ID` check must be applied *before* any `create_task` spawn; currently authorization + task creation are interleaved (see 02). An unauthorized message should never trigger a scheduled task.
- **`utils/api_logger.py`** — logs full exception state. Possible credential leakage in provider error paths. Redact `Authorization` / `x-api-key` headers and API-key query params before writing.
- **`docker/Dockerfile.api`, `Dockerfile.telegram`** — no `USER` directive; container runs as root. Add a non-root user.
- **`docker/docker-compose.yml`** — verify secrets are injected via env_file/secrets, not baked into images.

## Minor

- **`eval/judge.py:~136`** — on error, echoes `r.text[:300]` into the exception message. That string may contain prompt/response fragments; fine for local dev, careful in any shared log sink.
- **`eval/runner.py:~93`** — `OPENROUTER_API_KEY` read from env per run. No issue, just note it in a SECRETS doc.
