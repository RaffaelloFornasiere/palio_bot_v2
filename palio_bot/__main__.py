"""Main entry point for the palio_bot package."""

import sys
from .cli import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())