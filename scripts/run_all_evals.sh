#!/usr/bin/env bash
# Run every scenario under tests/scenarios/ against one or more models,
# then rebuild the results viewer.
#
# Usage:
#   scripts/run_all_evals.sh <model> [<model> ...]
#
# Example:
#   scripts/run_all_evals.sh anthropic/claude-3.5-haiku openai/gpt-4o-mini
#
# Requires: OPENROUTER_API_KEY in env (or passed through to `python -m palio_bot.eval`).

set -u

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <model> [<model> ...]" >&2
    exit 2
fi

cd "$(dirname "$0")/.."

scenarios=(tests/scenarios/*/)
if [[ ${#scenarios[@]} -eq 0 ]]; then
    echo "no scenarios found under tests/scenarios/" >&2
    exit 1
fi

failures=0

for model in "$@"; do
    echo
    echo "════════════════════════════════════════════════════════════════════"
    echo "  model: $model"
    echo "════════════════════════════════════════════════════════════════════"
    for scenario_dir in "${scenarios[@]}"; do
        scenario_dir="${scenario_dir%/}"
        echo
        echo "── $(basename "$scenario_dir") ──"
        if ! python -m palio_bot.eval --scenario "$scenario_dir" --model "$model"; then
            echo "  ✗ scenario failed: $(basename "$scenario_dir")" >&2
            failures=$((failures + 1))
        fi
    done
done

echo
echo "rebuilding viewer..."
python scripts/build_results_viewer.py

if [[ $failures -gt 0 ]]; then
    echo
    echo "$failures scenario(s) errored out (see logs above)." >&2
    exit 1
fi
