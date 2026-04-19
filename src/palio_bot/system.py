"""System coordinator with multi-file support and event streaming."""

import json
import logging
import uuid
from typing import Optional

from palio_bot.agent.agent import Agent
from palio_bot.agent.models import (
    AgentContextBlock,
    Message,
    Session,
    TextContent,
    TokenUsage,
    ToolResultContent,
    ToolUseContent,
)
from palio_bot.config import Config
from palio_bot.file_manager import FileManager
from palio_bot.models.game_status_models import extract_model_docs
from palio_bot.stream.events import (
    AgentCancelledEvent,
    AgentCompleteEvent,
    AgentUpdateEvent,
    ErrorEvent,
    ToolResultEvent,
    ToolUseEvent,
    UserMessageEvent,
)
from palio_bot.stream.interfaces import Producer
from palio_bot.stream.stream import Stream
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class System(Producer):
    """Coordinates sessions, agent execution, and event emission.

    File lifecycle (temp copies, commit on save, discard on cancel) is
    delegated to `FileManager` — this class only owns conversation state
    and agent orchestration.
    """

    def __init__(
        self,
        *,
        agent: Agent,
        stream: Stream,
        file_registry: FileRegistry,
        config: Optional[Config] = None,
        file_manager: Optional[FileManager] = None,
    ):
        super().__init__(stream)
        self.agent = agent
        self.stream = stream
        self.file_registry = file_registry
        self.file_manager = file_manager or FileManager(file_registry)
        self.active_session: Optional[Session] = None

        self._cancellation_requested = False

        self.config = config or Config()
        self.session_file_path = self.config.session_file_path

        logger.info(f"System initialized with {len(file_registry.files)} registered files")

        # Load existing session if available
        self._load_session()

    # ---------- public API ----------

    async def send_message(self, user_message: str) -> None:
        """Send a message through the agent, emitting events along the way."""
        logger.info(
            f"\n{'=' * 60}\nSystem.send_message() called\nMessage: {user_message}\n{'=' * 60}"
        )

        try:
            self.reset_cancellation()

            if self.active_session is None:
                logger.info("No active session, creating new one")
                self._create_session()
            else:
                logger.info(f"Using existing session: {self.active_session.id}")

            user_msg = Message.text(role="user", text=user_message)
            self.active_session.add_message(user_msg)
            self._save_session()

            await self.produce(
                UserMessageEvent(
                    session_id=self.active_session.id,
                    content=user_message,
                )
            )

            context = self._build_context()
            logger.debug(f"Context loaded: {len(context)} blocks")

            total_token_usage = TokenUsage()

            async for message in self.agent.run(
                messages=self.active_session.messages.copy(),
                context=context,
                cancellation_check=self._check_cancellation,
            ):
                if self._cancellation_requested:
                    await self.produce(
                        AgentCancelledEvent(
                            session_id=self.active_session.id,
                            reason="User requested cancellation via /stop command",
                        )
                    )
                    logger.info("Agent processing cancelled by user")
                    return

                self.active_session.add_message(message)
                self._save_session()

                if message.token_usage:
                    total_token_usage = total_token_usage + message.token_usage

                for content in message.content:
                    if isinstance(content, TextContent):
                        await self.produce(
                            AgentUpdateEvent(
                                session_id=self.active_session.id,
                                message=message,
                            )
                        )
                    elif isinstance(content, ToolUseContent):
                        await self.produce(
                            ToolUseEvent(
                                session_id=self.active_session.id,
                                tool_name=content.tool_name,
                                parameters=content.tool_parameters,
                            )
                        )
                    elif isinstance(content, ToolResultContent):
                        await self.produce(
                            ToolResultEvent(
                                session_id=self.active_session.id,
                                tool_name="unknown",
                                result=content.tool_result,
                            )
                        )

            logger.info("Agent processing complete")
            await self.produce(
                AgentCompleteEvent(
                    session_id=self.active_session.id,
                    total_token_usage=total_token_usage
                    if total_token_usage.total_tokens > 0
                    else None,
                )
            )

            self._save_session()
            logger.info("System.send_message() completed successfully")

        except Exception as e:
            import traceback

            error_traceback = traceback.format_exc()
            logger.error(f"Error in send_message: {str(e)}")
            logger.error(f"Traceback:\n{error_traceback}")

            if self.active_session:
                await self.produce(
                    ErrorEvent(
                        session_id=self.active_session.id,
                        error=str(e),
                        traceback=error_traceback,
                    )
                )

            raise

    def save_session(self) -> None:
        """Commit temp files to main without closing the session."""
        if self.active_session is None:
            logger.warning("save_session called but no active session")
            return
        logger.info(f"Saving changes for session {self.active_session.id}")
        self.file_manager.commit()

    def close_session(self, save_changes: bool = True) -> None:
        """Close the active session, optionally committing pending changes."""
        if self.active_session is None:
            logger.warning("close_session called but no active session")
            return

        logger.info(
            f"Closing session {self.active_session.id} (save_changes={save_changes})"
        )

        if save_changes:
            self.file_manager.commit()

        # Always discard temp files on close
        self.file_manager.discard()

        self.active_session = None
        self._cleanup_session_file()

    def cancel_session(self) -> None:
        """Cancel the active session, discarding all pending edits."""
        self.close_session(save_changes=False)

    def get_active_session(self) -> Optional[Session]:
        return self.active_session

    def request_cancellation(self) -> None:
        logger.info("Cancellation requested")
        self._cancellation_requested = True

    def reset_cancellation(self) -> None:
        self._cancellation_requested = False

    def _check_cancellation(self) -> bool:
        return self._cancellation_requested

    # ---------- session persistence ----------

    def _create_session(self) -> None:
        session_id = str(uuid.uuid4())
        self.active_session = Session(id=session_id)
        logger.info(f"Created new session: {session_id}")
        self.file_manager.start_session()

    def _save_session(self) -> None:
        if self.active_session is None:
            return
        with open(self.session_file_path, "w", encoding="utf-8") as f:
            json.dump(
                self.active_session.model_dump(mode="json"),
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _load_session(self) -> None:
        if not self.session_file_path.exists():
            logger.debug("No session file found")
            return

        try:
            with open(self.session_file_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            self.active_session = Session.model_validate(session_data)
            logger.info(
                f"Loaded existing session: {self.active_session.id} "
                f"with {len(self.active_session.messages)} messages"
            )
            self.file_manager.resume_session()

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            self.session_file_path.unlink()
            logger.warning("Removed corrupted session file")

    def _cleanup_session_file(self) -> None:
        if self.session_file_path.exists():
            logger.info(f"Removing session file: {self.session_file_path}")
            self.session_file_path.unlink()

    # ---------- context ----------

    def _build_context(self) -> list[AgentContextBlock]:
        blocks: list[AgentContextBlock] = [
            AgentContextBlock(context_name="game_status_models", content=extract_model_docs())
        ]
        blocks.extend(self.file_manager.load_context_blocks())
        return blocks
