"""Base configuration"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class Config:
    palio_file_path: Path = Path("data/palio.json")
    palio_games_status_path: Path = Path("data/palio_games_status.json")
    palio_updated_path: Path = Path("data/palio_games_status_tmp.json")
    leaderboard_file_path: Path = Path("data/leaderboard.json")
    session_file_path: Path = Path("data/session.json")

    # Anthropic Configuration
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-sonnet-4-20250514"

    # llama.cpp Configuration
    llama_cpp_url: str = "http://mac-studio.local:11454"

    # Groq Configuration
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    
    # General LLM Configuration
    llm_provider: str = "llamacpp"
    max_tokens: int = 8192
    cache_responses: bool = True


