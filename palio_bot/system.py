"""System coordinator for managing sessions and agent interactions."""

import json
import uuid
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .models import Message, Session, TextContent, Tool
from .agent import Agent


class System:
    """Main coordinator that manages sessions and orchestrates agent interactions."""
    
    def __init__(
        self, 
        agent: Agent, 
        palio_file_path: str = "palio.json",
        session_file_path: str = "session.json"
    ):
        self.agent = agent
        self.palio_file_path = Path(palio_file_path)
        self.session_file_path = Path(session_file_path)
        self.active_session: Optional[Session] = None
        self.palio_updated_path = Path("palio_updated.json")
        
        # Load existing session if available
        self._load_session()
    
    async def send_message(self, user_message: str) -> Message:
        """Send a message to the system.
        
        If there's an active session, continue the conversation.
        Otherwise, create a new session.
        
        Args:
            user_message: User's message text
            
        Returns:
            The final assistant response message
        """
        try:
            # Create new session if none exists
            if self.active_session is None:
                print("🔧 Creating new session...")
                self._create_session()
            
            # Add user message to session
            print("📝 Adding user message to session...")
            user_msg = Message.text(role="user", text=user_message)
            self.active_session.add_message(user_msg)
            
            # Get current palio.json content as context
            print("📄 Getting palio.json context...")
            context = self._get_palio_context()
            
            # Process messages through agent
            print("🤖 Processing messages through agent...")
            response_messages = await self.agent.process_messages(
                messages=self.active_session.messages,
                context=context
            )
            
            print(f"📨 Received {len(response_messages)} response messages")
            
            # Add all response messages to session
            for msg in response_messages:
                self.active_session.add_message(msg)
            
            # Save session after interaction
            print("💾 Saving session...")
            self._save_session()
            
            # Return the final assistant message (last text message)
            for msg in reversed(response_messages):
                if msg.role == "assistant" and any(
                    isinstance(content, TextContent) for content in msg.content
                ):
                    print("✅ Found assistant text message")
                    return msg
            
            # Fallback: return last message
            print("⚠️ No assistant text message found, returning last message")
            return response_messages[-1] if response_messages else Message.text(
                role="assistant", 
                text="Nessuna risposta disponibile."
            )
            
        except Exception as e:
            print(f"💥 Error in send_message: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def close_session(self) -> None:
        """Close the active session normally, copying palio_updated.json to palio.json."""
        if self.active_session is None:
            return
        
        # Copy palio_updated.json to palio.json
        if self.palio_updated_path.exists():
            shutil.copy2(self.palio_updated_path, self.palio_file_path)
            self.palio_updated_path.unlink()  # Remove palio_updated.json
        
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
        
        # Copy palio.json to palio_updated.json for editing
        if self.palio_file_path.exists():
            shutil.copy2(self.palio_file_path, self.palio_updated_path)
        else:
            # Create empty palio_updated.json if palio.json doesn't exist
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
            return
        
        try:
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.active_session = Session.model_validate(session_data)
            
            # Check if palio_updated.json exists (session was interrupted)
            if not self.palio_updated_path.exists() and self.palio_file_path.exists():
                # Recreate palio_updated.json from palio.json
                shutil.copy2(self.palio_file_path, self.palio_updated_path)
                
        except Exception as e:
            # If session loading fails, remove corrupted file
            self.session_file_path.unlink()
            print(f"Sessione corrotta rimossa: {e}")
    
    def _get_palio_context(self) -> List[TextContent]:
        """Get original palio.json content as context (not palio_updated.json)."""
        if not self.palio_file_path.exists():
            return [TextContent(text="File palio.json non trovato.")]
        
        try:
            with open(self.palio_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return [TextContent(text=f"Contenuto attuale di {self.palio_file_path.name}:\n```json\n{content}```")]
            
        except Exception as e:
            return [TextContent(text=f"Errore nel leggere {self.palio_file_path.name}: {str(e)}")]