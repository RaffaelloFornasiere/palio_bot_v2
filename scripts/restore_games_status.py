#!/usr/bin/env python3
"""
Restore script for palio_games_status.json and leaderboard.json

This script resets both files:
1. palio_games_status.json: Initializes all games from palio.json with appropriate structure:
   - "rounds" key for round-robin games
   - "scores" key for score-based games
2. leaderboard.json: Resets to clean state with:
   - Villages list from palio.json
   - palio_leaderboard with all villages at 0 points
   - Empty game_leaderboards (ready for divisions support)

Usage:
    python scripts/restore_games_status.py [--backup]
    
Options:
    --backup    Create a backup of the current files before restoring
"""

import json
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

def load_json(file_path: Path) -> Dict[str, Any]:
    """Load JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        return {}

def save_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Save JSON file with proper formatting"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def create_backup(file_path: Path) -> None:
    """Create a backup of the current file"""
    if file_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f'.backup_{timestamp}.json')
        shutil.copy2(file_path, backup_path)
        print(f"Backup created: {backup_path}")

def initialize_game_structure(game: Dict[str, Any], villages: list) -> Dict[str, Any]:
    """Initialize game structure based on game type and detect potential divisions"""
    game_structure = {
        "status": "not-started"
    }
    
    game_type = game.get("type", "")
    game_id = game.get("id", "unknown")
    description = game.get("description", "").lower()
    
    # Detect if game has gender divisions based on description
    has_gender_divisions = any(keyword in description for keyword in [
        "uomini e", "donne", "maschile", "femminile", "manches", "tornei separati"
    ])
    
    if game_type == "round-robin":
        if has_gender_divisions:
            # Initialize divisions for round-robin games with gender splits
            game_structure["divisions"] = [
                {
                    "name": "Maschile",
                    "status": "not-started",
                    "rounds": [],
                    "applied_bonuses": [],
                    "applied_penalties": []
                },
                {
                    "name": "Femminile", 
                    "status": "not-started",
                    "rounds": [],
                    "applied_bonuses": [],
                    "applied_penalties": []
                }
            ]
        else:
            # No divisions, just rounds directly
            game_structure["rounds"] = []
            game_structure["applied_bonuses"] = []
            game_structure["applied_penalties"] = []
    elif game_type == "score-based":
        if has_gender_divisions:
            # Initialize divisions for score-based games with gender splits
            game_structure["divisions"] = [
                {
                    "name": "Maschile",
                    "status": "not-started",
                    "scores": {},
                    "score_penalties": [],
                    "applied_bonuses": [],
                    "applied_penalties": []
                },
                {
                    "name": "Femminile",
                    "status": "not-started", 
                    "scores": {},
                    "score_penalties": [],
                    "applied_bonuses": [],
                    "applied_penalties": []
                }
            ]
        else:
            # No divisions, just scores directly
            game_structure["scores"] = {}
            game_structure["score_penalties"] = []
            game_structure["applied_bonuses"] = []
            game_structure["applied_penalties"] = []
    else:
        # Default to scores for unknown types
        game_structure["scores"] = {}
        game_structure["score_penalties"] = []
        game_structure["applied_bonuses"] = []
        game_structure["applied_penalties"] = []
        print(f"Warning: Unknown game type '{game_type}' for game {game_id}, using 'scores' structure")
    
    return game_structure

def restore_games_status(palio_file: Path, games_status_file: Path, leaderboard_file: Path, create_backup_flag: bool = False) -> None:
    """Restore the games status file and reset leaderboard with divisions support"""
    
    # Load palio.json
    palio_data = load_json(palio_file)
    if not palio_data:
        print("Error: Could not load palio.json")
        return
    
    # Create backup if requested
    if create_backup_flag:
        create_backup(games_status_file)
        if leaderboard_file.exists():
            create_backup(leaderboard_file)
    
    # Initialize new games status structure
    games_status = {
        "game_scores": {},
        "last_updated": datetime.now().isoformat() + "Z"
    }
    
    # Get villages list first
    villages = palio_data.get("villages", [])
    
    # Process each game from palio.json
    games = palio_data.get("games", [])
    
    if not games:
        print("Warning: No games found in palio.json")
        return
    
    print(f"Processing {len(games)} games...")
    
    for game in games:
        game_id = game.get("id")
        if not game_id:
            print("Warning: Game without ID found, skipping...")
            continue
            
        game_name = game.get("name", "Unknown")
        game_type = game.get("type", "unknown")
        
        # Initialize game structure with villages for divisions
        game_structure = initialize_game_structure(game, villages)
        games_status["game_scores"][game_id] = game_structure
        
        # Show division info in output
        divisions_info = ""
        if "divisions" in game_structure:
            div_names = [div["name"] for div in game_structure["divisions"]]
            divisions_info = f" [divisions: {', '.join(div_names)}]"
        else:
            divisions_info = " [no divisions]"
        
        print(f"  {game_id}: {game_name} ({game_type}){divisions_info} -> {list(game_structure.keys())}")
    
    # Save the restored games status file
    save_json(games_status_file, games_status)
    print(f"\nRestored {len(games_status['game_scores'])} games to {games_status_file}")
    
    # Reset leaderboard file with full structure including divisions support
    leaderboard_data = {
        "villages": villages,
        "palio_leaderboard": {
            village: {
                "points": 0,
                "position": idx + 1
            } for idx, village in enumerate(villages)
        },
        "game_leaderboards": {}
    }
    
    save_json(leaderboard_file, leaderboard_data)
    print(f"Reset leaderboard with {len(villages)} villages to {leaderboard_file}")
    
    # Print summary with division information
    round_robin_count = sum(1 for g in games if g.get("type") == "round-robin")
    score_based_count = sum(1 for g in games if g.get("type") == "score-based")
    
    # Count games with gender divisions
    gender_division_count = 0
    main_division_count = 0
    
    for game in games:
        description = game.get("description", "").lower()
        has_gender_divisions = any(keyword in description for keyword in [
            "uomini e", "donne", "maschile", "femminile", "manches", "tornei separati"
        ])
        if has_gender_divisions:
            gender_division_count += 1
        else:
            main_division_count += 1

    print(f"\nSummary:")
    print(f"  Round-robin games (with 'rounds'): {round_robin_count}")
    print(f"  Score-based games (with 'scores'): {score_based_count}")
    print(f"  Games with gender divisions (Maschile/Femminile): {gender_division_count}")
    print(f"  Games without divisions (direct rounds/scores): {main_division_count}")
    print(f"  Villages reset to 0 points: {len(villages)}")
    print(f"  Palio leaderboard reset with positions: ✅")
    print(f"  Game leaderboards cleared (divisions support ready): ✅")
    print(f"  Divisions structure properly initialized: ✅")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Restore palio_games_status.json from palio.json")
    parser.add_argument("--backup", action="store_true", help="Create backup before restoring")
    parser.add_argument("--palio-file", default="data/palio.json", help="Path to palio.json file")
    parser.add_argument("--status-file", default="data/palio_games_status.json", help="Path to palio_games_status.json file")
    parser.add_argument("--leaderboard-file", default="data/leaderboard.json", help="Path to leaderboard.json file")
    
    args = parser.parse_args()
    
    # Convert to Path objects
    palio_file = Path(args.palio_file)
    status_file = Path(args.status_file)
    leaderboard_file = Path(args.leaderboard_file)
    
    # Check if palio.json exists
    if not palio_file.exists():
        print(f"Error: {palio_file} not found")
        return 1
    
    # Create data directory if it doesn't exist
    status_file.parent.mkdir(parents=True, exist_ok=True)
    leaderboard_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Restoring games status from {palio_file} to {status_file}")
    print(f"Resetting leaderboard from {palio_file} to {leaderboard_file}")
    
    try:
        restore_games_status(palio_file, status_file, leaderboard_file, args.backup)
        print("✅ Restore completed successfully!")
        return 0
    except Exception as e:
        print(f"❌ Error during restore: {e}")
        return 1

if __name__ == "__main__":
    exit(main())