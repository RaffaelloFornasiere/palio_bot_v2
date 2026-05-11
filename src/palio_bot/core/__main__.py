"""Run palio_bot.core via `python -m palio_bot.core`."""

import argparse
import os

import uvicorn

from palio_bot.core.app import app
from palio_bot.core.config import CoreConfig


def main() -> None:
    config = CoreConfig()
    parser = argparse.ArgumentParser(prog="palio_bot.core")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override port from PALIO_CORE_URL (default: parsed from URL)",
    )
    args = parser.parse_args()

    if args.port is not None:
        os.environ["PALIO_CORE_URL"] = f"http://localhost:{args.port}"
        config = CoreConfig()

    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
