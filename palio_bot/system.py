"""System coordinator with event streaming support."""

import json
import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional

from palio_bot.agent.models import Message, Session
from palio_bot.agent.agent import Agent
from palio_bot.stream.stream import Stream

logger = logging.getLogger(__name__)


class System:
    """Main coordinator that manages sessions and orchestrates agent interactions with event streaming."""
    
    def __init__(
        self, 
        agent: Agent,
        stream: Stream,
        palio_file_path: str = "palio.json",
        session_file_path: str = "session.json"
    ):
        self.agent = agent
        self.stream = stream
        self.palio_file_path = Path(palio_file_path)
        self.session_file_path = Path(session_file_path)
        self.active_session: Optional[Session] = None
        self.palio_updated_path = Path("palio_updated.json")
        
        logger.info(f"System initialized with palio_file: {palio_file_path}")
        
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
            response_message = await self.agent.run(
                message=user_message,
                session_id=self.active_session.id,
                context=context
            )
            logger.info("Agent processing complete")
            
            # Add messages to session for persistence
            user_msg = Message.text(role="user", text=user_message)
            self.active_session.add_message(user_msg)
            self.active_session.add_message(response_message)
            
            # Save session after interaction
            logger.debug("Saving session")
            self._save_session()
            logger.info("Session saved successfully")
            
            logger.info("System.send_message() completed successfully")
            return response_message
            
        except Exception as e:
            import traceback
            logger.error(f"Error in send_message: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise
    
    def close_session(self) -> None:
        """Close the active session normally, copying palio_updated.json to palio.json."""
        if self.active_session is None:
            logger.warning("close_session called but no active session")
            return
        
        logger.info(f"Closing session {self.active_session.id}")
        
        # Copy palio_updated.json to palio.json
        if self.palio_updated_path.exists():
            logger.info(f"Copying {self.palio_updated_path} to {self.palio_file_path}")
            shutil.copy2(self.palio_updated_path, self.palio_file_path)
            self.palio_updated_path.unlink()  # Remove palio_updated.json
            logger.info("Changes saved to palio.json")
        else:
            logger.warning("palio_updated.json not found, nothing to save")
        
        self.active_session = None
        
        # Remove session file
        if self.session_file_path.exists():
            self.session_file_path.unlink()
    
    def cancel_session(self) -> None:
        """Cancel the active session and discard changes in palio_updated.json."""
        if self.active_session is None:
            return
        
        # Simply remove palio_updated.json to discard changes
        if self.palio_updated_path.exists():
            self.palio_updated_path.unlink()
        
        self.active_session = None
        
        # Remove session file
        if self.session_file_path.exists():
            self.session_file_path.unlink()
    
    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session."""
        return self.active_session
    
    def _create_session(self) -> None:
        """Create a new session and copy palio.json to palio_updated.json."""
        session_id = str(uuid.uuid4())
        self.active_session = Session(id=session_id)
        logger.info(f"Created new session: {session_id}")
        
        # Copy palio.json to palio_updated.json for editing
        if self.palio_file_path.exists():
            logger.info(f"Copying {self.palio_file_path} to {self.palio_updated_path}")
            shutil.copy2(self.palio_file_path, self.palio_updated_path)
        else:
            # Create empty palio_updated.json if palio.json doesn't exist
            logger.warning(f"{self.palio_file_path} not found, creating empty {self.palio_updated_path}")
            with open(self.palio_updated_path, 'w', encoding='utf-8') as f:
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
            
            # Check if palio_updated.json exists (session was interrupted)
            if not self.palio_updated_path.exists() and self.palio_file_path.exists():
                # Recreate palio_updated.json from palio.json
                logger.warning("Session exists but palio_updated.json missing, recreating from palio.json")
                shutil.copy2(self.palio_file_path, self.palio_updated_path)
                
        except Exception as e:
            # If session loading fails, remove corrupted file
            logger.error(f"Failed to load session: {e}")
            self.session_file_path.unlink()
            logger.warning("Removed corrupted session file")
    
    def _get_palio_context_string(self) -> str:
        """Get original palio.json content as a string context."""
        if not self.palio_file_path.exists():
            return "File palio.json non trovato."
        
        try:
            with open(self.palio_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return f"Contenuto attuale di {self.palio_file_path.name}:\n```json\n{content}```"
            
        except Exception as e:
            return f"Errore nel leggere {self.palio_file_path.name}: {str(e)}"