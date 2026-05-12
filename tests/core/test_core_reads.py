"""Phase 1 parity checks for core read endpoints.

Every GET returns exactly what Pydantic.model_validate(raw_json).model_dump()
would produce — same behavior as today's api_server for the three file
shapes. Year-scoped reads + the /api/years archive listing are also covered.
"""

import json
from pathlib import Path

from palio_bot.models.game_status_models import PalioGamesStatus
from palio_bot.models.leaderboard_models import Leaderboard
from palio_bot.models.palio_models import PalioData


def _expected(path: Path, validator) -> dict:
    return validator.model_validate(json.loads(path.read_text())).model_dump()


def test_get_palio_returns_validated_payload(core_client, core_data_dir):
    res = core_client.get("/api/files/palio")
    assert res.status_code == 200
    assert res.json() == _expected(core_data_dir / "palio.json", PalioData)


def test_get_leaderboard_returns_validated_payload(core_client, core_data_dir):
    res = core_client.get("/api/files/leaderboard")
    assert res.status_code == 200
    assert res.json() == _expected(core_data_dir / "leaderboard.json", Leaderboard)


def test_get_palio_games_status_returns_validated_payload(core_client, core_data_dir):
    res = core_client.get("/api/files/palio_games_status")
    assert res.status_code == 200
    assert res.json() == _expected(
        core_data_dir / "palio_games_status.json", PalioGamesStatus
    )


def test_unknown_file_returns_404(core_client):
    assert core_client.get("/api/files/nonexistent").status_code == 404


def test_missing_file_returns_404(core_client, core_data_dir):
    (core_data_dir / "leaderboard.json").unlink()
    assert core_client.get("/api/files/leaderboard").status_code == 404


def test_years_empty_when_no_archives(core_client):
    res = core_client.get("/api/years")
    assert res.status_code == 200
    assert res.json() == {"years": []}


def test_years_lists_descending(core_client, core_data_dir):
    from tests.core.conftest import PALIO_SEED

    for year in (2023, 2024):
        ydir = core_data_dir / str(year)
        ydir.mkdir()
        (ydir / "palio.json").write_text(json.dumps(PALIO_SEED))

    res = core_client.get("/api/years")
    assert res.status_code == 200
    assert res.json() == {"years": [2024, 2023]}


def test_get_file_by_year(core_client, core_data_dir):
    from tests.core.conftest import PALIO_SEED, LEADERBOARD_SEED

    ydir = core_data_dir / "2024"
    ydir.mkdir()
    (ydir / "palio.json").write_text(json.dumps(PALIO_SEED))
    (ydir / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED))

    palio_res = core_client.get("/api/files/palio/2024")
    assert palio_res.status_code == 200
    assert palio_res.json()["competition_name"] == "Test Palio"

    lb_res = core_client.get("/api/files/leaderboard/2024")
    assert lb_res.status_code == 200
    assert set(lb_res.json()["palio_leaderboard"].keys()) == {"villa", "salt"}


def test_get_file_by_year_missing_returns_404(core_client):
    assert core_client.get("/api/files/palio/1999").status_code == 404


def test_year_out_of_range_rejected(core_client):
    assert core_client.get("/api/files/palio/1800").status_code == 422
    assert core_client.get("/api/files/palio/2200").status_code == 422


def test_websocket_accepts_connection(core_client):
    with core_client.websocket_connect("/events"):
        pass


# ---------- legacy aliases (React SDK) ----------


def test_legacy_palio_alias(core_client, core_data_dir):
    res = core_client.get("/api/palio")
    assert res.status_code == 200
    assert res.json() == _expected(core_data_dir / "palio.json", PalioData)


def test_legacy_leaderboard_alias(core_client, core_data_dir):
    res = core_client.get("/api/leaderboard")
    assert res.status_code == 200
    assert res.json() == _expected(core_data_dir / "leaderboard.json", Leaderboard)


def test_legacy_games_status_alias(core_client, core_data_dir):
    res = core_client.get("/api/palio_games_status")
    assert res.status_code == 200
    assert res.json() == _expected(
        core_data_dir / "palio_games_status.json", PalioGamesStatus
    )


def test_legacy_year_scoped_alias(core_client, core_data_dir):
    from tests.core.conftest import PALIO_SEED

    ydir = core_data_dir / "2024"
    ydir.mkdir()
    (ydir / "palio.json").write_text(json.dumps(PALIO_SEED))

    res = core_client.get("/api/palio/2024")
    assert res.status_code == 200
    assert res.json()["competition_name"] == "Test Palio"


# ---------- read split: public sees last_save, authed sees working tree ----------
#
# These tests configure a bearer token to exercise the production branch
# where anonymous callers (public webapp) see the saved state and
# authenticated callers (editor webapp) see the live working tree.


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from palio_bot.core.app import create_app  # noqa: E402
from palio_bot.core.config import CoreConfig  # noqa: E402

from tests.core.conftest import LEADERBOARD_SEED  # noqa: E402


@pytest.fixture
def authed_setup(tmp_path: Path):
    """Core with a bearer token configured. Yields (authed_client,
    public_client, data_dir)."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "palio.json").write_text(
        json.dumps({
            "competition_name": "Test Palio",
            "villages": ["villa", "salt"],
            "villages_colors": {"villa": "#ff0000", "salt": "#00ff00"},
            "games": [],
            "non_game_events": [],
        })
    )
    (data / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED))
    (data / "palio_games_status.json").write_text(
        json.dumps({"game_scores": {}, "last_updated": "2026-04-20T00:00:00Z"})
    )
    cfg = CoreConfig(
        palio_file_path=data / "palio.json",
        palio_games_status_path=data / "palio_games_status.json",
        leaderboard_file_path=data / "leaderboard.json",
        data_dir=data,
        firebase_config_path=tmp_path / "no_firebase.json",
        bearer_token="test-token",
    )
    app = create_app(cfg)
    with TestClient(app) as base:
        authed = TestClient(app, headers={"Authorization": "Bearer test-token"})
        public = TestClient(app)  # no Authorization header
        # Use base only to keep TestClient(app) lifecycle parity; not exposed.
        del base
        yield authed, public, data


def test_public_sees_last_save_during_session(authed_setup):
    """While a session has in-flight intra-session writes, public reads
    must keep showing the previously-saved state."""
    authed, public, _ = authed_setup
    sid = authed.post("/api/sessions", json={"label": "cli"}).json()["id"]
    authed.post(f"/api/sessions/{sid}/acquire/leaderboard")
    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 777, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }
    authed.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": new_content, "tool": "json_set"},
    )

    # Authed sees the in-progress (HEAD) state.
    authed_view = authed.get("/api/files/leaderboard").json()
    assert authed_view["palio_leaderboard"]["villa"]["points"] == 777

    # Public still sees the previous save (= seed here).
    public_view = public.get("/api/files/leaderboard").json()
    assert public_view["palio_leaderboard"]["villa"]["points"] == 0

    # After commit, both align.
    authed.post(f"/api/sessions/{sid}/commit")
    assert (
        public.get("/api/files/leaderboard").json()[
            "palio_leaderboard"]["villa"]["points"] == 777
    )


def test_legacy_alias_respects_read_split(authed_setup):
    """The legacy `/api/leaderboard` alias must use the same auth-based
    branch as `/api/files/leaderboard`."""
    authed, public, _ = authed_setup
    sid = authed.post("/api/sessions", json={"label": "cli"}).json()["id"]
    authed.post(f"/api/sessions/{sid}/acquire/leaderboard")
    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 42, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }
    authed.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": new_content, "tool": "json_set"},
    )

    assert authed.get("/api/leaderboard").json()[
        "palio_leaderboard"]["villa"]["points"] == 42
    assert public.get("/api/leaderboard").json()[
        "palio_leaderboard"]["villa"]["points"] == 0


def test_dev_mode_serves_working_tree_to_everyone(core_client, core_data_dir):
    """When neither PALIO_CORE_TOKEN nor FIREBASE_PROJECT_ID is set,
    `is_authenticated` returns True for every request → public reads
    fall back to working tree (= today's pre-refactor behavior)."""
    res = core_client.get("/api/files/leaderboard")
    assert res.status_code == 200
    # Same content as on-disk = no surprise switch in dev.
    on_disk = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert res.json()["palio_leaderboard"] == on_disk["palio_leaderboard"]
