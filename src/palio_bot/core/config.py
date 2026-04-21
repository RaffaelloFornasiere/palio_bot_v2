"""Core-only settings. Independent of adapter-side LLM config.

Scope: file paths, HTTP port, bearer token, CORS. No LLM keys — core
never talks to an LLM.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    palio_file_path: Path = Path("data/palio.json")
    palio_games_status_path: Path = Path("data/palio_games_status.json")
    leaderboard_file_path: Path = Path("data/leaderboard.json")
    data_dir: Path = Path("data")

    port: int = Field(default=8000, alias="PALIO_CORE_PORT")
    bearer_token: Optional[str] = Field(default=None, alias="PALIO_CORE_TOKEN")

    cors_allowed_origins: Optional[str] = Field(
        default=None, alias="CORS_ALLOWED_ORIGINS"
    )

    def allowed_origins_list(self) -> list[str]:
        if self.cors_allowed_origins:
            return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
