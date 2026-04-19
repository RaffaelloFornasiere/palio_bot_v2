"""Shared pytest fixtures for palio_bot tests."""

import json
from pathlib import Path
from typing import List, Optional

import pytest
from pydantic import BaseModel

from palio_bot.agent.models import Message, TextContent, Tool
from palio_bot.llm_clients.base_client import BaseLLMClient
from palio_bot.tools.file_registry import FileConfig, FileRegistry


class SimplePalio(BaseModel):
    """Minimal validator for test files — accepts any dict shape."""

    class Config:
        extra = "allow"


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temp directory pre-seeded with palio data files."""
    data = tmp_path / "data"
    data.mkdir()

    (data / "palio.json").write_text(
        json.dumps(
            {
                "palio": {
                    "anno": 2026,
                    "eventi": [
                        {"id": "corsa", "nome": "Corsa dei sacchi"},
                        {"id": "calcetto", "nome": "Calcetto"},
                    ],
                }
            },
            ensure_ascii=False,
        )
    )

    (data / "palio_games_status.json").write_text(
        json.dumps(
            {
                "game_scores": {
                    "calcetto": {
                        "status": "not-started",
                        "scores": {"villa": 0, "salt": 0, "sottocastello": 0},
                        "applied_bonuses": [],
                        "applied_penalties": [],
                        "score_penalties": [],
                    }
                },
                "last_updated": "2026-04-01T00:00:00Z",
            },
            ensure_ascii=False,
        )
    )

    (data / "leaderboard.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"village": "villa", "points": 0},
                    {"village": "salt", "points": 0},
                    {"village": "sottocastello", "points": 0},
                ]
            },
            ensure_ascii=False,
        )
    )

    return data


@pytest.fixture
def registry(tmp_data_dir: Path) -> FileRegistry:
    """File registry wired to the temp data dir, no validators (for editor tests)."""
    reg = FileRegistry()
    reg.register(
        "palio",
        FileConfig(
            path=tmp_data_dir / "palio.json",
            allow_edit=False,
            use_safety_copy=False,
        ),
    )
    reg.register(
        "palio_games_status",
        FileConfig(
            path=tmp_data_dir / "palio_games_status.json",
            allow_edit=True,
            use_safety_copy=False,
        ),
    )
    reg.register(
        "leaderboard",
        FileConfig(
            path=tmp_data_dir / "leaderboard.json",
            allow_edit=True,
            use_safety_copy=False,
        ),
    )
    return reg


class ScriptedLLMClient(BaseLLMClient):
    """LLM client that returns pre-scripted messages in order."""

    def __init__(self, responses: List[Message]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def generate_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        context: Optional[List[TextContent]] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Message:
        self.calls.append(
            {
                "messages": messages,
                "system_prompt": system_prompt,
                "context": context,
                "tools": tools,
            }
        )
        if not self.responses:
            raise AssertionError("ScriptedLLMClient ran out of responses")
        return self.responses.pop(0)


@pytest.fixture
def scripted_llm_client():
    """Factory: pass a list of Messages, get a ScriptedLLMClient."""

    def _make(responses: List[Message]) -> ScriptedLLMClient:
        return ScriptedLLMClient(responses)

    return _make
