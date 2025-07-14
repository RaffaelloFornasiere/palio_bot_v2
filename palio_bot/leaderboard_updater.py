"""Leaderboard update functionality for the palio competition."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

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
            
            # Load current leaderboard
            with open(self.leaderboard_file_path, 'r', encoding='utf-8') as f:
                leaderboard = json.load(f)
            
            # Process each completed game
            for game_id, game_data in games_status.get('game_scores', {}).items():
                if game_data.get('status') == 'completed':
                    logger.info(f"Processing completed game: {game_id}")
                    
                    # Find game definition
                    game_def = self._find_game_definition(palio_data, game_id)
                    if not game_def:
                        logger.warning(f"Game definition not found for {game_id}")
                        continue
                    
                    # Check if game has divisions
                    if 'divisions' in game_data:
                        # Process each division separately
                        for division in game_data['divisions']:
                            if division.get('status') == 'completed':
                                division_id = f"{game_id}_{division['name']}"
                                logger.info(f"Processing completed division: {division_id}")
                                
                                # Calculate leaderboard for this division
                                division_leaderboard = self._calculate_division_leaderboard(game_def, division)
                                if division_leaderboard:
                                    leaderboard['game_leaderboards'][division_id] = {
                                        'name': f"{game_def['name']} - {division['name']}",
                                        'leaderboard': division_leaderboard
                                    }
                    else:
                        # Traditional game without divisions
                        game_leaderboard = self._calculate_game_leaderboard(game_def, game_data)
                        if game_leaderboard:
                            leaderboard['game_leaderboards'][game_id] = {
                                'name': game_def['name'],
                                'leaderboard': game_leaderboard
                            }
            
            # Recalculate total points
            self._recalculate_total_points(leaderboard)
            
            # Save updated leaderboard
            with open(self.leaderboard_file_path, 'w', encoding='utf-8') as f:
                json.dump(leaderboard, f, ensure_ascii=False, indent=2)
            
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
        
        if game_type == 'round-robin':
            return self._calculate_round_robin_leaderboard(game_def, division_data)
        elif game_type == 'score-based':
            return self._calculate_score_based_leaderboard(game_def, division_data)
        else:
            logger.warning(f"Unknown game type: {game_type}")
            return {}
    
    def _calculate_round_robin_leaderboard(self, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard for round-robin games."""
        logger.info(f"Calculating round-robin leaderboard for {game_def['name']}")
        
        # Initialize village points
        village_points = {}
        rounds = game_data.get('rounds', [])
        
        for round_data in rounds:
            villages = list(round_data.keys())
            if len(villages) != 2:
                logger.warning(f"Round with {len(villages)} villages, expected 2")
                continue
            
            village1, village2 = villages
            score1 = round_data[village1]
            score2 = round_data[village2]
            
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
        
        # Sort villages by points to create final ranking
        sorted_villages = sorted(village_points.items(), key=lambda x: x[1], reverse=True)
        
        # Assign final leaderboard points based on ranking
        final_leaderboard = {}
        for rank, (village, _) in enumerate(sorted_villages, 1):
            final_leaderboard[village] = self.RANKING_POINTS.get(rank, 0)
        
        logger.info(f"Round-robin leaderboard: {final_leaderboard}")
        return final_leaderboard
    
    def _calculate_score_based_leaderboard(self, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard for score-based games."""
        logger.info(f"Calculating score-based leaderboard for {game_def['name']}")
        
        scores = game_data.get('scores', {})
        if not scores:
            logger.warning("No scores found in game data")
            return {}
        
        # Check if lower scores are better
        lower_is_better = game_def.get('lower_is_better', False)
        
        # Sort villages by score
        sorted_villages = sorted(scores.items(), key=lambda x: x[1], reverse=not lower_is_better)
        
        # Assign final leaderboard points based on ranking
        final_leaderboard = {}
        for rank, (village, score) in enumerate(sorted_villages, 1):
            final_leaderboard[village] = self.RANKING_POINTS.get(rank, 0)
        
        logger.info(f"Score-based leaderboard: {final_leaderboard}")
        return final_leaderboard
    
    def _recalculate_total_points(self, leaderboard: Dict[str, Any]) -> None:
        """Recalculate total points for each village."""
        logger.info("Recalculating total points")
        
        # Initialize total points
        total_points = {village: 0 for village in leaderboard.get('villages', [])}
        
        # Sum points from all games
        for game_id, game_data in leaderboard.get('game_leaderboards', {}).items():
            game_leaderboard = game_data.get('leaderboard', {})
            for village, points in game_leaderboard.items():
                if village in total_points:
                    total_points[village] += points
        
        # Update leaderboard
        leaderboard['points'] = total_points
        logger.info(f"Total points updated: {total_points}")