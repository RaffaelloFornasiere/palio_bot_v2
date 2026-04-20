"""Unit tests for LeaderboardUpdater.

Targets the pure-logic helpers (`_apply_ranking_points`,
`_apply_bonuses_and_penalties`, `_calculate_round_robin_raw_scores`, etc.) and
also exercises a few `update_leaderboard()` round-trips against tmp files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from palio_bot.leaderboard_updater import LeaderboardUpdater


# ---------- helpers ----------

def _make_updater(tmp_path: Path, palio: dict, status: dict, leaderboard: dict | None = None) -> LeaderboardUpdater:
    palio_path = tmp_path / "palio.json"
    status_path = tmp_path / "palio_games_status.json"
    leaderboard_path = tmp_path / "leaderboard.json"

    palio_path.write_text(json.dumps(palio, ensure_ascii=False))
    status_path.write_text(json.dumps(status, ensure_ascii=False))
    if leaderboard is not None:
        leaderboard_path.write_text(json.dumps(leaderboard, ensure_ascii=False))

    return LeaderboardUpdater(palio_path, status_path, leaderboard_path)


def _bare_updater() -> LeaderboardUpdater:
    """Updater with placeholder paths — only safe for pure-helper tests."""
    return LeaderboardUpdater(Path("/dev/null"), Path("/dev/null"), Path("/dev/null"))


VILLAGES = ["Villa", "Salt", "Sornico", "Sottocastello", "Sottomonte"]


def _empty_leaderboard() -> dict:
    return {
        "villages": list(VILLAGES),
        "palio_leaderboard": {v: {"points": 0, "position": 1} for v in VILLAGES},
        "game_leaderboards": {},
    }


# ---------- _find_game_definition ----------

def test_find_game_definition_returns_match():
    updater = _bare_updater()
    palio = {"games": [{"id": "G01", "name": "Taglio"}, {"id": "G02", "name": "Anguria"}]}
    assert updater._find_game_definition(palio, "G02") == {"id": "G02", "name": "Anguria"}


def test_find_game_definition_returns_none_when_missing():
    updater = _bare_updater()
    palio = {"games": [{"id": "G01"}]}
    assert updater._find_game_definition(palio, "GX") is None


def test_find_game_definition_handles_no_games_key():
    assert _bare_updater()._find_game_definition({}, "G01") is None


# ---------- _apply_ranking_points ----------

def test_apply_ranking_points_assigns_10_7_5_3_1():
    updater = _bare_updater()
    raw = {"a": 50, "b": 40, "c": 30, "d": 20, "e": 10}
    result = updater._apply_ranking_points({}, raw)
    assert result == {"a": 10, "b": 7, "c": 5, "d": 3, "e": 1}


def test_apply_ranking_points_lower_is_better_inverts_order():
    updater = _bare_updater()
    raw = {"a": 5.0, "b": 10.0, "c": 20.0}
    result = updater._apply_ranking_points({"lower_is_better": True}, raw)
    assert result == {"a": 10, "b": 7, "c": 5}


def test_apply_ranking_points_beyond_top_5_gets_zero():
    updater = _bare_updater()
    raw = {f"v{i}": 100 - i for i in range(7)}
    result = updater._apply_ranking_points({}, raw)
    # Top 5 get points, rest get 0
    awarded = [pts for pts in result.values() if pts > 0]
    zeros = [pts for pts in result.values() if pts == 0]
    assert sorted(awarded, reverse=True) == [10, 7, 5, 3, 1]
    assert len(zeros) == 2


def test_apply_ranking_points_empty_input_returns_empty():
    assert _bare_updater()._apply_ranking_points({}, {}) == {}


def test_apply_ranking_points_fewer_than_5_villages():
    updater = _bare_updater()
    raw = {"a": 30, "b": 20, "c": 10}
    result = updater._apply_ranking_points({}, raw)
    assert result == {"a": 10, "b": 7, "c": 5}


# ---------- _apply_bonuses_and_penalties ----------

def test_apply_bonuses_adds_to_existing_village():
    updater = _bare_updater()
    base = {"Villa": 10, "Salt": 7}
    game_data = {"applied_bonuses": [{"village": "Villa", "points": 3, "description": "x"}]}
    assert updater._apply_bonuses_and_penalties(game_data, base) == {"Villa": 13, "Salt": 7}


def test_apply_penalties_subtracts_negative_points():
    updater = _bare_updater()
    base = {"Villa": 10}
    game_data = {"applied_penalties": [{"village": "Villa", "points": -4, "description": "x"}]}
    assert updater._apply_bonuses_and_penalties(game_data, base) == {"Villa": 6}


def test_apply_bonus_to_unknown_village_is_ignored():
    updater = _bare_updater()
    base = {"Villa": 10}
    game_data = {"applied_bonuses": [{"village": "Ghost", "points": 5}]}
    assert updater._apply_bonuses_and_penalties(game_data, base) == {"Villa": 10}


def test_apply_bonuses_does_not_mutate_input():
    updater = _bare_updater()
    base = {"Villa": 10}
    game_data = {"applied_bonuses": [{"village": "Villa", "points": 3}]}
    updater._apply_bonuses_and_penalties(game_data, base)
    assert base == {"Villa": 10}


def test_apply_bonuses_empty_leaderboard_returns_empty():
    updater = _bare_updater()
    game_data = {"applied_bonuses": [{"village": "Villa", "points": 5}]}
    assert updater._apply_bonuses_and_penalties(game_data, {}) == {}


def test_multiple_bonuses_and_penalties_stack():
    updater = _bare_updater()
    base = {"Villa": 10, "Salt": 7}
    game_data = {
        "applied_bonuses": [
            {"village": "Villa", "points": 2},
            {"village": "Salt", "points": 1},
        ],
        "applied_penalties": [
            {"village": "Villa", "points": -1},
        ],
    }
    assert updater._apply_bonuses_and_penalties(game_data, base) == {"Villa": 11, "Salt": 8}


# ---------- _calculate_round_robin_raw_scores ----------

def test_round_robin_win_awards_3_points():
    updater = _bare_updater()
    division = {
        "rounds": [
            {"scores": [{"village": "Villa", "points": 4}, {"village": "Salt", "points": 2}]},
        ]
    }
    assert updater._calculate_round_robin_raw_scores({}, division) == {"Villa": 3, "Salt": 0}


def test_round_robin_draw_awards_1_each():
    updater = _bare_updater()
    division = {
        "rounds": [
            {"scores": [{"village": "Villa", "points": 2}, {"village": "Salt", "points": 2}]},
        ]
    }
    assert updater._calculate_round_robin_raw_scores({}, division) == {"Villa": 1, "Salt": 1}


def test_round_robin_accumulates_across_rounds():
    updater = _bare_updater()
    division = {
        "rounds": [
            {"scores": [{"village": "Villa", "points": 3}, {"village": "Salt", "points": 1}]},
            {"scores": [{"village": "Villa", "points": 2}, {"village": "Salt", "points": 2}]},
            {"scores": [{"village": "Salt", "points": 5}, {"village": "Villa", "points": 0}]},
        ]
    }
    # Villa: win + draw + loss = 3 + 1 + 0 = 4
    # Salt:  loss + draw + win  = 0 + 1 + 3 = 4
    assert updater._calculate_round_robin_raw_scores({}, division) == {"Villa": 4, "Salt": 4}


def test_round_robin_skips_malformed_rounds():
    updater = _bare_updater()
    division = {
        "rounds": [
            "not a dict",
            {"scores": [{"village": "Villa", "points": 3}]},  # only 1 entry
            {"scores": [{"village": "Villa", "points": 3}, {"village": "Salt", "points": 1}]},
        ]
    }
    assert updater._calculate_round_robin_raw_scores({}, division) == {"Villa": 3, "Salt": 0}


def test_round_robin_coerces_string_points():
    updater = _bare_updater()
    division = {
        "rounds": [
            {"scores": [{"village": "Villa", "points": "4"}, {"village": "Salt", "points": "2"}]},
        ]
    }
    assert updater._calculate_round_robin_raw_scores({}, division) == {"Villa": 3, "Salt": 0}


def test_round_robin_skips_rounds_with_invalid_entries():
    updater = _bare_updater()
    division = {
        "rounds": [
            {"scores": [{"village": "Villa"}, {"village": "Salt", "points": 2}]},  # missing points
            {"scores": [{"village": "Villa", "points": 3}, {"village": "Salt", "points": 1}]},
        ]
    }
    assert updater._calculate_round_robin_raw_scores({}, division) == {"Villa": 3, "Salt": 0}


def test_round_robin_empty_rounds_returns_empty():
    assert _bare_updater()._calculate_round_robin_raw_scores({}, {"rounds": []}) == {}
    assert _bare_updater()._calculate_round_robin_raw_scores({}, {}) == {}


# ---------- _calculate_score_based_raw_scores ----------

def test_score_based_returns_scores_dict():
    updater = _bare_updater()
    division = {"scores": {"Villa": 10, "Salt": 5}}
    assert updater._calculate_score_based_raw_scores({}, division) == {"Villa": 10, "Salt": 5}


def test_score_based_empty_returns_empty():
    assert _bare_updater()._calculate_score_based_raw_scores({}, {"scores": {}}) == {}
    assert _bare_updater()._calculate_score_based_raw_scores({}, {}) == {}


# ---------- _calculate_division_leaderboard ----------

def test_division_leaderboard_score_based_lower_is_better():
    updater = _bare_updater()
    game_def = {"type": "score-based", "lower_is_better": True}
    division = {
        "scores": {"Villa": 30, "Salt": 10, "Sornico": 20},
        "applied_bonuses": [],
        "applied_penalties": [],
    }
    result = updater._calculate_division_leaderboard(game_def, division)
    # Lower is better → Salt wins
    assert result == {"Salt": 10, "Sornico": 7, "Villa": 5}


def test_division_leaderboard_round_robin_with_bonus():
    updater = _bare_updater()
    game_def = {"type": "round-robin"}
    division = {
        "rounds": [
            {"scores": [{"village": "Villa", "points": 4}, {"village": "Salt", "points": 2}]},
        ],
        "applied_bonuses": [{"village": "Salt", "points": 2}],
        "applied_penalties": [],
    }
    result = updater._calculate_division_leaderboard(game_def, division)
    # Villa wins round (3 raw) → 10 ranking pts; Salt loses (0) → 7 ranking pts; +2 bonus → 9
    assert result == {"Villa": 10, "Salt": 9}


def test_division_leaderboard_unknown_game_type_returns_empty():
    updater = _bare_updater()
    assert updater._calculate_division_leaderboard({"type": "mystery"}, {}) == {}


# ---------- _create_division_leaderboard ----------

def test_create_division_leaderboard_assigns_positions():
    updater = _bare_updater()
    game_def = {"type": "score-based", "lower_is_better": False}
    division = {
        "name": "Maschile",
        "scores": {"Villa": 100, "Salt": 50, "Sornico": 75},
        "applied_bonuses": [],
        "applied_penalties": [],
    }
    result = updater._create_division_leaderboard(game_def, division)
    assert result["name"] == "Maschile"
    # Higher raw → 10/7/5 → Villa(10)=pos1, Sornico(7)=pos2, Salt(5)=pos3
    lb = result["leaderboard"]
    assert lb["Villa"] == {"points": 10, "position": 1}
    assert lb["Sornico"] == {"points": 7, "position": 2}
    assert lb["Salt"] == {"points": 5, "position": 3}


def test_create_division_leaderboard_returns_none_for_empty():
    updater = _bare_updater()
    division = {"scores": {}, "applied_bonuses": [], "applied_penalties": []}
    assert updater._create_division_leaderboard({"type": "score-based"}, division) is None


# ---------- _recalculate_palio_leaderboard ----------

def test_recalculate_sums_overall_leaderboards_per_village():
    updater = _bare_updater()
    leaderboard = {
        "villages": ["Villa", "Salt", "Sornico"],
        "palio_leaderboard": {},
        "game_leaderboards": {
            "G01": {
                "overall_leaderboard": {
                    "Villa": {"points": 10, "position": 1},
                    "Salt": {"points": 7, "position": 2},
                    "Sornico": {"points": 5, "position": 3},
                }
            },
            "G02": {
                "overall_leaderboard": {
                    "Villa": {"points": 5, "position": 3},
                    "Salt": {"points": 10, "position": 1},
                    "Sornico": {"points": 7, "position": 2},
                }
            },
        },
    }
    updater._recalculate_palio_leaderboard(leaderboard)
    pl = leaderboard["palio_leaderboard"]
    # Villa 15, Salt 17, Sornico 12 → Salt 1, Villa 2, Sornico 3
    assert pl["Salt"] == {"points": 17, "position": 1}
    assert pl["Villa"] == {"points": 15, "position": 2}
    assert pl["Sornico"] == {"points": 12, "position": 3}


def test_recalculate_villages_with_no_game_entries_get_zero():
    updater = _bare_updater()
    leaderboard = {
        "villages": ["Villa", "Salt"],
        "palio_leaderboard": {},
        "game_leaderboards": {
            "G01": {"overall_leaderboard": {"Villa": {"points": 10, "position": 1}}},
        },
    }
    updater._recalculate_palio_leaderboard(leaderboard)
    assert leaderboard["palio_leaderboard"]["Salt"] == {"points": 0, "position": 2}
    assert leaderboard["palio_leaderboard"]["Villa"] == {"points": 10, "position": 1}


def test_recalculate_ignores_games_without_overall_leaderboard():
    updater = _bare_updater()
    leaderboard = {
        "villages": ["Villa"],
        "palio_leaderboard": {},
        "game_leaderboards": {
            "G01": {"some_other_shape": True},
        },
    }
    updater._recalculate_palio_leaderboard(leaderboard)
    assert leaderboard["palio_leaderboard"]["Villa"] == {"points": 0, "position": 1}


# ---------- update_leaderboard end-to-end ----------

def test_update_leaderboard_score_based_no_divisions(tmp_path: Path):
    palio = {"games": [{"id": "G01", "name": "Anguria", "type": "score-based", "lower_is_better": False}]}
    status = {
        "game_scores": {
            "G01": {
                "status": "completed",
                "scores": {"Villa": 100, "Salt": 80, "Sornico": 60, "Sottocastello": 40, "Sottomonte": 20},
                "applied_bonuses": [],
                "applied_penalties": [],
            }
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard()

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    g = out["game_leaderboards"]["G01"]
    assert g["game_id"] == "G01"
    assert g["overall_leaderboard"]["Villa"]["points"] == 10
    assert g["overall_leaderboard"]["Sottomonte"]["points"] == 1
    # Palio totals match overall ranking
    assert out["palio_leaderboard"]["Villa"] == {"points": 10, "position": 1}


def test_update_leaderboard_score_based_with_divisions_combines_raw_scores(tmp_path: Path):
    """Divisions are combined by RAW score, then RANKING_POINTS applied to the combined ranking."""
    palio = {"games": [{"id": "G02", "name": "Corsa", "type": "score-based", "lower_is_better": True}]}
    status = {
        "game_scores": {
            "G02": {
                "status": "completed",
                "applied_bonuses": [],
                "applied_penalties": [],
                "divisions": [
                    {
                        "name": "Maschile",
                        "status": "completed",
                        "scores": {"Villa": 30, "Salt": 40},
                        "applied_bonuses": [],
                        "applied_penalties": [],
                    },
                    {
                        "name": "Femminile",
                        "status": "completed",
                        "scores": {"Villa": 20, "Salt": 25},
                        "applied_bonuses": [],
                        "applied_penalties": [],
                    },
                ],
            }
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard()

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    overall = out["game_leaderboards"]["G02"]["overall_leaderboard"]
    # Combined raw: Villa=50, Salt=65 → lower_is_better → Villa first
    assert overall["Villa"] == {"points": 10, "position": 1}
    assert overall["Salt"] == {"points": 7, "position": 2}


def test_update_leaderboard_round_robin(tmp_path: Path):
    palio = {"games": [{"id": "G04", "name": "Scatolone", "type": "round-robin"}]}
    status = {
        "game_scores": {
            "G04": {
                "status": "completed",
                "applied_bonuses": [],
                "applied_penalties": [],
                "rounds": [
                    {"scores": [{"village": "Villa", "points": 3}, {"village": "Salt", "points": 1}]},
                    {"scores": [{"village": "Villa", "points": 2}, {"village": "Sornico", "points": 0}]},
                    {"scores": [{"village": "Salt", "points": 1}, {"village": "Sornico", "points": 1}]},
                ],
            }
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard()

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    overall = out["game_leaderboards"]["G04"]["overall_leaderboard"]
    # Villa: 2 wins = 6 raw; Salt: 1 draw = 1 raw; Sornico: 1 draw = 1 raw
    # Ranking: Villa first → 10; Salt/Sornico tied for 2nd, sort is stable on dict order,
    # so the second-ranked gets 7 and third 5 (we don't test which is which on tie).
    assert overall["Villa"] == {"points": 10, "position": 1}
    other_points = sorted(v["points"] for k, v in overall.items() if k != "Villa")
    assert other_points == [5, 7]


def test_update_leaderboard_skips_non_completed_games(tmp_path: Path):
    palio = {"games": [
        {"id": "G01", "name": "A", "type": "score-based", "lower_is_better": False},
        {"id": "G02", "name": "B", "type": "score-based", "lower_is_better": False},
    ]}
    status = {
        "game_scores": {
            "G01": {
                "status": "completed",
                "scores": {"Villa": 10, "Salt": 5},
                "applied_bonuses": [], "applied_penalties": [],
            },
            "G02": {
                "status": "in-progress",
                "scores": {"Villa": 99, "Salt": 0},
                "applied_bonuses": [], "applied_penalties": [],
            },
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard()

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    assert "G01" in out["game_leaderboards"]
    assert "G02" not in out["game_leaderboards"]


def test_update_leaderboard_specific_game_only_processes_that_game(tmp_path: Path):
    palio = {"games": [
        {"id": "G01", "name": "A", "type": "score-based", "lower_is_better": False},
        {"id": "G02", "name": "B", "type": "score-based", "lower_is_better": False},
    ]}
    status = {
        "game_scores": {
            "G01": {
                "status": "completed",
                "scores": {"Villa": 10, "Salt": 5},
                "applied_bonuses": [], "applied_penalties": [],
            },
            "G02": {
                "status": "completed",
                "scores": {"Villa": 0, "Salt": 99},
                "applied_bonuses": [], "applied_penalties": [],
            },
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    # Pre-populate leaderboard with G01 already there
    seed_lb = _empty_leaderboard()
    updater = _make_updater(tmp_path, palio, status, seed_lb)
    updater.update_leaderboard(specific_game_id="G02")

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    assert "G02" in out["game_leaderboards"]
    # G01 was not in the prior leaderboard and was not requested → should not appear
    assert "G01" not in out["game_leaderboards"]


def test_update_leaderboard_specific_game_skips_when_not_completed(tmp_path: Path):
    palio = {"games": [{"id": "G01", "name": "A", "type": "score-based", "lower_is_better": False}]}
    status = {
        "game_scores": {
            "G01": {"status": "in-progress", "scores": {"Villa": 10}, "applied_bonuses": [], "applied_penalties": []},
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard(specific_game_id="G01")

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    # Output not modified — file stays as the seeded empty leaderboard
    assert out == _empty_leaderboard()


def test_update_leaderboard_applies_game_level_bonuses_after_ranking(tmp_path: Path):
    palio = {"games": [{"id": "G01", "name": "A", "type": "score-based", "lower_is_better": False}]}
    status = {
        "game_scores": {
            "G01": {
                "status": "completed",
                "applied_bonuses": [],
                "applied_penalties": [],
                "divisions": [
                    {
                        "name": "Only",
                        "status": "completed",
                        "scores": {"Villa": 100, "Salt": 50},
                        "applied_bonuses": [],
                        "applied_penalties": [],
                    }
                ],
            }
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    # No game-level bonus → Villa=10, Salt=7
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard()
    out = json.loads((tmp_path / "leaderboard.json").read_text())
    assert out["game_leaderboards"]["G01"]["overall_leaderboard"]["Salt"]["points"] == 7

    # Add a game-level bonus and reload
    status["game_scores"]["G01"]["applied_bonuses"] = [{"village": "Salt", "points": 5, "description": "x"}]
    updater2 = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater2.update_leaderboard()
    out2 = json.loads((tmp_path / "leaderboard.json").read_text())
    assert out2["game_leaderboards"]["G01"]["overall_leaderboard"]["Salt"]["points"] == 12


def test_update_leaderboard_creates_file_when_missing(tmp_path: Path):
    palio = {"games": [{"id": "G01", "name": "A", "type": "score-based", "lower_is_better": False}]}
    status = {
        "game_scores": {
            "G01": {
                "status": "completed",
                "scores": {"Villa": 10, "Salt": 5},
                "applied_bonuses": [], "applied_penalties": [],
            },
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    # No leaderboard seed
    updater = _make_updater(tmp_path, palio, status, leaderboard=None)
    updater.update_leaderboard()

    assert (tmp_path / "leaderboard.json").exists()
    out = json.loads((tmp_path / "leaderboard.json").read_text())
    assert out["villages"] == []  # No prior villages list
    assert "G01" in out["game_leaderboards"]


def test_update_leaderboard_output_passes_pydantic_validation(tmp_path: Path):
    """The serialized leaderboard must round-trip through the Leaderboard model."""
    from palio_bot.models.leaderboard_models import Leaderboard

    palio = {"games": [{"id": "G01", "name": "A", "type": "score-based", "lower_is_better": False}]}
    status = {
        "game_scores": {
            "G01": {
                "status": "completed",
                "scores": {"Villa": 10, "Salt": 5},
                "applied_bonuses": [], "applied_penalties": [],
            },
        },
        "last_updated": "2026-04-19T00:00:00Z",
    }
    updater = _make_updater(tmp_path, palio, status, _empty_leaderboard())
    updater.update_leaderboard()

    out = json.loads((tmp_path / "leaderboard.json").read_text())
    Leaderboard.model_validate(out)  # raises if invalid


def test_recalculate_palio_totals_no_file_is_noop(tmp_path: Path):
    palio_path = tmp_path / "palio.json"
    status_path = tmp_path / "status.json"
    leaderboard_path = tmp_path / "lb.json"
    palio_path.write_text("{}")
    status_path.write_text("{}")
    # No leaderboard file
    updater = LeaderboardUpdater(palio_path, status_path, leaderboard_path)
    updater.recalculate_palio_totals()  # must not raise
    assert not leaderboard_path.exists()


def test_recalculate_palio_totals_recomputes_from_existing_games(tmp_path: Path):
    palio_path = tmp_path / "palio.json"
    status_path = tmp_path / "status.json"
    leaderboard_path = tmp_path / "lb.json"
    palio_path.write_text("{}")
    status_path.write_text("{}")
    leaderboard_path.write_text(json.dumps({
        "villages": ["Villa", "Salt"],
        "palio_leaderboard": {
            "Villa": {"points": 999, "position": 99},  # stale
            "Salt": {"points": 999, "position": 99},
        },
        "game_leaderboards": {
            "G01": {
                "game_id": "G01",
                "game_name": "A",
                "divisions": [],
                "overall_leaderboard": {
                    "Villa": {"points": 10, "position": 1},
                    "Salt": {"points": 7, "position": 2},
                },
            }
        },
    }))
    updater = LeaderboardUpdater(palio_path, status_path, leaderboard_path)
    updater.recalculate_palio_totals()

    out = json.loads(leaderboard_path.read_text())
    assert out["palio_leaderboard"]["Villa"] == {"points": 10, "position": 1}
    assert out["palio_leaderboard"]["Salt"] == {"points": 7, "position": 2}
