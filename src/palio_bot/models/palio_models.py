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
    type: Literal["score-based", "round-robin"]
    description: str
    measure_unit: str
    lower_is_better: bool
    dates: List[EventDate]
    # Semantics of `divisions` for this game (when the status carries any):
    #   false (default) → divisions are independent contests; the game's
    #     overall points are the SUM of each village's per-division ranking
    #     points (e.g. 1° Maschile + 3° Femminile = 10 + 5 = 15).
    #   true → divisions are stages of one combined contest; raw scores are
    #     summed across divisions, then re-ranked for the game.
    combine_divisions: bool = False


class NonGameEvent(BaseModel):
    """Non-game event model."""
    name: str
    type: str
    dates: List[EventDate]


class PalioData(BaseModel):
    """Complete palio data model."""
    competition_name: str
    villages: List[str]
    villages_colors: Dict[str, str]
    games: List[Game]
    non_game_events: List[NonGameEvent]


