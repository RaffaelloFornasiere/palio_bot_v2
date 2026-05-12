"""Tool parity: same edit sequence against DirectFileStore and
RemoteFileStore must produce byte-identical canonical files.

This is the regression guard for Phase 3 — if the two backends diverge, an
adapter migration in Phase 5/6 would ship subtle bugs.
"""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from palio_bot.core.app import create_app
from palio_bot.core.config import CoreConfig
from palio_bot.core_client.client import CoreClient
from palio_bot.core_client.file_store_remote import RemoteFileStore
from palio_bot.file_store import DirectFileStore
from palio_bot.models.game_status_models import PalioGamesStatus
from palio_bot.models.leaderboard_models import Leaderboard
from palio_bot.models.palio_models import PalioData
from palio_bot.tools.file_registry import FileConfig, FileRegistry
from palio_bot.tools.multi_json_editor_tool import MultiJSONEditorTool

from tests.core.conftest import LEADERBOARD_SEED, GAMES_STATUS_SEED, PALIO_SEED


def _seed_dir(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "palio.json").write_text(json.dumps(PALIO_SEED, ensure_ascii=False))
    (d / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED, ensure_ascii=False))
    (d / "palio_games_status.json").write_text(
        json.dumps(GAMES_STATUS_SEED, ensure_ascii=False)
    )
    return d


def _registry_for(data_dir: Path) -> FileRegistry:
    reg = FileRegistry()
    reg.register(
        "palio",
        FileConfig(
            path=data_dir / "palio.json",
            validator=PalioData,
            allow_edit=False,
            use_safety_copy=False,
        ),
    )
    reg.register(
        "palio_games_status",
        FileConfig(
            path=data_dir / "palio_games_status.json",
            validator=PalioGamesStatus,
            allow_edit=True,
            use_safety_copy=False,
        ),
    )
    reg.register(
        "leaderboard",
        FileConfig(
            path=data_dir / "leaderboard.json",
            validator=Leaderboard,
            allow_edit=True,
            use_safety_copy=False,
        ),
    )
    return reg


def _run_edit_sequence(editor: MultiJSONEditorTool) -> None:
    """Exercise view + two set_field calls against leaderboard."""
    editor.view("leaderboard")
    set_res = editor.set_field(
        "leaderboard",
        "$.palio_leaderboard.villa.points",
        42,
    )
    assert set_res.success, set_res.error

    set_res2 = editor.set_field(
        "leaderboard",
        "$.palio_leaderboard.salt.points",
        18,
    )
    assert set_res2.success, set_res2.error


@pytest.fixture
def direct_data_dir(tmp_path: Path) -> Path:
    return _seed_dir(tmp_path, "direct")


@pytest.fixture
def remote_data_dir(tmp_path: Path) -> Path:
    return _seed_dir(tmp_path, "remote")


def test_direct_and_remote_produce_same_canonical(
    direct_data_dir: Path, remote_data_dir: Path
):
    # --- Direct path ---
    direct_registry = _registry_for(direct_data_dir)
    direct_store = DirectFileStore(direct_registry)
    direct_tool = MultiJSONEditorTool(direct_registry, direct_store)
    _run_edit_sequence(direct_tool)

    # --- Remote path through core ---
    core_config = CoreConfig(
        palio_file_path=remote_data_dir / "palio.json",
        palio_games_status_path=remote_data_dir / "palio_games_status.json",
        leaderboard_file_path=remote_data_dir / "leaderboard.json",
        data_dir=remote_data_dir,
    )
    app = create_app(core_config)
    with TestClient(app) as tc:
        client = CoreClient(base_url="http://testserver", http_client=tc)
        sid = client.create_session("parity-test")
        remote_store = RemoteFileStore(client, sid)
        remote_registry = _registry_for(remote_data_dir)
        remote_tool = MultiJSONEditorTool(remote_registry, remote_store)
        _run_edit_sequence(remote_tool)
        client.commit(sid)

    direct_canonical = json.loads((direct_data_dir / "leaderboard.json").read_text())
    remote_canonical = json.loads((remote_data_dir / "leaderboard.json").read_text())

    assert direct_canonical == remote_canonical


def test_remote_history_and_revert_via_core(remote_data_dir: Path):
    """Through RemoteFileStore: two set_field calls then `json_revert(1)`
    must leave the canonical file at the state after the first set_field.

    DirectFileStore intentionally has no history layer (see protocol
    docstring); this is a remote-only contract, exercised here to keep
    parity tests pointed at the surface that matters for adapters."""
    core_config = CoreConfig(
        palio_file_path=remote_data_dir / "palio.json",
        palio_games_status_path=remote_data_dir / "palio_games_status.json",
        leaderboard_file_path=remote_data_dir / "leaderboard.json",
        data_dir=remote_data_dir,
    )
    app = create_app(core_config)
    with TestClient(app) as tc:
        client = CoreClient(base_url="http://testserver", http_client=tc)
        sid = client.create_session("history-revert")
        tool = MultiJSONEditorTool(
            _registry_for(remote_data_dir), RemoteFileStore(client, sid)
        )
        tool.view("leaderboard")
        tool.set_field("leaderboard", "$.palio_leaderboard.villa.points", 50)
        tool.set_field("leaderboard", "$.palio_leaderboard.villa.points", 999)

        hist = tool.history("leaderboard")
        assert hist.success
        assert len(hist.data["entries"]) == 2

        rev = tool.revert("leaderboard", n_steps=1)
        assert rev.success

        client.commit(sid)

    final = json.loads((remote_data_dir / "leaderboard.json").read_text())
    assert final["palio_leaderboard"]["villa"]["points"] == 50
