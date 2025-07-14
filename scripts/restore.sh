#!/bin/bash
# Simple wrapper script for restore_games_status.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🔄 Restoring palio_games_status.json and leaderboard.json..."
python scripts/restore_games_status.py --backup

echo ""
echo "📋 Current status:"
if [ -f "data/palio_games_status.json" ]; then
    echo "✅ palio_games_status.json restored successfully"
    echo "📊 Games count: $(jq '.game_scores | length' data/palio_games_status.json)"
else
    echo "❌ palio_games_status.json not found"
fi

if [ -f "data/leaderboard.json" ]; then
    echo "✅ leaderboard.json reset successfully"
    echo "🏆 Villages count: $(jq '.villages | length' data/leaderboard.json)"
    echo "🎯 Total points: $(jq '.points | add' data/leaderboard.json)"
else
    echo "❌ leaderboard.json not found"
fi