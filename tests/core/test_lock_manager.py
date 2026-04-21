"""Phase 2a unit tests for the per-file lock registry."""

import pytest

from palio_bot.core.lock_manager import LockConflict, LockManager


def test_acquire_and_release():
    lm = LockManager()
    lm.acquire("leaderboard", "s1")
    assert lm.holder("leaderboard") == "s1"
    lm.release("leaderboard", "s1")
    assert lm.holder("leaderboard") is None


def test_acquire_conflict_raises_with_holder():
    lm = LockManager()
    lm.acquire("leaderboard", "s1")
    with pytest.raises(LockConflict) as exc:
        lm.acquire("leaderboard", "s2")
    assert exc.value.holder_session_id == "s1"
    assert exc.value.file_name == "leaderboard"


def test_acquire_by_same_session_is_idempotent():
    lm = LockManager()
    lm.acquire("leaderboard", "s1")
    lm.acquire("leaderboard", "s1")
    assert lm.holder("leaderboard") == "s1"


def test_release_by_non_holder_is_noop():
    lm = LockManager()
    lm.acquire("leaderboard", "s1")
    lm.release("leaderboard", "s2")
    assert lm.holder("leaderboard") == "s1"


def test_release_all_for_session_returns_released_files():
    lm = LockManager()
    lm.acquire("leaderboard", "s1")
    lm.acquire("palio_games_status", "s1")
    lm.acquire("palio", "s2")

    released = lm.release_all("s1")

    assert set(released) == {"leaderboard", "palio_games_status"}
    assert lm.holder("leaderboard") is None
    assert lm.holder("palio_games_status") is None
    assert lm.holder("palio") == "s2"


def test_held_by_reports_session_files():
    lm = LockManager()
    lm.acquire("leaderboard", "s1")
    lm.acquire("palio_games_status", "s1")
    lm.acquire("palio", "s2")

    assert set(lm.held_by("s1")) == {"leaderboard", "palio_games_status"}
    assert lm.held_by("s2") == ["palio"]
    assert lm.held_by("nonexistent") == []


def test_holder_missing_file_returns_none():
    lm = LockManager()
    assert lm.holder("leaderboard") is None
