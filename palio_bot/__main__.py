"""Main entry point for the palio_bot package."""

from palio_bot.cli.cli import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())