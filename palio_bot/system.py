"""System coordinator with multi-file support and event streaming."""

import json
import os
import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional

from palio_bot.agent.models import (
    Message, Session, AgentContextBlock, TextContent, ToolUseContent, ToolResultContent, TokenUsage
)
from palio_bot.agent.agent import Agent
from palio_bot.models.game_status_models import extract_model_docs
from palio_bot.stream.stream import Stream
from palio_bot.stream.interfaces import Producer
from palio_bot.stream.events import (
    UserMessageEvent, AgentUpdateEvent, ToolUseEvent, 
    ToolResultEvent, AgentCompleteEvent, AgentCancelledEvent, ErrorEvent
)
from palio_bot.config import Config
from palio_bot.leaderboard_updater import LeaderboardUpdater
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class System(Producer):
    """Main coordinator with multi-file support that manages sessions and orchestrates agent interactions."""
    
    def __init__(
        self,
        *,
        agent: Agent,
        stream: Stream,
        file_registry: FileRegistry,
        config: Config = None,
    ):
        super().__init__(stream)
        self.agent = agent
        self.stream = stream
        self.file_registry = file_registry
        self.active_session: Optional[Session] = None
        
        # Add cancellation state management
        self._cancellation_requested = False
        
        if config is None:
            config = Config()
            
        # Keep config for legacy compatibility
        self.config = config
        self.palio_file_path = config.palio_file_path
        self.palio_games_status_path = config.palio_games_status_path
        self.leader_board_file_path = config.leaderboard_file_path
        self.session_file_path = config.session_file_path
        self.palio_games_status_temp_path = config.palio_games_status_temp_path
        
        logger.info(f"System initialized with {len(file_registry.files)} registered files")
        
        # Load existing session if available
        self._load_session()
    
    async def send_message(self, user_message: str) -> None:
        """Send a message to the system with event streaming.
        
        If there's an active session, continue the conversation.
        Otherwise, create a new session.
        
        Args:
            user_message: User's message text
        """
        logger.info(f"\n{'='*60}\nSystem.send_message() called\nMessage: {user_message}\n{'='*60}")
        
        try:
            # Reset cancellation flag for new message processing
            self.reset_cancellation()
            
            # Create new session if none exists
            if self.active_session is None:
                logger.info("No active session, creating new one")
                self._create_session()
            else:
                logger.info(f"Using existing session: {self.active_session.id}")
            
            # Add user message to session
            user_msg = Message.text(role="user", text=user_message)
            self.active_session.add_message(user_msg)
            self._save_session()

            # Emit user message event
            logger.debug("Producing UserMessageEvent")
            await self.produce(UserMessageEvent(
                session_id=self.active_session.id,
                content=user_message
            ))
            
            # Get current context
            logger.debug("Loading context")
            context = self._get_context_from_registry()
            logger.debug(f"Context loaded: {len(context)} blocks")
            
            # Process message through agent generator
            logger.info("Calling agent.run()")
            
            # Track total token usage for this interaction
            total_token_usage = TokenUsage()

            async for message in self.agent.run(
                messages=self.active_session.messages.copy(),
                context=context,
                cancellation_check=self._check_cancellation
            ):
                # Check if we got a cancellation message
                if self._cancellation_requested:
                    # Emit cancellation event
                    await self.produce(AgentCancelledEvent(
                        session_id=self.active_session.id,
                        reason="User requested cancellation via /stop command"
                    ))
                    logger.info("Agent processing cancelled by user")
                    return
                
                # Add message to session
                self.active_session.add_message(message)
                self._save_session()
                
                # Accumulate token usage if present
                if message.token_usage:
                    total_token_usage = total_token_usage + message.token_usage
                
                # Check message content and emit appropriate events
                for content in message.content:
                    if isinstance(content, TextContent):
                        # Emit agent update event for text responses
                        await self.produce(AgentUpdateEvent(
                            session_id=self.active_session.id,
                            message=message
                        ))
                    elif isinstance(content, ToolUseContent):
                        # Emit tool use event
                        await self.produce(ToolUseEvent(
                            session_id=self.active_session.id,
                            tool_name=content.tool_name,
                            parameters=content.tool_parameters
                        ))
                    elif isinstance(content, ToolResultContent):
                        # Emit tool result event
                        await self.produce(ToolResultEvent(
                            session_id=self.active_session.id,
                            tool_name="unknown",  # We don't have tool_name in ToolResultContent
                            result=content.tool_result
                        ))
            
            logger.info("Agent processing complete")
            logger.info(f"Producing AgentCompleteEvent with token usage: {total_token_usage}")
            await self.produce(AgentCompleteEvent(
                session_id=self.active_session.id,
                total_token_usage=total_token_usage if total_token_usage.total_tokens > 0 else None
            ))
            
            # Save session after interaction
            logger.debug("Saving session")
            self._save_session()
            logger.info("Session saved successfully")
            
            logger.info("System.send_message() completed successfully")
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error in send_message: {str(e)}")
            logger.error(f"Traceback:\n{error_traceback}")
            
            # Emit error event
            if self.active_session:
                await self.produce(ErrorEvent(
                    session_id=self.active_session.id,
                    error=str(e),
                    traceback=error_traceback
                ))
            
            raise
    
    def save_session(self) -> None:
        """Save changes from temp files to original files without closing the session."""
        if self.active_session is None:
            logger.warning("save_session called but no active session")
            return
        
        logger.info(f"Saving changes for session {self.active_session.id}")
        
        # Copy all modified temp files back to their originals
        modified_files = self.file_registry.get_modified_files()
        for file_name in modified_files:
            config = self.file_registry.get_config(file_name)
            if config and config.use_safety_copy:
                temp_path = self.file_registry.get_temp_path(file_name)
                if temp_path and temp_path.exists():
                    logger.info(f"Copying {temp_path} to {config.path}")
                    shutil.copy2(temp_path, config.path)
                    logger.info(f"Changes saved to {file_name}")
                    # DO NOT remove temp file - session is still active
                    # Temp files should only be removed when session is closed
        
        # Clear modified files tracking (but keep temp files)
        self.file_registry.clear_modified()

    def close_session(self, save_changes: bool = True) -> None:
        """Close the active session, optionally saving changes."""
        if self.active_session is None:
            logger.warning("close_session called but no active session")
            return
        
        logger.info(f"Closing session {self.active_session.id} (save_changes={save_changes})")
        
        if save_changes:
            self.save_session()
        
        # Always cleanup temp files when closing session
        self._cleanup_temp_files()
        
        self.active_session = None
        
        # Remove session file
        self._cleanup_session_file()
    
    def cancel_session(self) -> None:
        """Cancel the active session and discard all changes."""
        self.close_session(save_changes=False)
    
    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session."""
        return self.active_session
    
    def request_cancellation(self) -> None:
        """Request cancellation of current computation."""
        logger.info("Cancellation requested")
        self._cancellation_requested = True
    
    def reset_cancellation(self) -> None:
        """Reset cancellation flag for new operations."""
        self._cancellation_requested = False
    
    def _check_cancellation(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancellation_requested
    
    def _cleanup_temp_files(self) -> None:
        """Remove all temporary files and clear modified tracking."""
        logger.info("Cleaning up temporary files")
        for file_name, config in self.file_registry.files.items():
            if config.use_safety_copy:
                temp_path = self.file_registry.get_temp_path(file_name)
                if temp_path and temp_path.exists():
                    logger.info(f"Removing temp file: {temp_path}")
                    temp_path.unlink()
        
        # Clear modified files tracking
        self.file_registry.clear_modified()
        logger.info("Temporary files cleanup completed")
    
    def _cleanup_session_file(self) -> None:
        """Remove session.json file."""
        if self.session_file_path.exists():
            logger.info(f"Removing session file: {self.session_file_path}")
            self.session_file_path.unlink()
            logger.info("Session file removed")
    
    def _create_session(self) -> None:
        """Create a new session and copy all files that need safety copies."""
        session_id = str(uuid.uuid4())
        self.active_session = Session(id=session_id)
        logger.info(f"Created new session: {session_id}")
        
        # Copy all files that use safety copy
        for file_name, config in self.file_registry.files.items():
            if config.use_safety_copy and config.path.exists():
                temp_path = self.file_registry.get_temp_path(file_name)
                logger.info(f"Copying {config.path} to {temp_path}")
                shutil.copy2(config.path, temp_path)
            elif config.use_safety_copy and not config.path.exists():
                # Create empty file if it doesn't exist
                temp_path = self.file_registry.get_temp_path(file_name)
                logger.warning(f"{config.path} not found, creating empty {temp_path}")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)

    def _save_session(self) -> None:
        """Save the current session to file."""
        if self.active_session is None:
            return
        
        with open(self.session_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.active_session.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
    
    def _load_session(self) -> None:
        """Load session from file if it exists."""
        if not self.session_file_path.exists():
            logger.debug("No session file found")
            return
        
        try:
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.active_session = Session.model_validate(session_data)
            logger.info(f"Loaded existing session: {self.active_session.id} with {len(self.active_session.messages)} messages")
            
            # Check if temp files exist for all files that need them
            for file_name, config in self.file_registry.files.items():
                if config.use_safety_copy:
                    temp_path = self.file_registry.get_temp_path(file_name)
                    if not temp_path.exists() and config.path.exists():
                        # Recreate temp file from original
                        logger.warning(f"Session exists but {temp_path} missing, recreating from {config.path}")
                        shutil.copy2(config.path, temp_path)
                
        except Exception as e:
            # If session loading fails, remove corrupted file
            logger.error(f"Failed to load session: {e}")
            self.session_file_path.unlink()
            logger.warning("Removed corrupted session file")

    
    
    def _get_context_from_registry(self) -> list[AgentContextBlock]:
        """Get context from registered files (multi-file mode)."""
        result = []

        # Add game status models documentation
        result.append(AgentContextBlock(
            context_name="game_status_models",
            content=extract_model_docs()
        ))

        # Add palio specification if registered
        if "palio" in self.file_registry.files:
            config = self.file_registry.get_config("palio")
            active_path = self.file_registry.get_active_path("palio")
            if active_path and active_path.exists():
                with open(active_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    result.append(AgentContextBlock(
                        context_name="palio_specification",
                        content=json.dumps(content, indent=4),
                    ))
                    
                    # Add game ID mapping
                    ids = '\n'.join([f"{game['id']} - {game['name']}" for game in content['games']])
                    result.append(AgentContextBlock(
                        context_name="palio_game_id_mapping",
                        content=ids,
                    ))

        # Add current leaderboard if registered
        if "leaderboard" in self.file_registry.files:
            config = self.file_registry.get_config("leaderboard")
            active_path = self.file_registry.get_active_path("leaderboard")
            if active_path and active_path.exists():
                with open(active_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    result.append(AgentContextBlock(
                        context_name="current_leaderboard",
                        content=json.dumps(content, indent=4),
                    ))

        # Add palio games status if registered
        if "palio_games_status" in self.file_registry.files:
            config = self.file_registry.get_config("palio_games_status")
            active_path = self.file_registry.get_active_path("palio_games_status")
            if active_path and active_path.exists():
                with open(active_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    result.append(AgentContextBlock(
                        context_name="palio_games_status",
                        content=json.dumps(content, indent=4),
                    ))

        return result
