"""Tests for MultiJSONEditorTool.

Several tests marked xfail document bugs to be fixed in step 4 of the refactor
(see REFACTOR_PLAN.md). After the fix they should be un-marked.
"""

import json
from pathlib import Path

import pytest

from palio_bot.tools.file_registry import FileRegistry
from palio_bot.tools.multi_json_editor_tool import MultiJSONEditorTool


@pytest.fixture
def editor(registry: FileRegistry) -> MultiJSONEditorTool:
    e = MultiJSONEditorTool(registry)
    # Pre-view the editable files so tests don't need to sprinkle view() calls.
    # Real callers (the agent) are forced to view first by the guardrail.
    e.view("palio_games_status")
    e.view("leaderboard")
    return e


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


# ---------- view ----------


def test_view_full_file(editor: MultiJSONEditorTool):
    result = editor.view("palio")
    assert result.success
    assert result.data["matches"] == 1
    content = json.loads(result.data["content"])
    assert content["palio"]["anno"] == 2026


def test_view_with_simple_jsonpath(editor: MultiJSONEditorTool):
    result = editor.view("palio", path="$.palio.anno")
    assert result.success
    assert result.data["matches"] == 1
    assert json.loads(result.data["content"]) == 2026


def test_view_unknown_file_returns_error(editor: MultiJSONEditorTool):
    result = editor.view("nonexistent")
    assert not result.success
    assert "non registrato" in result.error


def test_view_nonmatching_path_returns_error(editor: MultiJSONEditorTool):
    result = editor.view("palio", path="$.does.not.exist")
    assert not result.success


# ---------- set_field ----------


def test_set_field_simple_path(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.set_field("palio_games_status", "$.game_scores.calcetto.status", "in-progress")
    assert result.success
    data = _read(tmp_data_dir / "palio_games_status.json")
    assert data["game_scores"]["calcetto"]["status"] == "in-progress"


def test_set_field_nested_path(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.set_field(
        "palio_games_status", "$.game_scores.calcetto.scores.villa", 3
    )
    assert result.success
    data = _read(tmp_data_dir / "palio_games_status.json")
    assert data["game_scores"]["calcetto"]["scores"]["villa"] == 3


def test_set_field_whole_subtree(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    new_status = {
        "status": "completed",
        "scores": {"villa": 4, "salt": 2, "sottocastello": 1},
        "applied_bonuses": [],
        "applied_penalties": [],
        "score_penalties": [],
    }
    result = editor.set_field(
        "palio_games_status", "$.game_scores.calcetto", new_status
    )
    assert result.success
    data = _read(tmp_data_dir / "palio_games_status.json")
    assert data["game_scores"]["calcetto"] == new_status


def test_set_field_with_jsonpath_filter(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    """Filter syntax resolves to the correct location (bug #1 fixed)."""
    path = tmp_data_dir / "palio_games_status.json"
    data = _read(path)
    data["game_scores"]["calcetto"]["scores"] = [
        {"village": "villa", "points": 0},
        {"village": "salt", "points": 0},
    ]
    path.write_text(json.dumps(data))
    editor.view("palio_games_status")  # refresh view after external file edit

    result = editor.set_field(
        "palio_games_status",
        "$.game_scores.calcetto.scores[?(@.village=='villa')].points",
        5,
    )
    assert result.success
    data = _read(path)
    villa = next(s for s in data["game_scores"]["calcetto"]["scores"] if s["village"] == "villa")
    assert villa["points"] == 5
    # And no corrupt key was added
    assert all(not k.startswith("scores[") for k in data["game_scores"]["calcetto"].keys())


def test_set_field_readonly_file_rejected(editor: MultiJSONEditorTool):
    result = editor.set_field("palio", "$.palio.anno", 2027)
    assert not result.success
    assert "sola lettura" in result.error


# ---------- delete_field ----------


def test_delete_field_removes_key(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.delete_field("leaderboard", "$.entries[0].points")
    assert result.success
    data = _read(tmp_data_dir / "leaderboard.json")
    assert "points" not in data["entries"][0]


def test_delete_field_does_not_prune_unrelated_none_values(
    editor: MultiJSONEditorTool, tmp_data_dir: Path
):
    """Bug #2 fixed: delete_field no longer walks the tree pruning None values."""
    path = tmp_data_dir / "leaderboard.json"
    data = _read(path)
    data["unrelated_list"] = [1, None, 2, None, 3]
    path.write_text(json.dumps(data))
    editor.view("leaderboard")

    result = editor.delete_field("leaderboard", "$.entries[0].points")
    assert result.success
    data = _read(path)
    assert data["unrelated_list"] == [1, None, 2, None, 3]


# ---------- append ----------


def test_append_to_array(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.append("leaderboard", "$.entries", {"village": "new", "points": 5})
    assert result.success
    data = _read(tmp_data_dir / "leaderboard.json")
    assert data["entries"][-1] == {"village": "new", "points": 5}


def test_append_to_non_array_fails(editor: MultiJSONEditorTool):
    result = editor.append("palio_games_status", "$.last_updated", "x")
    assert not result.success


# ---------- insert_at / remove_at ----------


def test_insert_at(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.insert_at(
        "leaderboard", "$.entries", 0, {"village": "first", "points": 99}
    )
    assert result.success
    data = _read(tmp_data_dir / "leaderboard.json")
    assert data["entries"][0] == {"village": "first", "points": 99}


def test_remove_at(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.remove_at("leaderboard", "$.entries", 0)
    assert result.success
    data = _read(tmp_data_dir / "leaderboard.json")
    assert len(data["entries"]) == 2


def test_remove_at_invalid_index(editor: MultiJSONEditorTool):
    result = editor.remove_at("leaderboard", "$.entries", 999)
    assert not result.success


# ---------- history / revert ----------
#
# DirectFileStore (used by this fixture) has no history layer — eval
# scenarios run against a real core, not this in-process store. The
# tool surface still must exist and degrade gracefully.


def test_history_on_direct_store_returns_empty(editor: MultiJSONEditorTool):
    editor.set_field("palio_games_status", "$.game_scores.calcetto.status", "in-progress")
    result = editor.history("palio_games_status")
    assert result.success
    assert result.data == {"entries": []}


def test_revert_on_direct_store_fails(editor: MultiJSONEditorTool):
    editor.set_field("palio_games_status", "$.game_scores.calcetto.status", "in-progress")
    result = editor.revert("palio_games_status", n_steps=1)
    assert not result.success


# ---------- view-before-edit ----------


def test_edit_without_view_is_rejected(registry: FileRegistry):
    """Fresh editor with no prior views: writes must be rejected."""
    fresh = MultiJSONEditorTool(registry)
    result = fresh.set_field("palio_games_status", "$.game_scores.calcetto.status", "x")
    assert not result.success
    assert "view" in (result.error or "").lower()


def test_view_on_ancestor_allows_descendant_edit(registry: FileRegistry):
    fresh = MultiJSONEditorTool(registry)
    fresh.view("palio_games_status", "$.game_scores.calcetto")
    result = fresh.set_field(
        "palio_games_status", "$.game_scores.calcetto.status", "in-progress"
    )
    assert result.success


def test_view_does_not_leak_across_siblings(registry: FileRegistry, tmp_data_dir: Path):
    """Viewing $.a.b should NOT authorise edits to $.a.bc."""
    path = tmp_data_dir / "leaderboard.json"
    data = _read(path)
    data["a"] = {"b": {"x": 1}, "bc": {"y": 2}}
    path.write_text(json.dumps(data))

    fresh = MultiJSONEditorTool(registry)
    fresh.view("leaderboard", "$.a.b")
    result = fresh.set_field("leaderboard", "$.a.bc.y", 99)
    assert not result.success


def test_view_persists_across_writes(editor: MultiJSONEditorTool):
    """Once viewed, subsequent edits to the same subtree are allowed without re-viewing.

    The guardrail's goal is "don't edit what you haven't seen once" — not
    "re-view before every follow-up edit". Sequential edits are common.
    """
    r1 = editor.set_field("palio_games_status", "$.game_scores.calcetto.status", "in-progress")
    assert r1.success
    r2 = editor.set_field("palio_games_status", "$.game_scores.calcetto.status", "completed")
    assert r2.success


# ---------- merge ----------


def test_merge_deep_merges_dicts(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    result = editor.merge(
        "palio_games_status",
        "$.game_scores.calcetto",
        {"status": "completed", "scores": {"villa": 5}},
    )
    assert result.success
    data = _read(tmp_data_dir / "palio_games_status.json")
    cal = data["game_scores"]["calcetto"]
    assert cal["status"] == "completed"
    assert cal["scores"]["villa"] == 5
    # Other scores preserved (deep merge)
    assert cal["scores"]["salt"] == 0
    # Other fields preserved
    assert "applied_bonuses" in cal


def test_merge_replaces_non_dict_values(editor: MultiJSONEditorTool, tmp_data_dir: Path):
    """When the target path holds a scalar/list, merge replaces it."""
    result = editor.merge("palio_games_status", "$.last_updated", "2026-04-19T00:00:00Z")
    assert result.success
    data = _read(tmp_data_dir / "palio_games_status.json")
    assert data["last_updated"] == "2026-04-19T00:00:00Z"
