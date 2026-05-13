"""Tests for the leaderboard apply / commit-with-leaderboard flows.

Verifies the fix for the bug where leaderboard apply bypassed the git
history layer: both standalone `/api/leaderboard/apply` and the bundled
form `POST /api/sessions/{id}/commit` with a `leaderboard` payload must
advance `refs/palio/last_save` so the public webapp sees the new values.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from palio_bot.core.app import create_app
from palio_bot.core.config import CoreConfig

from tests.core.conftest import GAMES_STATUS_SEED, LEADERBOARD_SEED, PALIO_SEED


@pytest.fixture
def split_clients(tmp_path: Path):
    """Authed + anonymous TestClients sharing a single app."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "palio.json").write_text(json.dumps(PALIO_SEED))
    (data / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED))
    (data / "palio_games_status.json").write_text(json.dumps(GAMES_STATUS_SEED))
    cfg = CoreConfig(
        palio_file_path=data / "palio.json",
        palio_games_status_path=data / "palio_games_status.json",
        leaderboard_file_path=data / "leaderboard.json",
        data_dir=data,
        firebase_config_path=tmp_path / "no_firebase.json",
        bearer_token="test-token",
    )
    app = create_app(cfg)
    with TestClient(app) as _:
        authed = TestClient(app, headers={"Authorization": "Bearer test-token"})
        public = TestClient(app)
        yield authed, public, data


def _proposed_leaderboard(points: int) -> dict:
    return {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": points, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }


# ---------- standalone /api/leaderboard/apply ----------


def test_apply_advances_last_save_for_public_read(split_clients):
    """The standalone apply path (Telegram `/leaderboard`, CLI) must
    commit through history so the public webapp sees the new values."""
    authed, public, _ = split_clients
    proposed = _proposed_leaderboard(99)

    res = authed.post("/api/leaderboard/apply", json={"proposed": proposed})
    assert res.status_code == 200, res.text

    # Public read goes through last_save → must reflect the apply.
    public_view = public.get("/api/files/leaderboard").json()
    assert public_view["palio_leaderboard"]["villa"]["points"] == 99


def test_apply_rejects_invalid_payload(split_clients):
    authed, _, _ = split_clients
    res = authed.post("/api/leaderboard/apply", json={"proposed": {"garbage": True}})
    assert res.status_code == 422


# ---------- bundled commit with leaderboard ----------


def test_commit_with_leaderboard_squashes_both_into_last_save(split_clients):
    """When the editor saves palio_games_status AND opts in to the
    recompute, commit() must write the leaderboard before finalize_save
    so the squashed commit moves last_save past BOTH files at once."""
    authed, public, _ = split_clients
    sid = authed.post("/api/sessions", json={"label": "webapp"}).json()["id"]

    new_status = {
        **GAMES_STATUS_SEED,
        "game_scores": {"G01": {"status": "in_progress", "divisions": []}},
    }
    put_res = authed.put(
        f"/api/sessions/{sid}/files/palio_games_status",
        json={"content": new_status},
    )
    assert put_res.status_code == 200, put_res.text

    proposed = _proposed_leaderboard(123)
    commit_res = authed.post(
        f"/api/sessions/{sid}/commit",
        json={"leaderboard": proposed},
    )
    assert commit_res.status_code == 200, commit_res.text
    body = commit_res.json()
    assert "palio_games_status" in body["files"]
    assert "leaderboard" in body["files"]

    # Public read (last_save) must see the new leaderboard…
    public_lb = public.get("/api/files/leaderboard").json()
    assert public_lb["palio_leaderboard"]["villa"]["points"] == 123
    # …and the new games status.
    public_status = public.get("/api/files/palio_games_status").json()
    assert "G01" in public_status["game_scores"]


def test_commit_without_leaderboard_is_unchanged(split_clients):
    """Backwards-compat: commit() with no body (or no leaderboard key)
    still works and only touches the session's dirty files."""
    authed, public, _ = split_clients
    sid = authed.post("/api/sessions", json={"label": "cli"}).json()["id"]
    authed.post(f"/api/sessions/{sid}/acquire/leaderboard")
    new_lb = _proposed_leaderboard(7)
    authed.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": new_lb},
    )

    commit_res = authed.post(f"/api/sessions/{sid}/commit")
    assert commit_res.status_code == 200
    assert public.get("/api/files/leaderboard").json()[
        "palio_leaderboard"]["villa"]["points"] == 7


def test_commit_rejects_invalid_leaderboard(split_clients):
    authed, _, _ = split_clients
    sid = authed.post("/api/sessions", json={"label": "webapp"}).json()["id"]
    res = authed.post(
        f"/api/sessions/{sid}/commit",
        json={"leaderboard": {"not": "valid"}},
    )
    assert res.status_code == 422
