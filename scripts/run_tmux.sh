#!/usr/bin/env bash
# Launch API server, Telegram bot, and CLI in a single tmux session.
#
# Usage:
#   scripts/run_tmux.sh            # start (or attach if already running)
#   scripts/run_tmux.sh -k         # kill the session
#
# Requires: tmux, uv, a configured .env with at least OPENROUTER_API_KEY.

set -euo pipefail

SESSION="palio"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

kill_session() {
    tmux kill-session -t "$SESSION" 2>/dev/null && echo "killed $SESSION" || echo "no session"
}

if [[ "${1:-}" == "-k" || "${1:-}" == "--kill" ]]; then
    kill_session
    exit 0
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "session '$SESSION' already running — attaching"
    exec tmux attach-session -t "$SESSION"
fi

cd "$PROJECT_ROOT"

# Pre-flight: make sure deps are installed.
uv sync --quiet
if [ ! -d website/node_modules ]; then
    echo "installing website deps..."
    (cd website && npm install --legacy-peer-deps)
fi

# Window 1: palio-core (file authority + event bus + React, port 8000)
tmux new-session -d -s "$SESSION" -n core -c "$PROJECT_ROOT" \
    "uv run python -m palio_bot.core; read -n 1 -p 'core stopped, press any key to close'"

# Window 2: React dev server (port 3000; proxies /api to 8000 per CRA convention)
tmux new-window -t "$SESSION":2 -n website -c "$PROJECT_ROOT/website" \
    "npm start; read -n 1 -p 'website stopped, press any key to close'"

# Window 3: Telegram bot
tmux new-window -t "$SESSION":3 -n telegram -c "$PROJECT_ROOT" \
    "uv run python -m palio_bot.telegram_bot.telegram_bot; read -n 1 -p 'telegram stopped, press any key to close'"

# Window 4: CLI (interactive — last so it grabs focus)
tmux new-window -t "$SESSION":4 -n cli -c "$PROJECT_ROOT" \
    "uv run python -m palio_bot"

tmux select-window -t "$SESSION":4

exec tmux attach-session -t "$SESSION"
