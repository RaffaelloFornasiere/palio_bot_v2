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
