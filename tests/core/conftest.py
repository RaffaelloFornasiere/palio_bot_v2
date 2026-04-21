"""Fixtures for core tests.

The top-level `tmp_data_dir` fixture uses minimal JSON shapes tailored to
the editor tests. Core's read endpoints run full Pydantic validation, so
we seed a separate temp dir with schema-valid payloads.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from palio_bot.core.app import create_app
from palio_bot.core.config import CoreConfig


PALIO_SEED = {
    "competition_name": "Test Palio",
    "villages": ["villa", "salt"],
    "villages_colors": {"villa": "#ff0000", "salt": "#00ff00"},
    "games": [],
    "non_game_events": [],
}

LEADERBOARD_SEED = {
    "villages": ["villa", "salt"],
    "palio_leaderboard": {
        "villa": {"points": 0, "position": 1},
        "salt": {"points": 0, "position": 2},
    },
    "game_leaderboards": {},
}

GAMES_STATUS_SEED = {
    "game_scores": {},
    "last_updated": "2026-04-20T00:00:00Z",
}


@pytest.fixture
def core_data_dir(tmp_path: Path) -> Path:
    """Temp data/ dir seeded with Pydantic-valid JSON for all three files."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "palio.json").write_text(json.dumps(PALIO_SEED, ensure_ascii=False))
    (data / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED, ensure_ascii=False))
    (data / "palio_games_status.json").write_text(
        json.dumps(GAMES_STATUS_SEED, ensure_ascii=False)
    )
    return data


@pytest.fixture
def core_config(core_data_dir: Path) -> CoreConfig:
    return CoreConfig(
        palio_file_path=core_data_dir / "palio.json",
        palio_games_status_path=core_data_dir / "palio_games_status.json",
        leaderboard_file_path=core_data_dir / "leaderboard.json",
        data_dir=core_data_dir,
    )


@pytest.fixture
def core_client(core_config: CoreConfig):
    app = create_app(core_config)
    with TestClient(app) as client:
        yield client
