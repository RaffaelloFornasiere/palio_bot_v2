"""
Audio transcription service using Groq Whisper API
"""

import logging
import tempfile
import os
from typing import Optional
from pathlib import Path

from groq import Groq

from palio_bot.config import Config

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """Service for transcribing audio using Groq Whisper API"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        
        if config.groq_api_key:
            self.client = Groq(api_key=config.groq_api_key)
        else:
            logger.warning("Groq API key not found, audio transcription will be disabled")
    
    async def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Transcribe audio file using Groq Whisper API
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.client:
            logger.error("Groq client not initialized - missing API key")
            return None
            
        try:
            with open(audio_file_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3-turbo",
                    language="it",  # Italian language
                    response_format="text"
                )
                
            # Clean up temporary file
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                
            return transcription.strip()
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            # Clean up temporary file on error
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
            return None
    
    async def download_and_transcribe(self, file_url: str, bot_instance) -> Optional[str]:
        """
        Download audio file from Telegram and transcribe it
        
        Args:
            file_url: Telegram file URL
            bot_instance: Telegram bot instance
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.client:
            logger.error("Groq client not initialized - missing API key")
            return None
            
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Download file from Telegram
            file = await bot_instance.get_file(file_url)
            await file.download_to_drive(temp_path)
            
            # Transcribe the audio
            transcription = await self.transcribe_audio(temp_path)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Error downloading and transcribing audio: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if audio transcription service is available"""
        return self.client is not None