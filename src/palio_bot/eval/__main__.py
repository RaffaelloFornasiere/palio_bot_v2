"""CLI entry point: `python -m palio_bot.eval --scenario DIR --model NAME`."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from palio_bot.eval.runner import print_summary, run_scenario


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="palio-eval", description=__doc__)
    p.add_argument("--scenario", required=True, type=Path,
                   help="Path to the scenario folder (contains scenario.json and seeds/)")
    p.add_argument("--model", required=True,
                   help="OpenRouter model slug, e.g. 'anthropic/claude-3.5-haiku'. "
                        "The 'openrouter/' prefix is stripped if present.")
    p.add_argument("--out", type=Path, default=None,
                   help="Where to write the JSON report. Defaults to "
                        "results/<model>/<scenario>.json")
    p.add_argument("--api-key", default=None,
                   help="OpenRouter API key (else taken from OPENROUTER_API_KEY)")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    model = args.model.removeprefix("openrouter/")

    out_path = args.out
    if out_path is None:
        slug = model.replace("/", "-")
        out_path = Path("results") / slug / f"{args.scenario.name}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

    report = asyncio.run(
        run_scenario(
            scenario_dir=args.scenario.resolve(),
            model=model,
            out_path=out_path,
            api_key=args.api_key,
            on_event=lambda msg: print(msg, flush=True),
        )
    )
    print_summary(report)
    print(f"\nreport: {out_path}")


if __name__ == "__main__":
    main()
