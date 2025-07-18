from datetime import datetime
from typing import List, Dict, Optional, Union, Literal
from pydantic import BaseModel, Field

class LeaderboardEntry(BaseModel):
    points: int
    position: int


class DivisionLeaderboard(BaseModel):
    """Leaderboard for a specific division within a game."""
    name: str
    leaderboard: Dict[str, int] # village -> position
    updated_at: Optional[datetime] = None


class GameLeaderboard(BaseModel):
    """Leaderboard for a specific game, with explicit division support."""
    game_id: str
    game_name: str
    divisions: List[DivisionLeaderboard]
    overall_leaderboard: Dict[str, LeaderboardEntry] # village -> LeaderboardEntry
    updated_at: Optional[datetime] = None


class Leaderboard(BaseModel):
    """Main leaderboard model with explicit division support."""
    villages: List[str]
    palio_leaderboard: Dict[str, LeaderboardEntry] # village -> LeaderboardEntry
    game_leaderboards: Dict[str, GameLeaderboard]  # game_id -> GameLeaderboard