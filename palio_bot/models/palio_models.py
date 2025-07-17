from datetime import datetime
from typing import List, Dict, Optional, Union, Literal
from pydantic import BaseModel


class EventDate(BaseModel):
    """Date and time information for a game event."""
    start_datetime: datetime
    end_datetime: datetime
    subtitle: Optional[str] = None


class Game(BaseModel):
    """Game model representing a single game in the palio."""
    id: str
    name: str
    type: Literal["score-based", "round-robin", "points-based"]
    description: str
    measure_unit: str
    lower_is_better: bool
    dates: List[EventDate]


class NonGameEvent(BaseModel):
    """Non-game event model."""
    name: str
    type: str
    dates: List[EventDate]


class PalioData(BaseModel):
    """Complete palio data model."""
    competition_name: str
    villages: List[str]
    games: List[Game]
    non_game_events: List[NonGameEvent]


