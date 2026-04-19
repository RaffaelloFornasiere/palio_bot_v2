"""Session-scoped file lifecycle management.

Owns the copy-on-write temp-file dance, atomic commit on save, and
discard on cancel. `System` delegates all file operations here so it can
focus on conversation + agent orchestration.
"""

import json
import logging
import shutil
from typing import List

from palio_bot.agent.models import AgentContextBlock
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class FileManager:
    """Manages the session-scoped temp-file lifecycle for a FileRegistry."""

    def __init__(self, registry: FileRegistry):
        self.registry = registry

    # ---------- session lifecycle ----------

    def start_session(self) -> None:
        """Copy every safety-copy file to its temp path (creating empties as needed)."""
        for file_name, config in self.registry.files.items():
            if not config.use_safety_copy:
                continue
            temp_path = self.registry.get_temp_path(file_name)
            if config.path.exists():
                logger.info(f"Copying {config.path} -> {temp_path}")
                shutil.copy2(config.path, temp_path)
            else:
                logger.warning(f"{config.path} not found, creating empty {temp_path}")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)

    def resume_session(self) -> None:
        """Ensure every safety-copy file has a temp copy; recreate missing ones."""
        for file_name, config in self.registry.files.items():
            if not config.use_safety_copy:
                continue
            temp_path = self.registry.get_temp_path(file_name)
            if temp_path and not temp_path.exists() and config.path.exists():
                logger.warning(
                    f"Session exists but {temp_path} missing, recreating from {config.path}"
                )
                shutil.copy2(config.path, temp_path)

    def commit(self) -> None:
        """Copy all modified temp files back to their canonical paths.

        Temp files are NOT removed — the session is still active and may
        continue editing.
        """
        for file_name in self.registry.get_modified_files():
            config = self.registry.get_config(file_name)
            if not config or not config.use_safety_copy:
                continue
            temp_path = self.registry.get_temp_path(file_name)
            if temp_path and temp_path.exists():
                logger.info(f"Committing {temp_path} -> {config.path}")
                shutil.copy2(temp_path, config.path)
        self.registry.clear_modified()

    def discard(self) -> None:
        """Remove every temp file and clear the modified-set."""
        for file_name, config in self.registry.files.items():
            if not config.use_safety_copy:
                continue
            temp_path = self.registry.get_temp_path(file_name)
            if temp_path and temp_path.exists():
                logger.info(f"Removing temp file: {temp_path}")
                temp_path.unlink()
        self.registry.clear_modified()

    # ---------- context loading ----------

    def load_context_blocks(self) -> List[AgentContextBlock]:
        """Read registered files and return them as context blocks.

        Only reads files by their registered name: caller controls which
        files are surfaced by registering them.
        """
        blocks: List[AgentContextBlock] = []

        named_blocks = {
            "palio": "palio_specification",
            "leaderboard": "current_leaderboard",
            "palio_games_status": "palio_games_status",
        }

        for file_name, context_name in named_blocks.items():
            if file_name not in self.registry.files:
                continue
            active_path = self.registry.get_active_path(file_name)
            if not active_path or not active_path.exists():
                continue
            with open(active_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            blocks.append(
                AgentContextBlock(
                    context_name=context_name,
                    content=json.dumps(content, indent=4),
                )
            )

            # Add game-id → name mapping when reading the palio spec
            if file_name == "palio" and "games" in content:
                ids = "\n".join(f"{g['id']} - {g['name']}" for g in content["games"])
                blocks.append(
                    AgentContextBlock(context_name="palio_game_id_mapping", content=ids)
                )

        return blocks
