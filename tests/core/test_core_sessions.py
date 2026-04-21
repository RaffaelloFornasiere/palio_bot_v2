"""Phase 2d–e integration tests for session HTTP endpoints.

Covers the full acquire → PUT → commit lifecycle, lock conflicts,
validation failures, discard, and `file_changed` WS emission on commit.
"""

import json

from tests.core.conftest import LEADERBOARD_SEED


def _create_session(client, label: str = "cli") -> str:
    res = client.post("/api/sessions", json={"label": label})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_create_session_returns_id(core_client):
    sid = _create_session(core_client)
    assert isinstance(sid, str) and len(sid) > 0


def test_acquire_returns_canonical_content(core_client, core_data_dir):
    sid = _create_session(core_client)
    res = core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    assert res.status_code == 200
    body = res.json()
    assert body["content"] == LEADERBOARD_SEED
    assert "version" in body


def test_acquire_unknown_file_returns_404(core_client):
    sid = _create_session(core_client)
    res = core_client.post(f"/api/sessions/{sid}/acquire/nonexistent")
    assert res.status_code == 404


def test_acquire_unknown_session_returns_404(core_client):
    res = core_client.post("/api/sessions/does-not-exist/acquire/leaderboard")
    assert res.status_code == 404


def test_second_acquire_by_different_session_returns_409(core_client):
    s1 = _create_session(core_client, "cli")
    s2 = _create_session(core_client, "telegram:42")

    assert core_client.post(f"/api/sessions/{s1}/acquire/leaderboard").status_code == 200
    res = core_client.post(f"/api/sessions/{s2}/acquire/leaderboard")
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["error"] == "lock_conflict"
    assert detail["holder_session_id"] == s1


def test_reacquire_by_same_session_is_ok(core_client):
    sid = _create_session(core_client)
    assert core_client.post(f"/api/sessions/{sid}/acquire/leaderboard").status_code == 200
    assert core_client.post(f"/api/sessions/{sid}/acquire/leaderboard").status_code == 200


def test_put_commits_to_canonical(core_client, core_data_dir):
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")

    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 42, "position": 1},
            "salt": {"points": 10, "position": 2},
        },
    }

    put_res = core_client.put(
        f"/api/sessions/{sid}/files/leaderboard", json={"content": new_content}
    )
    assert put_res.status_code == 200, put_res.text

    commit_res = core_client.post(f"/api/sessions/{sid}/commit")
    assert commit_res.status_code == 200
    assert "leaderboard" in commit_res.json()["files"]

    on_disk = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert on_disk["palio_leaderboard"]["villa"]["points"] == 42


def test_put_without_acquire_returns_409(core_client):
    sid = _create_session(core_client)
    res = core_client.put(
        f"/api/sessions/{sid}/files/leaderboard", json={"content": LEADERBOARD_SEED}
    )
    assert res.status_code == 409


def test_put_readonly_file_returns_403(core_client):
    # `palio` is allow_edit=False in the registry.
    sid = _create_session(core_client)
    # Can't acquire palio lock first because registry doesn't block on acquire;
    # we need to hold the lock for PUT to check allow_edit. Acquire works,
    # but PUT must reject.
    core_client.post(f"/api/sessions/{sid}/acquire/palio")
    res = core_client.put(
        f"/api/sessions/{sid}/files/palio",
        json={
            "content": {
                "competition_name": "x",
                "villages": [],
                "villages_colors": {},
                "games": [],
                "non_game_events": [],
            }
        },
    )
    assert res.status_code == 403


def test_put_invalid_payload_returns_422(core_client):
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    res = core_client.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": {"bogus": "payload"}},
    )
    assert res.status_code == 422


def test_discard_releases_lock(core_client):
    s1 = _create_session(core_client, "cli")
    s2 = _create_session(core_client, "telegram:42")

    core_client.post(f"/api/sessions/{s1}/acquire/leaderboard")
    core_client.post(f"/api/sessions/{s1}/discard")

    # s2 can now acquire
    assert core_client.post(f"/api/sessions/{s2}/acquire/leaderboard").status_code == 200


def test_commit_without_put_writes_nothing(core_client, core_data_dir):
    before = (core_data_dir / "leaderboard.json").read_text()
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    res = core_client.post(f"/api/sessions/{sid}/commit")
    assert res.status_code == 200
    assert res.json()["files"] == {}
    after = (core_data_dir / "leaderboard.json").read_text()
    assert before == after


def test_list_sessions_shows_held_files(core_client):
    sid = _create_session(core_client, "cli")
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    res = core_client.get("/api/sessions")
    assert res.status_code == 200
    sessions = res.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == sid
    assert sessions[0]["files_held"] == ["leaderboard"]


def test_file_changed_event_fires_on_commit(core_client):
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")

    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 1, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }

    with core_client.websocket_connect("/events") as ws:
        core_client.put(
            f"/api/sessions/{sid}/files/leaderboard", json={"content": new_content}
        )
        core_client.post(f"/api/sessions/{sid}/commit")

        # Commit broadcasts file_changed + session_committed (in that order).
        # session_started / lock_acquired fired before we subscribed.
        file_changed = ws.receive_json()
        session_committed = ws.receive_json()

    assert file_changed["type"] == "file_changed"
    assert file_changed["file"] == "leaderboard"
    assert file_changed["session_id"] == sid
    assert session_committed["type"] == "session_committed"
    assert session_committed["session_id"] == sid
