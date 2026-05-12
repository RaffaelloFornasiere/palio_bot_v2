"""Leaderboard update functionality for the palio competition."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .models.leaderboard_models import Leaderboard, GameLeaderboard, DivisionLeaderboard

logger = logging.getLogger(__name__)


def _strip_timestamps(game_lb: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a copy of a game_leaderboard entry with `updated_at` removed
    (top-level and per-division). Used to compare semantic content while
    ignoring auto-bumped timestamps."""
    if not isinstance(game_lb, dict):
        return game_lb
    out = {k: v for k, v in game_lb.items() if k != 'updated_at'}
    divs = out.get('divisions')
    if isinstance(divs, list):
        out['divisions'] = [
            {dk: dv for dk, dv in d.items() if dk != 'updated_at'} if isinstance(d, dict) else d
            for d in divs
        ]
    return out


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
    
    def compute(self) -> tuple[Dict[str, Any], List[str]]:
        """Compute the proposed leaderboard from current inputs without writing.

        Returns:
            (proposed_leaderboard, changed_game_ids) where `changed_game_ids`
            is the list of game_ids whose semantic content (everything except
            `updated_at`) differs from the entry currently on disk. For games
            whose content is unchanged, the existing timestamps are preserved
            in the proposed output so on-disk leaderboard doesn't churn on
            re-runs.
        """
        with open(self.palio_file_path, 'r', encoding='utf-8') as f:
            palio_data = json.load(f)

        with open(self.palio_games_status_path, 'r', encoding='utf-8') as f:
            games_status = json.load(f)

        # Normalize the old leaderboard through Pydantic so its shape matches
        # what `model_dump()` produces — otherwise default-valued optional
        # fields create cosmetic-only diffs.
        if self.leaderboard_file_path.exists():
            with open(self.leaderboard_file_path, 'r', encoding='utf-8') as f:
                raw_old = json.load(f)
            try:
                old_norm = Leaderboard.model_validate(raw_old).model_dump()
            except Exception:
                old_norm = raw_old
            leaderboard = {
                'villages': old_norm.get('villages', []),
                'palio_leaderboard': {},
                'game_leaderboards': dict(old_norm.get('game_leaderboards', {})),
            }
            old_games = old_norm.get('game_leaderboards', {})
        else:
            leaderboard = {'villages': [], 'palio_leaderboard': {}, 'game_leaderboards': {}}
            old_games = {}

        for game_id, game_data in games_status.get('game_scores', {}).items():
            # A game contributes to the leaderboard if either:
            #   - it has no divisions and its top-level status == 'completed', OR
            #   - it has divisions and at least one of them is 'completed'.
            # The second case lets the leaderboard update incrementally as
            # individual divisions finish, without requiring the user to
            # also flip the top-level status.
            divisions = game_data.get('divisions') or []
            if divisions:
                if not any(
                    isinstance(d, dict) and d.get('status') == 'completed'
                    for d in divisions
                ):
                    continue
            else:
                if game_data.get('status') != 'completed':
                    continue
            game_def = self._find_game_definition(palio_data, game_id)
            if not game_def:
                logger.warning(f"Game definition not found for {game_id}")
                continue
            game_leaderboard = self._create_game_leaderboard(game_id, game_def, game_data)
            if game_leaderboard:
                leaderboard['game_leaderboards'][game_id] = game_leaderboard

        self._recalculate_palio_leaderboard(leaderboard)

        leaderboard_obj = Leaderboard.model_validate(leaderboard)
        leaderboard = leaderboard_obj.model_dump()

        new_games = leaderboard.get('game_leaderboards', {})
        changed_ids: List[str] = []
        for k in sorted(set(old_games) | set(new_games)):
            old = old_games.get(k)
            new = new_games.get(k)
            if _strip_timestamps(old) == _strip_timestamps(new):
                # No semantic change: copy the old timestamps back into the
                # proposed so apply() doesn't bump them for nothing.
                if isinstance(old, dict) and isinstance(new, dict):
                    new['updated_at'] = old.get('updated_at')
                    old_divs = old.get('divisions') or []
                    new_divs = new.get('divisions') or []
                    if len(old_divs) == len(new_divs):
                        for nd, od in zip(new_divs, old_divs):
                            if isinstance(nd, dict) and isinstance(od, dict):
                                nd['updated_at'] = od.get('updated_at')
            else:
                changed_ids.append(k)
        return leaderboard, changed_ids

    def write_leaderboard(self, leaderboard: Dict[str, Any]) -> None:
        """Persist a previously-computed leaderboard to disk."""
        with open(self.leaderboard_file_path, 'w', encoding='utf-8') as f:
            json.dump(leaderboard, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Leaderboard written to disk")

    def update_leaderboard(self, specific_game_id: str = None) -> None:
        """Compute and write in one shot. Kept for explicit triggers (CLI)."""
        if specific_game_id:
            logger.warning("specific_game_id is no longer honored; recomputing all")
        try:
            new_leaderboard, _ = self.compute()
            self.write_leaderboard(new_leaderboard)
            logger.info("Leaderboard update completed successfully")
        except Exception as e:
            logger.error(f"Error updating leaderboard: {e}")
            raise
    
    def recalculate_palio_totals(self) -> None:
        """Recalculate only the palio_leaderboard totals from existing game_leaderboards.
        
        This method doesn't recompute individual games, it just sums up the points
        from the existing game_leaderboards and updates the palio_leaderboard.
        """
        logger.info("Recalculating palio leaderboard totals from existing games")
        
        try:
            # Load current leaderboard
            if not self.leaderboard_file_path.exists():
                logger.warning("Leaderboard file doesn't exist, nothing to recalculate")
                return
                
            with open(self.leaderboard_file_path, 'r', encoding='utf-8') as f:
                leaderboard = json.load(f)
            
            # Recalculate total points and positions from existing game data
            self._recalculate_palio_leaderboard(leaderboard)
            
            # Convert to Pydantic model for validation
            leaderboard_obj = Leaderboard.model_validate(leaderboard)
            # Convert back to dict for JSON serialization
            leaderboard = leaderboard_obj.model_dump()
            
            # Save updated leaderboard
            with open(self.leaderboard_file_path, 'w', encoding='utf-8') as f:
                json.dump(leaderboard, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info("Palio leaderboard totals recalculated successfully")
            
        except Exception as e:
            logger.error(f"Error recalculating palio totals: {e}")
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
            combine_divisions = bool(game_def.get('combine_divisions', False))
            # Build per-division leaderboards in either case.
            overall_raw_scores: Dict[str, Any] = {}
            summed_division_points: Dict[str, int] = {}

            for division in game_data['divisions']:
                if division.get('status') != 'completed':
                    continue
                division_leaderboard = self._create_division_leaderboard(game_def, division)
                if not division_leaderboard:
                    continue
                divisions.append(division_leaderboard)

                if combine_divisions:
                    # Stages of one contest → accumulate raw scores for a
                    # single final re-rank across divisions.
                    division_raw_scores = self._calculate_division_raw_scores(game_def, division)
                    for village, score in division_raw_scores.items():
                        overall_raw_scores[village] = overall_raw_scores.get(village, 0) + score
                else:
                    # Independent contests → each village's contribution to
                    # the game is the SUM of its per-division ranking points.
                    for village, entry in division_leaderboard['leaderboard'].items():
                        summed_division_points[village] = (
                            summed_division_points.get(village, 0) + entry['points']
                        )

            if combine_divisions:
                if overall_raw_scores:
                    ranking_points = self._apply_ranking_points(game_def, overall_raw_scores)
                    final_points = self._apply_bonuses_and_penalties(game_data, ranking_points)
                    sorted_villages = sorted(final_points.items(), key=lambda x: x[1], reverse=True)
                    for position, (village, points) in enumerate(sorted_villages, 1):
                        overall_leaderboard[village] = {
                            'points': points,
                            'position': position
                        }
            else:
                if summed_division_points:
                    final_points = self._apply_bonuses_and_penalties(game_data, summed_division_points)
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
            'updated_at': datetime.now().isoformat()
        }
    
    def _create_division_leaderboard(self, game_def: Dict[str, Any], division_data: Dict[str, Any], division_name: str = None) -> Dict[str, Any]:
        """Create a DivisionLeaderboard structure for a division."""
        name = division_name or division_data.get('name', 'Main')
        
        # Calculate points for this division
        points = self._calculate_division_leaderboard(game_def, division_data)
        if not points:
            return None
        
        # Sort villages by points and build LeaderboardEntry dicts
        sorted_villages = sorted(points.items(), key=lambda x: x[1], reverse=True)
        leaderboard = {
            village: {'points': pts, 'position': position}
            for position, (village, pts) in enumerate(sorted_villages, 1)
        }

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
        logger.info(f"Calculating round-robin leaderboard for {game_def.get('name', '<unnamed>')}")
        
        # Get raw scores first
        raw_scores = self._calculate_round_robin_raw_scores(game_def, game_data)
        
        # Apply ranking points
        return self._apply_ranking_points(game_def, raw_scores)
    
    def _calculate_score_based_leaderboard(self, game_def: Dict[str, Any], game_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate leaderboard for score-based games."""
        logger.info(f"Calculating score-based leaderboard for {game_def.get('name', '<unnamed>')}")
        
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
        """Calculate round-robin win totals.

        Expects each round in `rounds` to be:
            { "scores": [ {"village": str, "points": number|str}, ... ] }
        (the `RoundRobinScore` Pydantic shape). Exactly 2 entries per round.
        """
        village_points: Dict[str, int] = {}

        for round_data in division_data.get('rounds', []) or []:
            if not isinstance(round_data, dict):
                logger.warning(f"Skipping non-dict round data: {round_data!r}")
                continue

            scores_list = round_data.get('scores', []) or []
            if not isinstance(scores_list, list) or len(scores_list) != 2:
                logger.warning(
                    f"Round with {len(scores_list) if isinstance(scores_list, list) else '?'} "
                    f"entries, expected a list of 2 (RoundRobinScore objects)"
                )
                continue

            def _unpack(entry: Any) -> Optional[tuple]:
                if not isinstance(entry, dict):
                    return None
                v = entry.get('village')
                p = entry.get('points')
                if not v or p is None:
                    return None
                try:
                    p = float(p) if not isinstance(p, (int, float)) else p
                except (TypeError, ValueError):
                    return None
                return v, p

            a = _unpack(scores_list[0])
            b = _unpack(scores_list[1])
            if a is None or b is None:
                logger.warning(f"Invalid round score entries: {scores_list!r}")
                continue

            (village1, score1), (village2, score2) = a, b
            village_points.setdefault(village1, 0)
            village_points.setdefault(village2, 0)

            if score1 > score2:
                village_points[village1] += 3
            elif score2 > score1:
                village_points[village2] += 3
            else:
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
        
        # Apply penalties. Convention: `points` is a positive magnitude that
        # gets SUBTRACTED. abs() is defensive in case legacy data still has
        # the old signed convention.
        for penalty in game_data.get('applied_penalties', []):
            village = penalty.get('village')
            penalty_points = abs(penalty.get('points', 0))
            if village in final_points:
                final_points[village] -= penalty_points
                logger.info(f"Applied penalty to {village}: -{penalty_points} points (reason: {penalty.get('description', 'No description')})")
        
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