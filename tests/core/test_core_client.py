"""Phase 3 integration tests for CoreClient + RemoteFileStore.

Uses FastAPI's TestClient (which is itself an httpx.Client) injected into
CoreClient so we exercise the full HTTP contract in-process — no real
sockets, but all marshalling/unmarshalling runs.
"""

import json

import pytest
from fastapi.testclient import TestClient

from palio_bot.core.app import create_app
from palio_bot.core_client.client import CoreClient, CoreClientError
from palio_bot.core_client.file_store_remote import RemoteFileStore
from palio_bot.file_store import (
    FileStoreLockConflict,
    FileStoreValidationError,
)

from tests.core.conftest import LEADERBOARD_SEED, PALIO_SEED


@pytest.fixture
def core_test_client(core_config):
    app = create_app(core_config, enable_leaderboard_hook=False)
    with TestClient(app) as tc:
        yield tc


@pytest.fixture
def core_rpc(core_test_client) -> CoreClient:
    return CoreClient(base_url="http://testserver", http_client=core_test_client)


def test_get_file_roundtrip(core_rpc: CoreClient):
    content = core_rpc.get_file("leaderboard")
    assert content["palio_leaderboard"]["villa"]["points"] == 0


def test_create_session_and_commit(core_rpc: CoreClient, core_data_dir):
    sid = core_rpc.create_session("cli")
    store = RemoteFileStore(core_rpc, sid)

    data = store.load("leaderboard")
    assert data["palio_leaderboard"]["villa"]["points"] == 0

    data["palio_leaderboard"]["villa"]["points"] = 77
    store.save("leaderboard", data)

    core_rpc.commit(sid)

    on_disk = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert on_disk["palio_leaderboard"]["villa"]["points"] == 77


def test_remote_load_returns_independent_copy(core_rpc: CoreClient):
    sid = core_rpc.create_session("cli")
    store = RemoteFileStore(core_rpc, sid)

    a = store.load("leaderboard")
    a["palio_leaderboard"]["villa"]["points"] = 999

    b = store.load("leaderboard")
    assert b["palio_leaderboard"]["villa"]["points"] == 0


def test_lock_conflict_raises_file_store_error(core_rpc: CoreClient):
    s1 = core_rpc.create_session("cli")
    s2 = core_rpc.create_session("telegram:42")

    RemoteFileStore(core_rpc, s1).load("leaderboard")

    with pytest.raises(FileStoreLockConflict) as exc:
        RemoteFileStore(core_rpc, s2).load("leaderboard")
    assert exc.value.holder_session_id == s1


def test_validation_error_raises_file_store_error(core_rpc: CoreClient):
    sid = core_rpc.create_session("cli")
    store = RemoteFileStore(core_rpc, sid)
    store.load("leaderboard")

    with pytest.raises(FileStoreValidationError):
        store.save("leaderboard", {"clearly": "invalid"})


def test_discard_releases_lock(core_rpc: CoreClient):
    s1 = core_rpc.create_session("cli")
    s2 = core_rpc.create_session("telegram:42")

    RemoteFileStore(core_rpc, s1).load("leaderboard")
    core_rpc.discard(s1)

    # s2 can now acquire
    RemoteFileStore(core_rpc, s2).load("leaderboard")


def test_admin_reset_wipes_sessions(core_rpc: CoreClient):
    sid = core_rpc.create_session("cli")
    RemoteFileStore(core_rpc, sid).load("leaderboard")

    core_rpc.admin_reset()

    assert core_rpc.list_sessions()["sessions"] == []


def test_admin_reset_applies_seeds(core_rpc: CoreClient, core_data_dir, tmp_path):
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    replacement = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 250, "position": 1},
            "salt": {"points": 100, "position": 2},
        },
    }
    (seeds / "leaderboard.json").write_text(json.dumps(replacement))
    (seeds / "palio.json").write_text(json.dumps(PALIO_SEED))

    core_rpc.admin_reset(seeds_dir=str(seeds))

    lb = core_rpc.get_file("leaderboard")
    assert lb["palio_leaderboard"]["villa"]["points"] == 250


def test_unknown_session_raises_core_client_error(core_rpc: CoreClient):
    with pytest.raises(CoreClientError) as exc:
        core_rpc.acquire("no-such-session", "leaderboard")
    assert exc.value.status_code == 404
