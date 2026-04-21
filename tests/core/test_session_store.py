"""Phase 2b/c tests for SessionStore.

Phase 2b covers create / stage / unstage / list in isolation — no lock
manager wiring. Phase 2c will add integration tests once sessions and
locks are composed inside a higher-level service.
"""

import pytest

from palio_bot.core.session_store import SessionStore, UnknownSession


def test_create_returns_unique_ids():
    store = SessionStore()
    s1 = store.create("cli")
    s2 = store.create("cli")
    assert s1.id != s2.id
    assert s1.label == "cli"


def test_get_returns_session():
    store = SessionStore()
    s1 = store.create("telegram:123")
    fetched = store.get(s1.id)
    assert fetched.id == s1.id
    assert fetched.label == "telegram:123"


def test_get_unknown_session_raises():
    store = SessionStore()
    with pytest.raises(UnknownSession):
        store.get("no-such-session")


def test_stage_and_get_staged():
    store = SessionStore()
    s = store.create("cli")
    store.stage(s.id, "leaderboard", {"entries": [{"village": "villa", "points": 0}]})
    staged = store.get_staged(s.id, "leaderboard")
    assert staged == {"entries": [{"village": "villa", "points": 0}]}


def test_get_staged_returns_deep_copy():
    store = SessionStore()
    s = store.create("cli")
    payload = {"entries": [{"village": "villa", "points": 0}]}
    store.stage(s.id, "leaderboard", payload)

    got = store.get_staged(s.id, "leaderboard")
    got["entries"][0]["points"] = 999

    assert store.get_staged(s.id, "leaderboard")["entries"][0]["points"] == 0


def test_stage_overwrites_previous_content():
    store = SessionStore()
    s = store.create("cli")
    store.stage(s.id, "leaderboard", {"v": 1})
    store.stage(s.id, "leaderboard", {"v": 2})
    assert store.get_staged(s.id, "leaderboard") == {"v": 2}


def test_unstage_removes_file():
    store = SessionStore()
    s = store.create("cli")
    store.stage(s.id, "leaderboard", {"v": 1})
    store.unstage(s.id, "leaderboard")
    assert store.get_staged(s.id, "leaderboard") is None


def test_staged_files_lists_names():
    store = SessionStore()
    s = store.create("cli")
    store.stage(s.id, "leaderboard", {})
    store.stage(s.id, "palio_games_status", {})
    assert set(store.staged_files(s.id)) == {"leaderboard", "palio_games_status"}


def test_delete_removes_session():
    store = SessionStore()
    s = store.create("cli")
    store.delete(s.id)
    assert not store.exists(s.id)
    with pytest.raises(UnknownSession):
        store.get(s.id)


def test_list_returns_all_sessions():
    store = SessionStore()
    s1 = store.create("cli")
    s2 = store.create("telegram:42")
    ids = {s.id for s in store.list()}
    assert ids == {s1.id, s2.id}


def test_clear_staged_drops_all_files_but_keeps_session():
    store = SessionStore()
    s = store.create("cli")
    store.stage(s.id, "leaderboard", {})
    store.stage(s.id, "palio_games_status", {})
    store.clear_staged(s.id)
    assert store.staged_files(s.id) == []
    assert store.exists(s.id)
