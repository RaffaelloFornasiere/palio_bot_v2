from datetime import datetime
from typing import List, Dict, Optional, Union, Literal
from pydantic import BaseModel


class GameResult(BaseModel):
    """Individual game result for a village."""
    village: str
    score: Union[int, float]
    position: Optional[int] = None


class DivisionLeaderboard(BaseModel):
    """Leaderboard for a specific division within a game."""
    name: str
    results: List[GameResult]
    points: Dict[str, int]  # village -> points earned
    completed: bool = False
    updated_at: Optional[datetime] = None


class GameLeaderboard(BaseModel):
    """Leaderboard for a specific game, with explicit division support."""
    game_id: str
    game_name: str
    divisions: List[DivisionLeaderboard]
    overall_points: Dict[str, int]  # aggregated points across all divisions
    completed: bool = False
    updated_at: Optional[datetime] = None


class Leaderboard(BaseModel):
    """Main leaderboard model with explicit division support."""
    villages: List[str]
    points: Dict[str, int]  # total points across all games
    game_leaderboards: Dict[str, GameLeaderboard]  # game_id -> GameLeaderboard