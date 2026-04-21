"""Typed application configuration backed by environment variables / .env."""

import logging
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


LLMProvider = Literal["openrouter", "llamacpp", "ollama"]


class Config(BaseSettings):
    """Application config.

    Fields are populated from (in order of priority):
    1. Constructor arguments
    2. Environment variables (case-insensitive)
    3. `.env` file at the project root
    4. Defaults declared below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # File paths
    palio_file_path: Path = Path("data/palio.json")
    palio_games_status_path: Path = Path("data/palio_games_status.json")
    palio_games_status_temp_path: Path = Path("data/palio_games_status_tmp.json")
    leaderboard_file_path: Path = Path("data/leaderboard.json")
    session_file_path: Path = Path("data/session.json")

    # LLM provider selection
    llm_provider: LLMProvider = "openrouter"

    # OpenRouter
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "anthropic/claude-3.5-haiku"
    openrouter_base_url: str = "https://openrouter.ai/api"

    # llama.cpp
    llama_cpp_url: str = Field(default="http://mac-studio.local:11454", alias="LLAMACPP_URL")

    # Ollama
    ollama_model: str = "mistral-optimized"
    ollama_num_gpu: int = -1  # -1 means all layers
    ollama_num_batch: int = 512
    ollama_num_thread: int = 8

    # Groq (used by audio transcription)
    groq_api_key: Optional[str] = None

    # palio-core (adapter-side client settings)
    palio_core_url: str = "http://localhost:8000"
    palio_core_token: Optional[str] = None

    @model_validator(mode="after")
    def _validate_provider_keys(self) -> "Config":
        if self.llm_provider == "openrouter" and not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter"
            )
        return self
