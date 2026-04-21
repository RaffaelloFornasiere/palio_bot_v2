"""Phase 2f tests for /admin/reset.

Drops active sessions + their locks, optionally replaces canonical files
with a scenario seed directory.
"""

import json
from pathlib import Path

from tests.core.conftest import LEADERBOARD_SEED, GAMES_STATUS_SEED


def _create_session(client, label: str = "cli") -> str:
    return client.post("/api/sessions", json={"label": label}).json()["id"]


def test_reset_drops_all_sessions_and_locks(core_client):
    s1 = _create_session(core_client)
    s2 = _create_session(core_client)
    core_client.post(f"/api/sessions/{s1}/acquire/leaderboard")
    core_client.post(f"/api/sessions/{s2}/acquire/palio_games_status")

    res = core_client.post("/admin/reset", json={})
    assert res.status_code == 200
    assert core_client.get("/api/sessions").json()["sessions"] == []

    # A fresh session can now acquire both files.
    fresh = _create_session(core_client)
    assert core_client.post(f"/api/sessions/{fresh}/acquire/leaderboard").status_code == 200
    assert (
        core_client.post(f"/api/sessions/{fresh}/acquire/palio_games_status").status_code
        == 200
    )


def test_reset_replaces_canonical_from_seeds(core_client, core_data_dir, tmp_path):
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    replacement = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 100, "position": 1},
            "salt": {"points": 50, "position": 2},
        },
    }
    (seeds / "leaderboard.json").write_text(json.dumps(replacement))

    res = core_client.post("/admin/reset", json={"seeds_dir": str(seeds)})
    assert res.status_code == 200

    on_disk = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert on_disk["palio_leaderboard"]["villa"]["points"] == 100


def test_reset_removes_canonical_when_no_seed_provided(core_client, core_data_dir, tmp_path):
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    # Only seed leaderboard — palio_games_status + palio should be removed.
    (seeds / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED))

    res = core_client.post("/admin/reset", json={"seeds_dir": str(seeds)})
    assert res.status_code == 200

    assert (core_data_dir / "leaderboard.json").exists()
    assert not (core_data_dir / "palio_games_status.json").exists()
    assert not (core_data_dir / "palio.json").exists()


def test_reset_missing_seeds_dir_returns_400(core_client):
    res = core_client.post("/admin/reset", json={"seeds_dir": "/no/such/path"})
    assert res.status_code == 400
