"""Pydantic models for palio_games_status.json structure."""

from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ScorePenalty(BaseModel):
    """A penalty applied to raw scores/rounds that affects ranking."""
    village: str = Field(..., description="The village receiving the penalty")
    description: str = Field(..., description="Description of the penalty")
    points: Union[int, float] = Field(..., description="Points deducted from raw score (negative number)")


class GamePenalty(BaseModel):
    """A penalty applied to final leaderboard points after ranking."""
    village: str = Field(..., description="The village receiving the penalty")
    description: str = Field(..., description="Description of the penalty")
    points: int = Field(..., description="Points deducted from leaderboard points (negative number)")


class GameBonus(BaseModel):
    """A bonus applied to final leaderboard points after ranking."""
    village: str = Field(..., description="The village receiving the bonus")
    description: str = Field(..., description="Description of the bonus")
    points: int = Field(..., description="Points awarded to leaderboard points (positive number)")


class GameRound(BaseModel):
    """A single round in a round-robin game."""
    # Dynamic fields for village scores (e.g., "Villa": 5, "Sottocastello": 8)
    # Using Dict to allow flexible village names
    scores: Dict[str, Union[int, float]] = Field(default_factory=dict)
    score_penalties: List[ScorePenalty] = Field(default_factory=list, description="Score penalties applied in this round")
    
    def __init__(self, **data):
        # Separate scores from penalties
        score_penalties = data.pop('score_penalties', [])
        # Support legacy 'penalties' field
        legacy_penalties = data.pop('penalties', [])
        if legacy_penalties:
            score_penalties.extend(legacy_penalties)
        scores = {k: v for k, v in data.items() if k not in ['score_penalties', 'penalties']}
        super().__init__(scores=scores, score_penalties=score_penalties)
    
    def __getitem__(self, key):
        """Allow dict-like access to scores."""
        return self.scores[key]
    
    def __setitem__(self, key, value):
        """Allow dict-like assignment to scores."""
        self.scores[key] = value
    
    def keys(self):
        """Return score keys for dict-like iteration."""
        return self.scores.keys()
    
    def items(self):
        """Return score items for dict-like iteration."""
        return self.scores.items()


class Division(BaseModel):
    """A division within a game (e.g., Maschile, Femminile)."""
    name: str = Field(..., description="Division name")
    status: str = Field(..., description="Division status (not-started, in-progress, completed)")
    scores: Dict[str, Union[int, float]] = Field(default_factory=dict, description="Village scores in this division")
    
    # Score penalties affect ranking within the division
    score_penalties: List[ScorePenalty] = Field(default_factory=list, description="Score penalties applied in this division")
    
    # Game bonuses/penalties affect final leaderboard points
    applied_bonuses: List[GameBonus] = Field(default_factory=list, description="Game bonuses applied in this division")
    applied_penalties: List[GamePenalty] = Field(default_factory=list, description="Game penalties applied in this division")


class ScoreBasedGameStatus(BaseModel):
    """Status of a score-based game."""
    status: str = Field(..., description="Game status (not-started, in-progress, completed)")
    scores: Dict[str, Union[int, float]] = Field(default_factory=dict, description="Village scores")

    # For games with divisions
    divisions: Optional[List[Division]] = Field(None, description="Game divisions")

    # Score penalties affect ranking
    score_penalties: List[ScorePenalty] = Field(default_factory=list, description="Score penalties for score-based games")

    # Game bonuses/penalties affect final leaderboard points
    applied_bonuses: List[GameBonus] = Field(default_factory=list, description="Game-level bonuses")
    applied_penalties: List[GamePenalty] = Field(default_factory=list, description="Game-level penalties")


class RoundRobinGameStatus(BaseModel):
    """Status of a single game."""
    status: str = Field(..., description="Game status (not-started, in-progress, completed)")
    
    # For round-robin games
    rounds: Optional[List[GameRound]] = Field(None, description="Game rounds (for round-robin games)")
    
    # For games with divisions
    divisions: Optional[List[Division]] = Field(None, description="Game divisions")
    
    # Game bonuses/penalties affect final leaderboard points (applied after ranking)
    applied_bonuses: List[GameBonus] = Field(default_factory=list, description="Game-level bonuses")
    applied_penalties: List[GamePenalty] = Field(default_factory=list, description="Game-level penalties")


class PalioGamesStatus(BaseModel):
    """Complete structure for palio_games_status.json."""
    game_scores: Dict[str, Union[ScoreBasedGameStatus, RoundRobinGameStatus]] = Field(..., description="Status of all games by game ID")
    last_updated: str = Field(..., description="ISO timestamp of last update")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }


