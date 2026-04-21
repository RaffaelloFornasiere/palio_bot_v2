"""Build a FileRegistry from a CoreConfig.

Mirrors the registration done by `palio_bot.container.Container.file_registry`
but without the adapter-only dependencies (LLM clients, etc.). This is the
single source of truth for what files core manages.
"""

from palio_bot.core.config import CoreConfig
from palio_bot.models.game_status_models import PalioGamesStatus
from palio_bot.models.leaderboard_models import Leaderboard
from palio_bot.models.palio_models import PalioData
from palio_bot.tools.file_registry import FileConfig, FileRegistry


def build_registry(config: CoreConfig) -> FileRegistry:
    registry = FileRegistry()

    registry.register(
        "palio",
        FileConfig(
            path=config.palio_file_path,
            validator=PalioData,
            allow_edit=False,
            use_safety_copy=False,
        ),
    )
    registry.register(
        "palio_games_status",
        FileConfig(
            path=config.palio_games_status_path,
            validator=PalioGamesStatus,
            allow_edit=True,
            use_safety_copy=False,
        ),
    )
    registry.register(
        "leaderboard",
        FileConfig(
            path=config.leaderboard_file_path,
            validator=Leaderboard,
            allow_edit=True,
            use_safety_copy=False,
        ),
    )

    return registry
