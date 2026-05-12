"""Unit tests for HistoryService — git-backed history & rollback layer.

Each test gets a fresh temp data_dir with three seed JSON files, mirroring
the production registered set. We exercise the service directly (no
FastAPI, no HTTP) so failures point at one component.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pygit2
import pytest

from palio_bot.core.history import (
    LAST_SAVE_REF,
    HistoryService,
    festival_day,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    (d / "palio.json").write_text(json.dumps({"name": "P"}))
    (d / "palio_games_status.json").write_text(json.dumps({"v": 1}))
    (d / "leaderboard.json").write_text(json.dumps({"v": 1}))
    return d


@pytest.fixture
def tracked(data_dir: Path) -> list[Path]:
    return [
        data_dir / "palio.json",
        data_dir / "palio_games_status.json",
        data_dir / "leaderboard.json",
    ]


@pytest.fixture
def history(data_dir: Path, tracked: list[Path]) -> HistoryService:
    hs = HistoryService(data_dir)
    hs.init_repo(tracked)
    return hs


def _repo(data_dir: Path) -> pygit2.Repository:
    return pygit2.Repository(str(data_dir))


# ---------- init ----------


def test_init_repo_creates_seed_commit_and_last_save(data_dir: Path, tracked):
    hs = HistoryService(data_dir)
    hs.init_repo(tracked)
    repo = _repo(data_dir)
    assert (data_dir / ".git").is_dir()
    assert repo.head.target == repo.references[LAST_SAVE_REF].target
    seed = repo.head.peel(pygit2.Commit)
    assert seed.message.startswith("seed:")


def test_init_repo_is_idempotent(data_dir: Path, tracked):
    HistoryService(data_dir).init_repo(tracked)
    repo = _repo(data_dir)
    seed_sha = repo.head.target
    # Second init must open, not re-seed.
    HistoryService(data_dir).init_repo(tracked)
    assert _repo(data_dir).head.target == seed_sha


# ---------- record_write ----------


def test_record_write_commits_disk_state(history: HistoryService, data_dir: Path):
    (data_dir / "palio_games_status.json").write_text(json.dumps({"v": 2}))
    sha = history.record_write(
        file_name="palio_games_status.json",
        source="cli", committer="forna", session_id="s",
    )
    assert sha is not None
    repo = _repo(data_dir)
    assert str(repo.head.target) == sha
    # last_save is NOT moved by per-write commits.
    assert str(repo.references[LAST_SAVE_REF].target) != sha


def test_record_write_returns_none_when_tree_unchanged(
    history: HistoryService, data_dir: Path
):
    # No on-disk change → no commit.
    sha = history.record_write(
        file_name="palio_games_status.json",
        source="cli", committer=None, session_id="s",
    )
    assert sha is None


def test_record_write_trailers_include_tool_and_session(
    history: HistoryService, data_dir: Path
):
    (data_dir / "leaderboard.json").write_text(json.dumps({"v": 9}))
    history.record_write(
        file_name="leaderboard.json",
        source="agent", committer="@forna_tg", session_id="abc123",
        tool="json_set",
    )
    msg = _repo(data_dir).head.peel(pygit2.Commit).message
    assert "source: agent" in msg
    assert "committer: @forna_tg" in msg
    assert "tool: json_set" in msg
    assert "session: abc123" in msg


# ---------- finalize_save (squash) ----------


def test_finalize_save_squashes_intra_session_commits(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    # Three writes → three intra-session commits.
    for v in (2, 3, 4):
        f.write_text(json.dumps({"v": v}))
        history.record_write(
            file_name="leaderboard.json",
            source="cli", committer=None, session_id="s",
        )
    repo = _repo(data_dir)
    pre_head = repo.head.target
    pre_last_save = repo.references[LAST_SAVE_REF].target
    assert pre_head != pre_last_save

    sha = history.finalize_save(
        source="cli", committer=None, session_id="s",
        files_touched=["leaderboard.json"],
    )
    assert sha is not None

    repo = _repo(data_dir)
    new_head = repo.head.target
    assert str(new_head) == sha
    assert repo.references[LAST_SAVE_REF].target == new_head
    # The squashed commit's parent must be the OLD last_save (= seed),
    # not the last per-write commit.
    parent = repo.head.peel(pygit2.Commit).parents[0]
    assert parent.id == pre_last_save


def test_finalize_save_returns_none_when_nothing_changed(history: HistoryService):
    sha = history.finalize_save(
        source="cli", committer=None, session_id="s",
        files_touched=["leaderboard.json"],
    )
    assert sha is None


# ---------- revert_session_files (discard) ----------


def test_revert_session_files_restores_working_tree(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 999}))
    history.record_write(
        file_name="leaderboard.json",
        source="cli", committer=None, session_id="s",
    )
    assert json.loads(f.read_text()) == {"v": 999}

    history.revert_session_files(
        files_touched=["leaderboard.json"],
        source="cli", committer=None, session_id="s",
    )

    assert json.loads(f.read_text()) == {"v": 1}  # back to seed
    assert "cancel session" in _repo(data_dir).head.peel(pygit2.Commit).message


# ---------- revert_steps ----------


def test_revert_steps_one_step_undoes_only_the_most_recent(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    for v in (10, 20, 30):
        f.write_text(json.dumps({"v": v}))
        history.record_write(
            file_name="leaderboard.json",
            source="cli", committer=None, session_id="s",
        )

    history.revert_steps(
        file_name="leaderboard.json", n_steps=1,
        source="cli", committer=None,
    )
    assert json.loads(f.read_text()) == {"v": 20}


def test_revert_steps_all_returns_to_last_save(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    for v in (10, 20, 30):
        f.write_text(json.dumps({"v": v}))
        history.record_write(
            file_name="leaderboard.json",
            source="cli", committer=None, session_id="s",
        )

    history.revert_steps(
        file_name="leaderboard.json", n_steps=3,
        source="cli", committer=None,
    )
    assert json.loads(f.read_text()) == {"v": 1}  # seed state


def test_revert_steps_out_of_range_returns_none(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 2}))
    history.record_write(
        file_name="leaderboard.json",
        source="cli", committer=None, session_id="s",
    )
    sha = history.revert_steps(
        file_name="leaderboard.json", n_steps=99,
        source="cli", committer=None,
    )
    assert sha is None


# ---------- list_session_commits ----------


def test_list_session_commits_scopes_to_since_last_save(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 2}))
    history.record_write(
        file_name="leaderboard.json", source="cli", committer=None,
        session_id="s", tool="json_set",
    )
    f.write_text(json.dumps({"v": 3}))
    history.record_write(
        file_name="leaderboard.json", source="cli", committer=None,
        session_id="s", tool="json_set",
    )

    entries = history.list_session_commits("leaderboard.json", limit=10)
    assert len(entries) == 2
    assert all(e.tool == "json_set" for e in entries)


def test_list_session_commits_empty_after_save(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 2}))
    history.record_write(
        file_name="leaderboard.json",
        source="cli", committer=None, session_id="s",
    )
    history.finalize_save(
        source="cli", committer=None, session_id="s",
        files_touched=["leaderboard.json"],
    )
    assert history.list_session_commits("leaderboard.json") == []


# ---------- read_at_ref ----------


def test_read_at_ref_returns_last_save_blob(
    history: HistoryService, data_dir: Path
):
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 7}))
    history.record_write(
        file_name="leaderboard.json",
        source="cli", committer=None, session_id="s",
    )
    # Before save: last_save still has seed content.
    blob = history.read_at_ref("leaderboard.json")
    assert json.loads(blob) == {"v": 1}

    history.finalize_save(
        source="cli", committer=None, session_id="s",
        files_touched=["leaderboard.json"],
    )
    blob = history.read_at_ref("leaderboard.json")
    assert json.loads(blob) == {"v": 7}


def test_read_at_ref_unknown_file_returns_none(history: HistoryService):
    assert history.read_at_ref("does_not_exist.json") is None


# ---------- snap_workdir (admin reset) ----------


def test_snap_workdir_anchors_last_save_to_seed_state(
    history: HistoryService, data_dir: Path, tracked: list[Path]
):
    # Simulate admin/reset: replace canonical files bypassing the session
    # layer, then snap_workdir to lock that state as the new baseline.
    (data_dir / "leaderboard.json").write_text(json.dumps({"v": 100}))
    history.snap_workdir(tracked_files=tracked, source="admin", label="reset")

    repo = _repo(data_dir)
    assert repo.head.target == repo.references[LAST_SAVE_REF].target

    # Subsequent agent edits + revert(n=all) must land at the snap, not
    # at the pre-snap seed.
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 200}))
    history.record_write(
        file_name="leaderboard.json",
        source="agent", committer=None, session_id="s",
    )
    history.revert_steps(
        file_name="leaderboard.json", n_steps=1,
        source="agent", committer=None,
    )
    assert json.loads(f.read_text()) == {"v": 100}


# ---------- festival_day cutoff ----------


def test_festival_day_cutoff_5am_europe_rome():
    rome = datetime(2024, 8, 14, 1, 30, tzinfo=timezone.utc)  # 03:30 Rome
    # Activity at 03:30 Rome should belong to the previous festival day.
    # We pass UTC and let festival_day handle the tz shift.
    from zoneinfo import ZoneInfo
    rome_local = datetime(2024, 8, 14, 1, 30, tzinfo=ZoneInfo("Europe/Rome"))
    assert festival_day(rome_local.astimezone(timezone.utc)) == "2024-08-13"

    morning = datetime(2024, 8, 14, 5, 1, tzinfo=ZoneInfo("Europe/Rome"))
    assert festival_day(morning.astimezone(timezone.utc)) == "2024-08-14"

    boundary = datetime(2024, 8, 14, 4, 59, tzinfo=ZoneInfo("Europe/Rome"))
    assert festival_day(boundary.astimezone(timezone.utc)) == "2024-08-13"


# ---------- daily tag (lazy) ----------


def test_daily_tag_created_when_festival_day_rolls_over(
    history: HistoryService, data_dir: Path
):
    """Forge a 'yesterday' last_save by rewriting committer time, then
    save again: the rollover triggers a lazy tag of yesterday's date."""
    f = data_dir / "leaderboard.json"
    f.write_text(json.dumps({"v": 5}))
    history.record_write(
        file_name="leaderboard.json",
        source="cli", committer=None, session_id="s1",
    )
    history.finalize_save(
        source="cli", committer=None, session_id="s1",
        files_touched=["leaderboard.json"],
    )
    old_last_save = _repo(data_dir).references[LAST_SAVE_REF].target

    # Forge the committer time of the current last_save to "two days ago".
    repo = _repo(data_dir)
    old_commit = repo.get(old_last_save)
    forged_time = old_commit.commit_time - 2 * 86400  # -2 days
    sig_forged = pygit2.Signature(
        old_commit.author.name, old_commit.author.email,
        forged_time, old_commit.author.offset,
    )
    parent_oids = [p.id for p in old_commit.parents]
    new_oid = repo.create_commit(
        None, sig_forged, sig_forged,
        old_commit.message, old_commit.tree.id, parent_oids,
    )
    repo.references[LAST_SAVE_REF].set_target(new_oid)
    repo.set_head(new_oid)

    # Now save again — festival day rolled over, so a daily tag should
    # be created on the OLD last_save value.
    f.write_text(json.dumps({"v": 6}))
    history.record_write(
        file_name="leaderboard.json",
        source="cli", committer=None, session_id="s2",
    )
    history.finalize_save(
        source="cli", committer=None, session_id="s2",
        files_touched=["leaderboard.json"],
    )

    repo = _repo(data_dir)
    tag_refs = [r for r in repo.references if r.startswith("refs/tags/")]
    assert len(tag_refs) == 1
    tag_name = tag_refs[0].split("refs/tags/", 1)[1]
    # Festival_day("2 days ago") — exact date depends on wall clock, but
    # it must NOT be today.
    today = festival_day(datetime.now(timezone.utc))
    assert tag_name != today
