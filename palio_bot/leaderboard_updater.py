"""Leaderboard update functionality for the palio competition."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .models.leaderboard_models import Leaderboard, GameLeaderboard, DivisionLeaderboard

logger = logging.getLogger(__name__)


class LeaderboardUpdater:
    """Updates the leaderboard.json based on completed games."""
    
    def __init__(self, palio_file_path: Path, palio_games_status_path: Path, leaderboard_file_path: Path):
        self.palio_file_path = palio_file_path
        self.palio_games_status_path = palio_games_status_path
        self.leaderboard_file_path = leaderboard_file_path
        
        # Point distribution for final rankings
        self.RANKING_POINTS = {
            1: 10,
            2: 7,
            3: 5,
            4: 3,
            5: 1
        }
    
    def update_leaderboard(self) -> None:
        """Update the leaderboard with all completed games."""
        logger.info("Starting leaderboard update")
        
        try:
            # Load game definitions
            with open(self.palio_file_path, 'r', encoding='utf-8') as f:
                palio_data = json.load(f)
            
            # Load game status
            with open(self.palio_games_status_path, 'r', encoding='utf-8') as f:
                games_status = json.load(f)
            
            # Load current leaderboard or create new structure
            if self.leaderboard_file_path.exists():
                with open(self.leaderboard_file_path, 'r', encoding='utf-8') as f:
                    old_leaderboard = json.load(f)
                    # Create new structure from old data
                    leaderboard = {
                        'villages': old_leaderboard.get('villages', []),
                        'palio_leaderboard': {},
                        'game_leaderboards': {}  # Will be rebuilt from scratch
                    }
            else:
                leaderboard = {
                    'villages': [],
                    'palio_leaderboard': {},
                    'game_leaderboards': {}
                }
            
            # Process each completed game
            for game_id, game_data in games_status.get('game_scores', {}).items():
                if game_data.get('status') == 'completed':
                    logger.info(f"Processing completed game: {game_id}")
                    
                    # Find game definition
                    game_def = self._find_game_definition(palio_data, game_id)
                    if not game_def:
                        logger.warning(f"Game definition not found for {game_id}")
                        continue
                    
                    # Create GameLeaderboard for this game
                    game_leaderboard = self._create_game_leaderboard(game_id, game_def, game_data)
                    if game_leaderboard:
                        leaderboard['game_leaderboards'][game_id] = game_leaderboard
            
            # Recalculate total points and positions
            self._recalculate_palio_leaderboard(leaderboard)
            
            # Convert to Pydantic model for validation
            leaderboard_obj = Leaderboard.model_validate(leaderboard)
            # Convert back to dict for JSON serialization
            leaderboard = leaderboard_obj.model_dump()
            
            # Save updated leaderboard
            with open(self.leaderboard_file_path, 'w', encoding='utf-8') as f:
                json.dump(leaderboard, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info("Leaderboard update completed successfully")
            
        except Exception as e:
            logger.error(f"Error updating leaderboard: {e}")
            raise
    
    def _find_game_definition(self, palio_data: Dict[str, Any], game_id: str) -> Optional[Dict[str, Any]]:
        """Find game definition by ID."""
        for game in palio_data.get('games', []):
            if game.get('id') == game_id:
                return game
        return None
    
    def _create_game_leaderboard(self, game_id: str, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a GameLeaderboard structure for a game."""
        divisions = []
        overall_leaderboard = {}
        
        if 'divisions' in game_data:
            # Process each division separately
            overall_raw_scores = {}
            
            for division in game_data['divisions']:
                if division.get('status') == 'completed':
                    division_leaderboard = self._create_division_leaderboard(game_def, division)
                    if division_leaderboard:
                        divisions.append(division_leaderboard)
                        
                        # Add division RAW SCORES (not ranking points) to overall
                        division_raw_scores = self._calculate_division_raw_scores(game_def, division)
                        for village, score in division_raw_scores.items():
                            overall_raw_scores[village] = overall_raw_scores.get(village, 0) + score
            
            # Re-rank based on combined raw scores and apply RANKING_POINTS
            if overall_raw_scores:
                ranking_points = self._apply_ranking_points(game_def, overall_raw_scores)
                # Apply game-level bonuses and penalties
                final_points = self._apply_bonuses_and_penalties(game_data, ranking_points)
                # Convert to LeaderboardEntry format
                sorted_villages = sorted(final_points.items(), key=lambda x: x[1], reverse=True)
                for position, (village, points) in enumerate(sorted_villages, 1):
                    overall_leaderboard[village] = {
                        'points': points,
                        'position': position
                    }
        else:
            # Traditional game without divisions - create a single "Main" division
            main_division = self._create_division_leaderboard(game_def, game_data, division_name="Main")
            if main_division:
                divisions.append(main_division)
                # Convert division points to LeaderboardEntry format
                division_points = main_division['points']
                sorted_villages = sorted(division_points.items(), key=lambda x: x[1], reverse=True)
                for position, (village, points) in enumerate(sorted_villages, 1):
                    overall_leaderboard[village] = {
                        'points': points,
                        'position': position
                    }
        
        if not divisions:
            return None
            
        return {
            'game_id': game_id,
            'game_name': game_def['name'],
            'divisions': divisions,
            'overall_leaderboard': overall_leaderboard,
            'completed': True,
            'updated_at': datetime.now().isoformat()
        }
    
    def _create_division_leaderboard(self, game_def: Dict[str, Any], division_data: Dict[str, Any], division_name: str = None) -> Dict[str, Any]:
        """Create a DivisionLeaderboard structure for a division."""
        name = division_name or division_data.get('name', 'Main')
        
        # Calculate points for this division
        points = self._calculate_division_leaderboard(game_def, division_data)
        if not points:
            return None
        
        # Sort villages by points and create position mapping
        sorted_villages = sorted(points.items(), key=lambda x: x[1], reverse=True)
        leaderboard = {}
        for position, (village, _) in enumerate(sorted_villages, 1):
            leaderboard[village] = position
        
        return {
            'name': name,
            'leaderboard': leaderboard,
            'points': points,  # Keep for internal calculations
            'updated_at': datetime.now().isoformat()
        }
    
    def _calculate_game_leaderboard(self, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard points for a specific game."""
        game_type = game_def.get('type')
        
        if game_type == 'round-robin':
            return self._calculate_round_robin_leaderboard(game_def, game_data)
        elif game_type == 'score-based':
            return self._calculate_score_based_leaderboard(game_def, game_data)
        else:
            logger.warning(f"Unknown game type: {game_type}")
            return {}
    
    def _calculate_division_leaderboard(self, game_def: Dict[str, Any], division_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard points for a specific division."""
        game_type = game_def.get('type')
        
        # Calculate base ranking points
        if game_type == 'round-robin':
            base_points = self._calculate_round_robin_leaderboard(game_def, division_data)
        elif game_type == 'score-based':
            base_points = self._calculate_score_based_leaderboard(game_def, division_data)
        else:
            logger.warning(f"Unknown game type: {game_type}")
            return {}
        
        # Apply bonuses and penalties
        final_points = self._apply_bonuses_and_penalties(division_data, base_points)
        
        return final_points
    
    def _calculate_round_robin_leaderboard(self, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard for round-robin games."""
        logger.info(f"Calculating round-robin leaderboard for {game_def['name']}")
        
        # Get raw scores first
        raw_scores = self._calculate_round_robin_raw_scores(game_def, game_data)
        
        # Apply ranking points
        return self._apply_ranking_points(game_def, raw_scores)
    
    def _calculate_score_based_leaderboard(self, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard for score-based games."""
        logger.info(f"Calculating score-based leaderboard for {game_def['name']}")
        
        # Get raw scores first
        raw_scores = self._calculate_score_based_raw_scores(game_def, game_data)
        
        # Apply ranking points
        return self._apply_ranking_points(game_def, raw_scores)
    
    def _calculate_division_raw_scores(self, game_def: Dict[str, Any], division_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate raw scores for a division (before applying RANKING_POINTS)."""
        game_type = game_def.get('type')
        
        if game_type == 'round-robin':
            return self._calculate_round_robin_raw_scores(game_def, division_data)
        elif game_type == 'score-based':
            return self._calculate_score_based_raw_scores(game_def, division_data)
        else:
            logger.warning(f"Unknown game type: {game_type}")
            return {}
    
    def _calculate_round_robin_raw_scores(self, game_def: Dict[str, Any], division_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate raw scores for round-robin games (total wins/points)."""
        village_points = {}
        rounds = division_data.get('rounds', [])
        
        for round_data in rounds:
            scores = round_data.get('scores', {})
            villages = list(scores.keys())
            if len(villages) != 2:
                logger.warning(f"Round with {len(villages)} villages, expected 2")
                continue
            
            village1, village2 = villages
            score1 = scores[village1]
            score2 = scores[village2]
            
            # Initialize if not exists
            if village1 not in village_points:
                village_points[village1] = 0
            if village2 not in village_points:
                village_points[village2] = 0
            
            # Award points based on round result
            if score1 > score2:
                village_points[village1] += 3  # Winner gets 3 points
                village_points[village2] += 0  # Loser gets 0 points
            elif score2 > score1:
                village_points[village2] += 3  # Winner gets 3 points
                village_points[village1] += 0  # Loser gets 0 points
            else:
                # Tie - both get 1 point
                village_points[village1] += 1
                village_points[village2] += 1
        
        return village_points
    
    def _calculate_score_based_raw_scores(self, game_def: Dict[str, Any], division_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate raw scores for score-based games."""
        scores = division_data.get('scores', {})
        if not scores:
            logger.warning("No scores found in division data")
            return {}
        
        # Return the raw scores directly
        return scores
    
    def _apply_ranking_points(self, game_def: Dict[str, Any], raw_scores: Dict[str, Any]) -> Dict[str, int]:
        """Apply RANKING_POINTS to raw scores after ranking."""
        if not raw_scores:
            return {}
        
        # Check if lower scores are better (for score-based games)
        lower_is_better = game_def.get('lower_is_better', False)
        
        # Sort villages by raw score
        sorted_villages = sorted(raw_scores.items(), key=lambda x: x[1], reverse=not lower_is_better)
        
        # Assign final leaderboard points based on ranking
        final_leaderboard = {}
        for rank, (village, _) in enumerate(sorted_villages, 1):
            final_leaderboard[village] = self.RANKING_POINTS.get(rank, 0)
        
        logger.info(f"Applied ranking points: {final_leaderboard}")
        return final_leaderboard
    
    def _apply_bonuses_and_penalties(self, game_data: Dict[str, Any], leaderboard_points: Dict[str, int]) -> Dict[str, int]:
        """Apply bonuses and penalties to leaderboard points."""
        if not leaderboard_points:
            return {}
        
        # Create a copy to avoid modifying the original
        final_points = leaderboard_points.copy()
        
        # Apply bonuses
        for bonus in game_data.get('applied_bonuses', []):
            village = bonus.get('village')
            bonus_points = bonus.get('points', 0)
            if village in final_points:
                final_points[village] += bonus_points
                logger.info(f"Applied bonus to {village}: +{bonus_points} points (reason: {bonus.get('description', 'No description')})")
        
        # Apply penalties
        for penalty in game_data.get('applied_penalties', []):
            village = penalty.get('village')
            penalty_points = penalty.get('points', 0)
            if village in final_points:
                final_points[village] += penalty_points  # penalties are negative numbers
                logger.info(f"Applied penalty to {village}: {penalty_points} points (reason: {penalty.get('description', 'No description')})")
        
        return final_points
    
    def _recalculate_palio_leaderboard(self, leaderboard: Dict[str, Any]) -> None:
        """Recalculate total points and positions for each village."""
        logger.info("Recalculating palio leaderboard")
        
        # Initialize total points
        total_points = {village: 0 for village in leaderboard.get('villages', [])}
        
        # Sum points from all games
        for game_id, game_data in leaderboard.get('game_leaderboards', {}).items():
            # Handle new GameLeaderboard structure
            if isinstance(game_data, dict) and 'overall_leaderboard' in game_data:
                for village, entry in game_data['overall_leaderboard'].items():
                    if village in total_points and isinstance(entry, dict) and 'points' in entry:
                        total_points[village] += entry['points']
        
        # Sort villages by points (descending) and assign positions
        sorted_villages = sorted(total_points.items(), key=lambda x: x[1], reverse=True)
        
        palio_leaderboard = {}
        for position, (village, points) in enumerate(sorted_villages, 1):
            palio_leaderboard[village] = {
                'points': points,
                'position': position
            }
        
        # Update leaderboard
        leaderboard['palio_leaderboard'] = palio_leaderboard
        logger.info(f"Palio leaderboard updated: {palio_leaderboard}")