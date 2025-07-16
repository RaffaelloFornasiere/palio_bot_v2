"""System coordinator with event streaming support."""

import json
import os
import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional

from palio_bot.agent.models import Message, Session, AgentContextBlock
from palio_bot.agent.agent import Agent
from palio_bot.stream.stream import Stream
from palio_bot.config import Config
from palio_bot.leaderboard_updater import LeaderboardUpdater

logger = logging.getLogger(__name__)


class System:
    """Main coordinator that manages sessions and orchestrates agent interactions with event streaming."""
    
    def __init__(
        self,
            *,
        agent: Agent,
        stream: Stream,
        config: Config = None,
    ):
        self.agent = agent
        self.stream = stream
        self.active_session: Optional[Session] = None
        
        if config is None:
            config = Config()
            
        self.palio_file_path = config.palio_file_path
        self.palio_games_status_path = config.palio_games_status_path
        self.leader_board_file_path = config.leaderboard_file_path
        self.session_file_path = config.session_file_path
        self.palio_games_status_temp_path = config.palio_games_status_temp_path
        
        logger.info(f"System initialized with palio_file: {self.palio_file_path}")
        
        # Load existing session if available
        self._load_session()
    
    async def send_message(self, user_message: str) -> Message:
        """Send a message to the system with event streaming.
        
        If there's an active session, continue the conversation.
        Otherwise, create a new session.
        
        Args:
            user_message: User's message text
            
        Returns:
            The final assistant response message
        """
        logger.info(f"\n{'='*60}\nSystem.send_message() called\nMessage: {user_message}\n{'='*60}")
        
        try:
            # Create new session if none exists
            if self.active_session is None:
                logger.info("No active session, creating new one")
                self._create_session()
            else:
                logger.info(f"Using existing session: {self.active_session.id}")
            
            # Get current palio.json content as context
            logger.debug("Loading palio.json context")
            context = self._get_palio_context_string()
            logger.debug(f"Context loaded: {len(context)} characters")
            
            # Process message through agent with events
            # The agent will emit events during processing
            logger.info("Calling agent.run()")
            final_message, all_messages = await self.agent.run(
                message=user_message,
                session_id=self.active_session.id,
                context=context
            )
            logger.info("Agent processing complete")
            
            # Add user message to session
            user_msg = Message.text(role="user", text=user_message)
            self.active_session.add_message(user_msg)
            
            # Add all agent messages (including tool calls and results) to session
            for msg in all_messages:
                self.active_session.add_message(msg)
            
            # Save session after interaction
            logger.debug("Saving session")
            self._save_session()
            logger.info("Session saved successfully")
            
            logger.info("System.send_message() completed successfully")
            return final_message
            
        except Exception as e:
            import traceback
            logger.error(f"Error in send_message: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise
    
    def close_session(self) -> None:
        """Close the active session normally, copying palio_games_status_temp_path.json to palio_games_status.json."""
        if self.active_session is None:
            logger.warning("close_session called but no active session")
            return
        
        logger.info(f"Closing session {self.active_session.id}")
        
        # Copy palio_games_status_temp_path.json to palio_games_status.json
        if self.palio_games_status_temp_path.exists():
            logger.info(f"Copying {self.palio_games_status_temp_path} to {self.palio_games_status_path}")
            shutil.copy2(self.palio_games_status_temp_path, self.palio_games_status_path)
            self.palio_games_status_temp_path.unlink()  # Remove palio_games_status_temp_path.json
            logger.info("Changes saved to palio.json")
            
            # Update leaderboard with completed games
            try:
                logger.info("Updating leaderboard with completed games")
                leaderboard_updater = LeaderboardUpdater(
                    self.palio_file_path,
                    self.palio_games_status_path,
                    self.leader_board_file_path
                )
                leaderboard_updater.update_leaderboard()
                logger.info("Leaderboard updated successfully")
            except Exception as e:
                logger.error(f"Error updating leaderboard: {e}")
                # Don't raise the exception to avoid breaking session closure
        else:
            logger.warning("palio_games_status_temp_path.json not found, nothing to save")
        
        self.active_session = None
        
        # Remove session file
        if self.session_file_path.exists():
            self.session_file_path.unlink()
    
    def cancel_session(self) -> None:
        """Cancel the active session and discard changes in palio_games_status_temp_path.json."""
        if self.active_session is None:
            return
        
        # Simply remove palio_games_status_temp_path.json to discard changes
        if self.palio_games_status_temp_path.exists():
            self.palio_games_status_temp_path.unlink()
        
        self.active_session = None
        
        # Remove session file
        if self.session_file_path.exists():
            self.session_file_path.unlink()
    
    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session."""
        return self.active_session
    
    def _create_session(self) -> None:
        """Create a new session and copy palio_games_status.json to palio_games_status_temp_path.json."""
        session_id = str(uuid.uuid4())
        self.active_session = Session(id=session_id)
        logger.info(f"Created new session: {session_id}")
        
        # Copy palio_games_status.json to palio_games_status_temp_path.json for editing
        if self.palio_games_status_path.exists():
            logger.info(f"Copying {self.palio_games_status_path} to {self.palio_games_status_temp_path}")
            shutil.copy2(self.palio_games_status_path, self.palio_games_status_temp_path)
        else:
            # Create empty palio_games_status_temp_path.json if palio_games_status.json doesn't exist
            logger.warning(f"{self.palio_games_status_path} not found, creating empty {self.palio_games_status_temp_path}")
            with open(self.palio_games_status_temp_path, 'w', encoding='utf-8') as f:
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
            
            # Check if palio_games_status_temp_path.json exists (session was interrupted)
            if not self.palio_games_status_temp_path.exists() and self.palio_games_status_path.exists():
                # Recreate palio_games_status_temp_path.json from palio_games_status.json
                logger.warning("Session exists but palio_games_status_temp_path.json missing, recreating from palio_games_status.json")
                shutil.copy2(self.palio_games_status_path, self.palio_games_status_temp_path)
                
        except Exception as e:
            # If session loading fails, remove corrupted file
            logger.error(f"Failed to load session: {e}")
            self.session_file_path.unlink()
            logger.warning("Removed corrupted session file")
    
    def _get_palio_context_string(self) -> list[AgentContextBlock]:
        """Get original palio.json content as a string context."""
        if not self.palio_file_path.exists():
            raise FileNotFoundError("palio.json does not exist")
        result = []
        with open(self.palio_file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)

            result.append(AgentContextBlock(
                context_name="palio_specification",
                content=json.dumps(content, indent=4),
            ))

        with open(self.leader_board_file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)

            result.append(AgentContextBlock(
                context_name="current_leaderboard",
                content=json.dumps(content, indent=4),
            ))

        return result
