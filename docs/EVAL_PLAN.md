# Agent Eval — Design Sketch

End-to-end test harness: send natural-language prompts through the real agent
loop + tools, confirm the resulting JSON files match expectations. Run against
a single LLM at a time to measure reliability.

---

## 1. Scenario format

One JSON file per scenario. The whole scenario is either chained or isolated —
set once at the root, not per step.

Each step declares the **changes** it expects the agent to make, as a list of
JSONPath patches. The runner computes `expected = baseline + patches` and
deep-equals it against the actual file. Anything the agent touches outside the
declared patches is a failure.

### Layout

Each scenario gets its own self-contained folder with a `scenario.json` and a
`seeds/` subfolder for its starting data. Seeds stay local to the scenario —
no cross-scenario sharing for v1 (copy a seed if you want to reuse it).

```
tests/scenarios/
├── 01_simple_reads/
│   ├── scenario.json
│   └── seeds/
│       ├── palio.json
│       ├── leaderboard.json
│       └── palio_games_status.json
├── 02_game_completion/
│   ├── scenario.json
│   └── seeds/
│       ├── palio.json
│       ├── leaderboard.json
│       └── palio_games_status.json
└── 03_palio_flow/
    ├── scenario.json
    └── seeds/
        └── ...
```

```json
{
  "name": "calcetto_first_round",
  "reset_between_steps": false,
  "seed": {
    "palio.json":               "seeds/palio.json",
    "leaderboard.json":         "seeds/leaderboard.json",
    "palio_games_status.json":  "seeds/palio_games_status.json"
  },
  "steps": [
    {
      "id": "s1",
      "prompt": "mostra lo stato del calcio a cinque"
    },
    {
      "id": "s2",
      "prompt": "villa vince 4-2 contro salt al calcio a cinque, primo round maschile",
      "changes": {
        "palio_games_status.json": [
          { "path": "$.game_scores.G09.status", "set": "in-progress" },
          { "path": "$.game_scores.G09.divisions[0].status", "set": "in-progress" },
          { "path": "$.game_scores.G09.divisions[0].rounds",
            "set": [
              {
                "scores": [
                  { "village": "villa", "points": 4 },
                  { "village": "salt",  "points": 2 }
                ],
                "score_penalties": []
              }
            ]
          }
        ]
      }
    }
  ]
}
```

### Fields

- `seed` — a map from data-file name (as it lives in `data/`) to a path of a
  seed JSON file inside the scenario folder. Paths are resolved relative to
  `scenario.json`. The runner copies each referenced file into the temp
  `data/` dir before the scenario runs.
- `reset_between_steps: true` — reload seed + drop conversation before each
  step (isolated mode). Baseline = seed for every step.
- `reset_between_steps: false` — state and conversation persist across steps
  (chained mode). Baseline = state at end of previous step.
- `steps[].prompt` — what gets sent to `system.send_message`.
- `steps[].changes` — per-file list of patches. Operations:
  - `{"path": "...", "set": <value>}` — write value at path (edits or creates).
  - `{"path": "...", "delete": true}` — remove the dict key or list index at path.
  Omit `changes` entirely when the step should not mutate any file (pure reads
  like `s1` above). Such a step passes as long as the agent doesn't error out.

### Semantics

For each step:
1. `baseline = snapshot of each data file at step start` (seed if first step
   or `reset_between_steps=true`, otherwise previous step's final state).
2. `expected[file] = apply(baseline[file], changes[file])` for every file listed
   in `changes`. Files not listed are expected to stay equal to baseline.
3. Run the agent prompt. Let the temp files be mutated freely.
4. Deep-equal `expected` vs `actual` for every file in the data dir.
5. On mismatch, render a diff and mark the step failed.

---

## 2. Runner

```
python -m palio_bot.eval \
  --scenario tests/scenarios/02_game_completion \
  --model openrouter/anthropic/claude-3.5-haiku \
  --out results/02_game_completion__haiku.json
```

The `--scenario` arg points at a folder; the runner loads
`<folder>/scenario.json` and resolves seed paths relative to that folder.

Per run:

1. Make a fresh temp `data/` dir, write `seed` into it.
2. Spin up a `Container` pointed at that temp dir with the chosen model.
3. For each step:
   - Capture baseline snapshot.
   - If `reset_between_steps`: re-seed + new session.
   - Compute `expected` = `apply(baseline, changes)`.
   - Call `system.send_message(prompt)`, wait for `AgentCompleteEvent`.
   - Deep-equal files against `expected`. Record pass/fail + diff.
4. Print a stat line:

   ```
   claude-3.5-haiku   7/9 steps passed   48,203 tokens   62s
   ```

5. Write a JSON result file (per-step pass/fail, tokens, elapsed ms, diffs).

Running against another LLM = re-run with `--model`. No matrix runner; collect
per-model reports manually.

---

## 3. Scenarios to build (v1)

- **`tests/scenarios/01_simple_reads/`** — isolated, pure reads, no `changes`.
  Probes whether the LLM uses `json_view` and produces sane replies.
- **`tests/scenarios/02_game_completion/`** — chained, 5–6 steps completing
  one round-robin game.
- **`tests/scenarios/03_palio_flow/`** — chained, 10+ steps, growing file
  sizes. Stress test for context growth.

---

## 4. Open questions (revisit later)

- **Non-determinism** — some prompts admit multiple correct JSONs (e.g. order of
  items in an array the agent freshly constructs). Options: canonicalize arrays
  before comparison, or accept a list of alternative `changes` per step. For v1
  we'll eyeball the diff and tighten the scenario.
- **Cost guardrail** — `--max-tokens` and `--max-steps` limits so a buggy model
  can't loop forever.
- **Session flow** — no `/close` between steps; let the session keep writing to
  temp files. After the scenario finishes, `cancel_session` and wipe the dir.

---

## 5. What to build

- `src/palio_bot/eval/runner.py` — load scenario, apply patches, run steps,
  diff, emit report.
- `src/palio_bot/eval/patch.py` — tiny helper that applies `{path, set}` /
  `{path, delete}` via `jsonpath_ng` (same dep the editor already uses).
- `tests/scenarios/*.json` — three starter scenarios.
- Model override: plumb `--model` through to `Config.openrouter_model` (trivial).

Estimated effort: half a day for runner + first scenario, then iterate.
