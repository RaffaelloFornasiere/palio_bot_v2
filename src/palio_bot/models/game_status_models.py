"""Pydantic models for palio_games_status.json structure."""

from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ScorePenalty(BaseModel):
    """A penalty applied to raw scores/rounds that affects ranking."""
    village: str = Field(..., description="The village receiving the penalty")
    description: str = Field(..., description="Description of the penalty")
    points: int | float = Field(..., description="Points deducted from raw score (negative number)")


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

class RoundRobinScore(BaseModel):
    """A score for a village in a round-robin game."""
    village: str = Field(..., description="The village name")
    points: int | float | str = Field(..., description="Points scored by the village in this round")

class GameRound(BaseModel):
    """A single round in a round-robin game."""
    scores: List[RoundRobinScore] = Field(default=[], description="Village scores in this round")
    score_penalties: List[ScorePenalty] = Field(default_factory=list, description="Score penalties applied in this round")
    
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


class ScoreBasedDivision(BaseModel):
    """A division within a game (e.g., Maschile, Femminile)."""
    name: str = Field(..., description="Division name")
    status: str = Field(..., description="Division status (not-started, in-progress, completed)")
    scores: Dict[str, int | float | str] = Field(default_factory=dict, description="Village scores in this division")
    
    # Score penalties affect ranking within the division
    score_penalties: List[ScorePenalty] = Field(default_factory=list, description="Score penalties applied in this division")
    
    # Game bonuses/penalties affect final leaderboard points
    applied_bonuses: List[GameBonus] = Field(default_factory=list, description="Game bonuses applied in this division")
    applied_penalties: List[GamePenalty] = Field(default_factory=list, description="Game penalties applied in this division")


class RoundRobinDivision(BaseModel):
    """A division within a game (e.g., Maschile, Femminile)."""
    name: str = Field(..., description="Division name")
    status: str = Field(..., description="Division status (not-started, in-progress, completed)")
    rounds: Optional[List[GameRound]] =  Field(default_factory=dict, description="Village rounds in this division")

    # Game bonuses/penalties affect final leaderboard points
    applied_bonuses: List[GameBonus] = Field(default_factory=list, description="Game bonuses applied in this division")
    applied_penalties: List[GamePenalty] = Field(default_factory=list, description="Game penalties applied in this division")



class ScoreBasedGameStatus(BaseModel):
    """Status of a score-based game."""
    status: str = Field(..., description="Game status (not-started, in-progress, completed)")
    scores: Dict[str, int | float | str] = Field(default_factory=dict, description="Village scores")

    # For games with divisions
    divisions: Optional[List[ScoreBasedDivision]] = Field(None, description="Game divisions")

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
    divisions: Optional[List[RoundRobinDivision]] = Field(None, description="Game divisions")
    
    # Game bonuses/penalties affect final leaderboard points (applied after ranking)
    applied_bonuses: List[GameBonus] = Field(default_factory=list, description="Game-level bonuses")
    applied_penalties: List[GamePenalty] = Field(default_factory=list, description="Game-level penalties")


class PalioGamesStatus(BaseModel):
    """Complete structure for palio_games_status.json."""
    game_scores: Dict[str, ScoreBasedGameStatus | RoundRobinGameStatus] = Field(..., description="Status of all games by game ID")
    last_updated: str = Field(..., description="ISO timestamp of last update")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }



def extract_model_docs():
    """Generate JSON schema-like structure for system prompt."""
    models = [
        PalioGamesStatus,
        RoundRobinGameStatus,
        ScoreBasedGameStatus,
        RoundRobinDivision,
        ScoreBasedDivision,
        GameRound,
        ScorePenalty,
        GamePenalty,
        GameBonus
    ]
    
    # Add overview
    prompt_section = ""
    
    for model in models:
        prompt_section += f"## {model.__name__}\n"
        
        # Add docstring if available
        if model.__doc__:
            prompt_section += f"{model.__doc__.strip()}\n"
        
        # Generate JSON schema-like structure
        prompt_section += "```json\n{\n"
        
        if hasattr(model, 'model_fields'):
            for field_name, field_info in model.model_fields.items():
                # Get field type in a clean format
                field_type = str(field_info.annotation).replace('typing.', '').replace('Union', '').replace('[', '').replace(']', '')
                
                # Get field description
                description = ""
                if hasattr(field_info, 'description') and field_info.description:
                    description = f" // {field_info.description}"
                
                # Format based on type
                if 'List' in str(field_info.annotation):
                    prompt_section += f'  "{field_name}": []{description}\n'
                elif 'Dict' in str(field_info.annotation):
                    prompt_section += f'  "{field_name}": {{}}{description}\n'
                elif 'Optional' in str(field_info.annotation):
                    prompt_section += f'  "{field_name}": null{description}\n'
                elif 'str' in field_type:
                    prompt_section += f'  "{field_name}": "string"{description}\n'
                elif 'int' in field_type or 'float' in field_type:
                    prompt_section += f'  "{field_name}": 0{description}\n'
                else:
                    prompt_section += f'  "{field_name}": "{field_type}"{description}\n'
        
        prompt_section += "}\n```\n\n"
    
    return prompt_section


if __name__ == "__main__":
    # Print the extracted model documentation
    print(extract_model_docs())