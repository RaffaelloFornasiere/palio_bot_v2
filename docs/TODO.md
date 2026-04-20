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

---

## 2. API server `--reload` in dev

Current launch (`uv run python -m palio_bot.api.api_server`) doesn't hot-reload, so iterating on backend code needs manual restart. Consider:

- Separate `api.__main__` with `uvicorn.run(..., reload=True)` when `PALIO_DEV=1`.
- Or add a `scripts/dev_api.sh` that runs `uvicorn palio_bot.api.api_server:app --reload --port 8000`.

---

## 3. CRA port note in docs / tmux

The website runs on `:3010` (set in `website/.env` via `PORT=3010`), not the CRA default `:3000`. The `scripts/run_tmux.sh` header comment still says `:3000` — update when revisiting.

---

## 4. Stale `REACT_APP_SERVER_URL` in `website/.env`

Was hardcoded to `http://192.168.1.128:8000`. Commented out for now so it falls back to `localhost:8000`. If you need a LAN-visible deployment, set this to the machine's current IP or a stable hostname — don't re-hardcode an ephemeral IP.

---

## 5. Deferred from refactor plan

The following were explicitly deferred:

- **Delete custom `Message`/`Content` abstraction** — touches 10+ files for ~350 LOC savings. Type safety it provides (agent loop, event payloads, session persistence) outweighs the ~40-line conversion cost in `LlamaCPPClient`. Revisit only if we add more providers or the abstraction starts leaking.
- **Streaming LLM responses** — agent currently waits for the full response before yielding.
- **Multi-level undo** — currently 1-level per file.
- **Retry logic for transient LLM failures** — no retry on httpx errors.
- **sage_v2's stricter stream features** (tick batching, `on_put_event`, bounded queue, consumer lock) — our stream is fine at current scale; revisit if we see memory growth or racing consumers.
- **Trio migration** — blocked by `python-telegram-bot` being asyncio-only.
- **Domain-specific tools** (`record_match_result` etc.) — revisit only if the generic JSON editor proves unreliable in practice.

---

## 6. Known minor issues

- `PydanticDeprecatedSince20` warning from `Tool.Config` class in `agent/models.py` — should migrate to `model_config = ConfigDict(...)`.
- `src/palio_bot/telegram_bot/__init__.py` was missing and had to be added during the src-layout move — harmless, just noting.
- `container.py` still has an unused `Literal` import.
