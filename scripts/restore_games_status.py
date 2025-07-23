#!/usr/bin/env python3
"""
Restore script for palio_games_status.json

This script resets the palio_games_status.json file with all games from palio.json
and initializes them with the appropriate structure:
- "rounds" key for round-robin games
- "scores" key for score-based games

Usage:
    python scripts/restore_games_status.py [--backup]
    
Options:
    --backup    Create a backup of the current file before restoring
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

def initialize_game_structure(game: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize game structure based on game type"""
    game_structure = {
        "status": "not-started"
    }
    
    game_type = game.get("type", "")
    
    if game_type == "round-robin":
        game_structure["rounds"] = []
    elif game_type == "score-based":
        game_structure["scores"] = {}
    else:
        # Default to scores for unknown types
        game_structure["scores"] = {}
        print(f"Warning: Unknown game type '{game_type}' for game {game.get('id', 'unknown')}, using 'scores' structure")
    
    return game_structure

def restore_games_status(palio_file: Path, games_status_file: Path, leaderboard_file: Path, create_backup_flag: bool = False) -> None:
    """Restore the games status file"""
    
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
        
        # Initialize game structure
        game_structure = initialize_game_structure(game)
        games_status["game_scores"][game_id] = game_structure
        
        print(f"  {game_id}: {game_name} ({game_type}) -> {list(game_structure.keys())}")
    
    # Save the restored games status file
    save_json(games_status_file, games_status)
    print(f"\nRestored {len(games_status['game_scores'])} games to {games_status_file}")
    
    # Reset leaderboard file
    villages = palio_data.get("villages", [])
    leaderboard_data = {
        "villages": villages,
        "points": {village: 0 for village in villages},
        "game_leaderboards": {}
    }
    
    save_json(leaderboard_file, leaderboard_data)
    print(f"Reset leaderboard with {len(villages)} villages to {leaderboard_file}")
    
    # Print summary
    round_robin_count = sum(1 for g in games if g.get("type") == "round-robin")
    score_based_count = sum(1 for g in games if g.get("type") == "score-based")

    print(f"\nSummary:")
    print(f"  Round-robin games (with 'rounds'): {round_robin_count}")
    print(f"  Score-based games (with 'scores'): {score_based_count}")
    print(f"  Villages reset to 0 points: {len(villages)}")
    print(f"  Game leaderboards cleared: ✅")

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