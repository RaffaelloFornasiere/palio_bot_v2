from datetime import datetime
from typing import List, Dict, Optional, Union, Literal
from pydantic import BaseModel

class Leaderboard(BaseModel):
    """Leaderboard model."""
    villages: List[str]
    points: Dict[str, int]
    game_leaderboards: Dict[str, Dict[str, Union[int, float]]]


class GameResult(BaseModel):
    """Individual game result for a village."""
    village: str
    score: Union[int, float]
    position: Optional[int] = None


class GameLeaderboard(BaseModel):
    """Leaderboard for a specific game."""
    game_id: str
    game_name: str
    results: List[GameResult]
    completed: bool = False
    updated_at: Optional[datetime] = None