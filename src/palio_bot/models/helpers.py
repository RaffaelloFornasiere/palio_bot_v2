from typing import List, Union

from .game_status_models import (
    GameBonus,
    GamePenalty,
    RoundRobinGameStatus,
    ScoreBasedGameStatus,
    ScorePenalty,
)


# Helper functions for working with the models



def create_score_penalty(village: str, description: str, points: Union[int, float]) -> ScorePenalty:
    """Create a score penalty with validation. Stored as a positive magnitude."""
    return ScorePenalty(village=village, description=description, points=abs(points))


def create_game_penalty(village: str, description: str, points: int) -> GamePenalty:
    """Create a game penalty with validation. Stored as a positive magnitude."""
    return GamePenalty(village=village, description=description, points=abs(points))


def create_game_bonus(village: str, description: str, points: int) -> GameBonus:
    """Create a game bonus with validation."""
    return GameBonus(village=village, description=description, points=abs(points))


def calculate_adjusted_score(base_score: Union[int, float], score_penalties: List[ScorePenalty], village: str) -> float:
    """Calculate adjusted score (base score minus score penalties) for ranking purposes."""
    total = float(base_score)
    for penalty in score_penalties:
        if penalty.village == village:
            total -= abs(penalty.points)
    return total


def calculate_final_leaderboard_points(leaderboard_points: int, bonuses: List[GameBonus], penalties: List[GamePenalty], village: str) -> int:
    """Calculate final leaderboard points after applying game bonuses/penalties."""
    total = leaderboard_points

    for bonus in bonuses:
        if bonus.village == village:
            total += abs(bonus.points)

    for penalty in penalties:
        if penalty.village == village:
            total -= abs(penalty.points)

    return max(0, total)


def calculate_division_adjusted_score(division: Division, village: str) -> float:
    """Calculate adjusted score for a village in a division (for ranking)."""
    if village not in division.scores:
        return 0.0

    return calculate_adjusted_score(division.scores[village], division.score_penalties, village)


def calculate_round_robin_adjusted_score(game_status: RoundRobinGameStatus, village: str) -> float:
    """Calculate adjusted score for a village in a round-robin game (for ranking)."""
    base_score = 0.0

    if game_status.rounds:
        for round_data in game_status.rounds:
            if village in round_data.scores:
                base_score += round_data.scores[village]

            for penalty in round_data.score_penalties:
                if penalty.village == village:
                    base_score -= abs(penalty.points)

    return base_score


def calculate_score_based_adjusted_score(game_status: ScoreBasedGameStatus, village: str) -> float:
    """Calculate adjusted score for a village in a score-based game (for ranking)."""
    base_score = 0.0

    if village in game_status.scores:
        base_score += game_status.scores[village]

    for penalty in game_status.score_penalties:
        if penalty.village == village:
            base_score -= abs(penalty.points)

    return base_score

