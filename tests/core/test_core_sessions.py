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


def test_parallel_sessions_can_both_acquire(core_client):
    """Multiple sessions may acquire the same file concurrently. The
    system assumes a single active editor at a time; this test only
    confirms acquire itself doesn't lock the file across sessions."""
    s1 = _create_session(core_client, "cli")
    s2 = _create_session(core_client, "telegram:42")

    assert core_client.post(f"/api/sessions/{s1}/acquire/leaderboard").status_code == 200
    assert core_client.post(f"/api/sessions/{s2}/acquire/leaderboard").status_code == 200


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


def test_put_without_acquire_is_ok(core_client):
    """Without locks, PUT stages directly — acquire is an optimization, not a
    requirement."""
    sid = _create_session(core_client)
    res = core_client.put(
        f"/api/sessions/{sid}/files/leaderboard", json={"content": LEADERBOARD_SEED}
    )
    assert res.status_code == 200


def test_put_readonly_file_returns_403(core_client):
    # `palio` is allow_edit=False in the registry.
    sid = _create_session(core_client)
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


def test_discard_clears_session_state(core_client):
    sid = _create_session(core_client, "cli")
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    assert core_client.post(f"/api/sessions/{sid}/discard").status_code == 200
    # session is gone — subsequent ops return 404
    assert (
        core_client.post(f"/api/sessions/{sid}/acquire/leaderboard").status_code == 404
    )


def test_commit_without_put_writes_nothing(core_client, core_data_dir):
    before = (core_data_dir / "leaderboard.json").read_text()
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    res = core_client.post(f"/api/sessions/{sid}/commit")
    assert res.status_code == 200
    assert res.json()["files"] == {}
    after = (core_data_dir / "leaderboard.json").read_text()
    assert before == after


def test_list_sessions_shows_dirty_files(core_client):
    sid = _create_session(core_client, "cli")
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    core_client.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": LEADERBOARD_SEED},
    )
    res = core_client.get("/api/sessions")
    assert res.status_code == 200
    sessions = res.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == sid
    assert sessions[0]["files_dirty"] == ["leaderboard"]


# ---------- per-PUT commits + squash + history endpoints ----------


def test_put_creates_intra_session_history_entry(core_client):
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")

    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 5, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }
    core_client.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": new_content, "tool": "json_set"},
    )

    r = core_client.get(f"/api/sessions/{sid}/history/leaderboard")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["step"] == 1
    assert entries[0]["tool"] == "json_set"


def test_history_is_empty_after_commit(core_client):
    """`finalize_save` squashes intra-session commits into one and moves
    `last_save` forward; from a new session's perspective there is no
    history to revert into."""
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 1, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }
    core_client.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": new_content, "tool": "json_set"},
    )
    core_client.post(f"/api/sessions/{sid}/commit")

    sid2 = _create_session(core_client)
    r = core_client.get(f"/api/sessions/{sid2}/history/leaderboard")
    assert r.json()["entries"] == []


def test_revert_endpoint_undoes_n_steps(core_client, core_data_dir):
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    for pts in (10, 20, 30):
        new_content = {
            **LEADERBOARD_SEED,
            "palio_leaderboard": {
                "villa": {"points": pts, "position": 1},
                "salt": {"points": 0, "position": 2},
            },
        }
        core_client.put(
            f"/api/sessions/{sid}/files/leaderboard",
            json={"content": new_content, "tool": "json_set"},
        )

    r = core_client.post(
        f"/api/sessions/{sid}/revert/leaderboard", json={"n_steps": 1}
    )
    assert r.status_code == 200
    assert r.json() == {"applied": True, "n_steps": 1}
    disk = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert disk["palio_leaderboard"]["villa"]["points"] == 20


def test_revert_out_of_range_returns_400(core_client):
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    r = core_client.post(
        f"/api/sessions/{sid}/revert/leaderboard", json={"n_steps": 99}
    )
    assert r.status_code == 400


def test_discard_rolls_back_working_tree(core_client, core_data_dir):
    """`/discard` must restore every touched file to `last_save`. Without
    this, an aborted agent run would leave the public webapp serving
    partial state."""
    before = json.loads((core_data_dir / "leaderboard.json").read_text())
    sid = _create_session(core_client)
    core_client.post(f"/api/sessions/{sid}/acquire/leaderboard")
    new_content = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 999, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }
    core_client.put(
        f"/api/sessions/{sid}/files/leaderboard",
        json={"content": new_content, "tool": "json_set"},
    )
    mid = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert mid["palio_leaderboard"]["villa"]["points"] == 999

    core_client.post(f"/api/sessions/{sid}/discard")

    after = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert after == before


def test_file_changed_event_fires_on_put_then_session_committed(core_client):
    """With write-through PUTs, `file_changed` fires per PUT (canonical
    disk has actually changed). `commit` only fires `session_committed`
    — the squash itself produces no further `file_changed`."""
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
        file_changed = ws.receive_json()
        core_client.post(f"/api/sessions/{sid}/commit")
        session_committed = ws.receive_json()

    assert file_changed["event"]["type"] == "file_changed"
    assert file_changed["event"]["file"] == "leaderboard"
    assert file_changed["event"]["session_id"] == sid
    assert session_committed["event"]["type"] == "session_committed"
    assert session_committed["event"]["session_id"] == sid
