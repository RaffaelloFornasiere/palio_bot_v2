"""Run palio_bot.core via `python -m palio_bot.core`."""

import uvicorn

from palio_bot.core.app import app
from palio_bot.core.config import CoreConfig


def main() -> None:
    config = CoreConfig()
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
