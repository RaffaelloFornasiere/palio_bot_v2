"""System coordinator with multi-file support and event streaming.

File lifecycle + staging live in `palio_bot.core`. This class owns only
conversation state, agent orchestration, and event emission; all file I/O
is delegated to a `CoreClient` + `RemoteFileStore`.
"""

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
from palio_bot.core_client.client import CoreClient
from palio_bot.core_client.file_store_remote import RemoteFileStore
from palio_bot.models.game_status_models import extract_model_docs
from palio_bot.stream.events import (
    AgentCancelledEvent,
    AgentCompleteEvent,
    AgentUpdateEvent,
    ErrorEvent,
    Event,
    SessionDiscardedEvent,
    ToolResultEvent,
    ToolUseEvent,
    UserMessageEvent,
)
from palio_bot.core_client.stream_client import StreamClient
from palio_bot.stream.interfaces import Producer
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


_CONTEXT_FILES = {
    "palio": "palio_specification",
    "leaderboard": "current_leaderboard",
    "palio_games_status": "palio_games_status",
}


class System(Producer):
    """Coordinates sessions, agent execution, and event emission.

    File staging, locking, and commit semantics live in palio-core — this
    class calls into it via `CoreClient` and keeps the tool's
    `RemoteFileStore` in sync with the active remote session.
    """

    def __init__(
        self,
        *,
        agent: Agent,
        stream: StreamClient,
        file_registry: FileRegistry,
        core_client: CoreClient,
        remote_file_store: RemoteFileStore,
        label: str = "adapter",
        config: Optional[Config] = None,
    ):
        super().__init__(stream)
        self.agent = agent
        self.stream = stream
        self.file_registry = file_registry
        self.core_client = core_client
        self.remote_file_store = remote_file_store
        self.label = label
        self.active_session: Optional[Session] = None
        self.remote_session_id: Optional[str] = None

        self._cancellation_requested = False

        self.config = config or Config()
        self.session_file_path = self.config.session_file_path

        # Session ids we've voluntarily ended (commit/discard). We echo back
        # our own SessionDiscardedEvent via the bus; use this set to ignore
        # self-initiated events so we only react to EXTERNAL kills.
        self._self_ended_sessions: set[str] = set()

        logger.info(
            "System initialized (label=%s, files=%d)",
            label,
            len(file_registry.files),
        )

        # Load existing conversation from disk (no remote session yet; created lazily).
        self._load_session()

        # Subscribe to core-side lifecycle events so we can reset the
        # remote session when another party (web editor, other chat)
        # commits a file we had staged — see `_handle_external_event`.
        self.stream.add_consumer(self)

    # ---------- public API ----------

    async def send_message(self, user_message: str) -> None:
        logger.info(
            f"\n{'=' * 60}\nSystem.send_message() called\nMessage: {user_message}\n{'=' * 60}"
        )

        try:
            self.reset_cancellation()

            if self.active_session is None or self.remote_session_id is None:
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
        """Commit staged edits to canonical; start a fresh remote session."""
        if self.active_session is None or self.remote_session_id is None:
            logger.warning("save_session called but no active remote session")
            return
        logger.info(f"Committing remote session {self.remote_session_id}")
        ending_id = self.remote_session_id
        self._self_ended_sessions.add(ending_id)
        self.core_client.commit(ending_id)

        # Commit ends the core-side session. Start a fresh one so subsequent
        # edits in this conversation have somewhere to stage.
        self.remote_session_id = self.core_client.create_session(self.label)
        self.remote_file_store.rebind(self.remote_session_id)
        logger.info(f"Started new remote session {self.remote_session_id}")

    def close_session(self, save_changes: bool = True) -> None:
        if self.active_session is None:
            logger.warning("close_session called but no active session")
            return

        logger.info(
            "Closing session %s (remote=%s, save_changes=%s)",
            self.active_session.id,
            self.remote_session_id,
            save_changes,
        )

        if self.remote_session_id is not None:
            self._self_ended_sessions.add(self.remote_session_id)
            try:
                if save_changes:
                    self.core_client.commit(self.remote_session_id)
                else:
                    self.core_client.discard(self.remote_session_id)
            except Exception:
                logger.exception("close_session: core call failed; clearing local state")

        self.remote_session_id = None
        self.remote_file_store.rebind("")
        self.active_session = None
        self._cleanup_session_file()

    def cancel_session(self) -> None:
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
        local_id = str(uuid.uuid4())
        self.active_session = Session(id=local_id)
        self.remote_session_id = self.core_client.create_session(self.label)
        self.remote_file_store.rebind(self.remote_session_id)
        logger.info(
            "Created session (local=%s, remote=%s)", local_id, self.remote_session_id
        )

    # ---------- event consumer ----------

    async def consume(self, event: Event) -> None:
        """React to core-side lifecycle events.

        We only care about `session_discarded` targeting our own remote
        session when the discard was NOT self-initiated — i.e. core killed
        us because another session committed. In that case we drop the
        remote session, notify the user, and let the next message create a
        fresh one.
        """
        if not isinstance(event, SessionDiscardedEvent):
            return

        sid = event.session_id
        if sid in self._self_ended_sessions:
            self._self_ended_sessions.discard(sid)
            return

        if self.remote_session_id != sid:
            return

        logger.warning(
            "system: remote session %s was discarded externally (file committed "
            "by another session); resetting",
            sid,
        )
        self.remote_session_id = None
        self.remote_file_store.rebind("")

        try:
            await self.produce(
                ErrorEvent(
                    session_id=self.active_session.id if self.active_session else "",
                    error=(
                        "Il file è stato modificato da un'altra sessione "
                        "(editor web o altra chat). Le modifiche in corso "
                        "sono state scartate. Rimanda il messaggio per "
                        "ripartire con i dati aggiornati."
                    ),
                )
            )
        except Exception:
            logger.exception("failed to emit external-kill error event")

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
                f"Loaded existing conversation: {self.active_session.id} "
                f"with {len(self.active_session.messages)} messages "
                f"(remote session will be created on first message)"
            )

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

        for file_name, context_name in _CONTEXT_FILES.items():
            if file_name not in self.file_registry.files:
                continue
            try:
                content = self.remote_file_store.load(file_name)
            except Exception as exc:
                logger.warning(
                    "System._build_context: could not load %s: %s", file_name, exc
                )
                continue

            blocks.append(
                AgentContextBlock(
                    context_name=context_name,
                    content=json.dumps(content, indent=4),
                )
            )

            if file_name == "palio" and isinstance(content, dict) and "games" in content:
                ids = "\n".join(f"{g['id']} - {g['name']}" for g in content["games"])
                blocks.append(
                    AgentContextBlock(context_name="palio_game_id_mapping", content=ids)
                )

        return blocks
