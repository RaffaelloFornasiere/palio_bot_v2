"""Scenario runner: execute a scenario against a chosen LLM and diff results."""

from __future__ import annotations

import asyncio
import copy
import difflib
import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from palio_bot.config import Config
from palio_bot.container import Container
from palio_bot.eval.judge import run_judge
from palio_bot.eval.patch import apply_patches
from palio_bot.eval.recorder import Recorder

logger = logging.getLogger(__name__)


# --- IO helpers ---

def _load_scenario(scenario_dir: Path) -> dict:
    scenario_file = scenario_dir / "scenario.json"
    if not scenario_file.exists():
        raise FileNotFoundError(f"{scenario_file} does not exist")
    return json.loads(scenario_file.read_text(encoding="utf-8"))


def _write_seed(scenario_dir: Path, seed: dict[str, str], data_dir: Path) -> None:
    """Reset data_dir: wipe all files, then copy seeds in.

    Wiping everything (not just the seed files) makes sure leftover state —
    session.json, _tmp.json from a prior step — doesn't leak into the next
    Container and corrupt the conversation history.
    """
    if data_dir.exists():
        for child in data_dir.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
    data_dir.mkdir(parents=True, exist_ok=True)
    for data_name, seed_rel in seed.items():
        src = (scenario_dir / seed_rel).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Seed file not found: {src}")
        dst = data_dir / data_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# Matches strings that are purely a number optionally followed by a letter unit.
# "30" "30.5" "-5" "30s" → coerce. "2026-04-19T00:00:00Z" "Villa" → leave alone.
_NUMERIC_STR_RE = re.compile(r"^-?\d+(?:\.\d+)?[a-zA-Z]*$")


def _coerce_numeric_strings(obj: Any) -> Any:
    """Walk a JSON tree and coerce strings like '30' or '30s' to numbers.

    Used on both expected and actual state before diffing so that a model
    writing `"points": "30s"` when the scenario expected `"points": 30`
    doesn't count as a diff.
    """
    if isinstance(obj, dict):
        return {k: _coerce_numeric_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_numeric_strings(x) for x in obj]
    if isinstance(obj, str) and _NUMERIC_STR_RE.match(obj):
        m = re.match(r"^-?\d+(?:\.\d+)?", obj)
        if m:
            num = m.group(0)
            try:
                return float(num) if "." in num else int(num)
            except ValueError:
                return obj
    return obj


def _normalize_for_diff(fname: str, data: Any) -> Any:
    """Drop volatile/format-insensitive fields so diffs reflect real divergence.

    - `last_updated` on palio_games_status.json changes on every write; ignore.
    - Numeric strings in scores/points are treated as equivalent to their numeric form.
    """
    data = copy.deepcopy(data)
    if fname == "palio_games_status.json" and isinstance(data, dict):
        data.pop("last_updated", None)
    return _coerce_numeric_strings(data)


def _json_diff(expected: Any, actual: Any, *, context: int = 3) -> str:
    exp = json.dumps(expected, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
    act = json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
    return "\n".join(
        difflib.unified_diff(exp, act, fromfile="expected", tofile="actual", n=context, lineterm="")
    )


# --- Runner ---

async def run_scenario(
    scenario_dir: Path,
    model: str,
    out_path: Path | None = None,
    api_key: str | None = None,
    on_event: "callable | None" = None,
) -> dict:
    """Run a scenario folder against `model`. Returns the result dict and writes it to out_path.

    `on_event` is called with progress strings — the CLI wires it to `print`.
    """
    emit = on_event or (lambda _msg: None)

    scenario = _load_scenario(scenario_dir)
    name = scenario.get("name", scenario_dir.name)
    reset = bool(scenario.get("reset_between_steps", False))
    seed = scenario["seed"]
    steps = scenario["steps"]

    emit(f"▸ scenario: {name}  ({len(steps)} steps, "
         f"{'isolated' if reset else 'chained'}, model={model})")

    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (pass --api-key or export env)")

    tmp_root = Path(tempfile.mkdtemp(prefix=f"palio-eval-{name}-"))
    data_dir = tmp_root / "data"
    data_dir.mkdir(parents=True)

    step_results: list[dict] = []
    t_scenario_start = time.time()

    try:
        # In chained mode we build one container and keep it for all steps.
        # In reset mode we rebuild before each step so conversation + session are fresh.
        container: Container | None = None
        recorder: Recorder | None = None

        async def fresh_container() -> tuple[Container, Recorder]:
            _write_seed(scenario_dir, seed, data_dir)
            cfg = Config(
                openrouter_api_key=api_key,
                openrouter_model=model,
                palio_file_path=data_dir / "palio.json",
                palio_games_status_path=data_dir / "palio_games_status.json",
                palio_games_status_temp_path=data_dir / "palio_games_status_tmp.json",
                leaderboard_file_path=data_dir / "leaderboard.json",
                session_file_path=data_dir / "session.json",
                llm_provider="openrouter",
            )
            c = Container(config=cfg, llm_provider="openrouter")
            rec = Recorder()
            c.stream().add_consumer(rec)
            await c.init_container()
            return c, rec

        async def teardown(c: Container) -> None:
            try:
                sys = c.system()
                if sys.get_active_session():
                    sys.cancel_session()
            except Exception:
                pass
            try:
                await c.stream().stop_processing()
            except Exception:
                pass

        if not reset:
            container, recorder = await fresh_container()

        for idx, step in enumerate(steps, 1):
            step_prefix = f"[{idx}/{len(steps)}] {step['id']}"
            prompt_preview = step["prompt"]
            if len(prompt_preview) > 80:
                prompt_preview = prompt_preview[:77] + "..."
            emit(f"  {step_prefix} … {prompt_preview}")

            if reset:
                if container is not None:
                    await teardown(container)
                container, recorder = await fresh_container()

            system = container.system()

            # Baseline = files as they are right now (after any previous chained edits).
            baseline = {fname: _read_json(data_dir / fname) for fname in seed}

            # Build expected from baseline + declared patches.
            changes = step.get("changes") or {}
            expected = dict(baseline)
            for fname, patches in changes.items():
                if fname not in baseline:
                    raise ValueError(f"step '{step['id']}' patches unknown file: {fname}")
                expected[fname] = apply_patches(baseline[fname], patches)

            recorder.reset_step()

            t0 = time.time()
            send_error: str | None = None
            try:
                await system.send_message(step["prompt"])
            except Exception as e:
                send_error = f"{type(e).__name__}: {e}"

            # Wait for the AgentCompleteEvent (or equivalent) to drain through the stream.
            try:
                await asyncio.wait_for(recorder.complete.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

            elapsed_ms = int((time.time() - t0) * 1000)

            # Commit temp files -> main so the assertions run against the stable state.
            if system.get_active_session():
                try:
                    system.save_session()
                except Exception as e:
                    logger.warning(f"save_session failed: {e}")

            actual = {fname: _read_json(data_dir / fname) for fname in seed}

            diffs: dict[str, str] = {}
            for fname in seed:
                exp_norm = _normalize_for_diff(fname, expected[fname])
                act_norm = _normalize_for_diff(fname, actual[fname])
                if exp_norm != act_norm:
                    diffs[fname] = _json_diff(exp_norm, act_norm)

            # Judge (optional, per-step): LLM grades the final assistant text.
            judge_result: dict | None = None
            if step.get("judge"):
                judge_result = await run_judge(
                    step_prompt=step["prompt"],
                    agent_reply=recorder.final_assistant_text,
                    ground_truth_files=baseline,
                    judge_config=step["judge"],
                    api_key=api_key,
                )

            passed = (
                not send_error
                and not diffs
                and (judge_result is None or judge_result["passed"])
            )

            flag = "✓" if passed else "✗"
            tool_names = [tc["tool"] for tc in recorder.tool_calls]
            tool_str = ",".join(tool_names) if tool_names else "no tools"
            fail_reason = ""
            if send_error:
                fail_reason = f"  send_error: {send_error[:120]}"
            elif diffs:
                fail_reason = f"  diff in: {', '.join(diffs.keys())}"
            elif judge_result and not judge_result["passed"]:
                fail_reason = f"  judge: {judge_result['reasoning'][:120]}"
            elif recorder.tool_failures:
                fail_reason = f"  {len(recorder.tool_failures)} tool failures"
            emit(
                f"     {flag} {elapsed_ms/1000:5.1f}s  "
                f"{recorder.total_tokens:>6} tok  [{tool_str}]{fail_reason}"
            )

            step_results.append({
                "id": step["id"],
                "prompt": step["prompt"],
                "passed": passed,
                "elapsed_ms": elapsed_ms,
                "tokens": recorder.total_tokens,
                "send_error": send_error,
                "tool_failures": recorder.tool_failures,
                "tool_calls": [tc["tool"] for tc in recorder.tool_calls],
                "diffs": diffs,
                "final_text": recorder.final_assistant_text,
                "judge": judge_result,
            })

        if container is not None and not reset:
            await teardown(container)

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    n_passed = sum(1 for r in step_results if r["passed"])
    total_tokens = sum(r["tokens"] or 0 for r in step_results)
    total_elapsed = time.time() - t_scenario_start

    report = {
        "scenario": name,
        "model": model,
        "passed": n_passed,
        "total": len(step_results),
        "total_tokens": total_tokens,
        "total_elapsed_s": round(total_elapsed, 2),
        "steps": step_results,
    }

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    return report


def print_summary(report: dict) -> None:
    """Final one-line stat. Per-step lines are already printed live."""
    print(
        f"\n{report['model']}   "
        f"{report['passed']}/{report['total']} steps passed   "
        f"{report['total_tokens']:,} tokens   "
        f"{report['total_elapsed_s']}s"
    )
