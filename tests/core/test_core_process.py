"""Phase 4 smoke test for CoreProcess — the subprocess helper used by
the eval runner."""

import json
from pathlib import Path

import httpx

from palio_bot.core_client.subprocess import CoreProcess

from tests.core.conftest import LEADERBOARD_SEED, GAMES_STATUS_SEED, PALIO_SEED


def test_core_process_boots_and_serves_reads(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "palio.json").write_text(json.dumps(PALIO_SEED))
    (data_dir / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED))
    (data_dir / "palio_games_status.json").write_text(json.dumps(GAMES_STATUS_SEED))

    with CoreProcess(data_dir=data_dir) as core:
        res = httpx.get(f"{core.base_url}/api/files/leaderboard", timeout=2.0)
        assert res.status_code == 200
        assert res.json()["palio_leaderboard"]["villa"]["points"] == 0
