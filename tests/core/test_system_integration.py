"""Phase 4 integration test: System ↔ core via RemoteFileStore.

Uses a scripted LLM that views leaderboard, sets a field, returns text.
Verifies System creates a remote session, the tool's edits land in the
session's staged content, and `save_session` commits to canonical.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from palio_bot.agent.agent import Agent
from palio_bot.agent.models import (
    Message,
    TextContent,
    ToolUseContent,
)
from palio_bot.config import Config
from palio_bot.core.app import create_app
from palio_bot.core_client.client import CoreClient
from palio_bot.core_client.file_store_remote import RemoteFileStore
from palio_bot.stream.stream import Stream
from palio_bot.system import System
from palio_bot.tools.multi_json_editor_tool import create_multi_json_editor_tools

from tests.core.conftest import LEADERBOARD_SEED


@pytest.fixture
def system_bundle(core_config, scripted_llm_client, tmp_path):
    """Hand-wired System pointed at an in-process core via TestClient."""
    app = create_app(core_config, enable_leaderboard_hook=False)
    tc = TestClient(app)

    core_client = CoreClient(base_url="http://testserver", http_client=tc)
    remote_store = RemoteFileStore(core_client)

    from palio_bot.tools.file_registry import FileConfig, FileRegistry

    registry = FileRegistry()
    registry.register(
        "palio",
        FileConfig(
            path=core_config.palio_file_path,
            allow_edit=False,
            use_safety_copy=False,
        ),
    )
    registry.register(
        "palio_games_status",
        FileConfig(
            path=core_config.palio_games_status_path,
            allow_edit=True,
            use_safety_copy=False,
        ),
    )
    registry.register(
        "leaderboard",
        FileConfig(
            path=core_config.leaderboard_file_path,
            allow_edit=True,
            use_safety_copy=False,
        ),
    )

    tools_dict = create_multi_json_editor_tools(registry, file_store=remote_store)

    # Scripted LLM: view leaderboard → set villa points → final text.
    updated = {
        **LEADERBOARD_SEED,
        "palio_leaderboard": {
            "villa": {"points": 200, "position": 1},
            "salt": {"points": 0, "position": 2},
        },
    }
    llm = scripted_llm_client(
        [
            Message(
                role="assistant",
                content=[
                    ToolUseContent(
                        tool_name="json_view",
                        tool_parameters={"file_name": "leaderboard"},
                        tool_use_id="t1",
                    )
                ],
            ),
            Message(
                role="assistant",
                content=[
                    ToolUseContent(
                        tool_name="json_set",
                        tool_parameters={
                            "file_name": "leaderboard",
                            "path": "$.palio_leaderboard",
                            "value": updated["palio_leaderboard"],
                        },
                        tool_use_id="t2",
                    )
                ],
            ),
            Message.text(role="assistant", text="Done."),
        ]
    )

    agent = Agent(llm_client=llm, tools=tools_dict)
    stream = Stream()

    sys_config = Config(
        palio_core_url="http://testserver",
        session_file_path=tmp_path / "session.json",
        openrouter_api_key="dummy",  # only needed for provider validation
    )

    system = System(
        agent=agent,
        stream=stream,
        file_registry=registry,
        core_client=core_client,
        remote_file_store=remote_store,
        label="test",
        config=sys_config,
    )

    yield system, core_client, remote_store
    tc.close()


async def test_system_commits_through_core(system_bundle, core_data_dir: Path):
    system, client, _ = system_bundle

    # Initially no remote session
    assert system.remote_session_id is None

    await system.send_message("bump villa to 200")

    # Remote session created
    assert system.remote_session_id is not None

    # Pre-commit: canonical unchanged
    pre = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert pre["palio_leaderboard"]["villa"]["points"] == 0

    # save_session commits staged → canonical
    system.save_session()

    post = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert post["palio_leaderboard"]["villa"]["points"] == 200

    # After save_session, a fresh remote session was started.
    fresh_session_id = system.remote_session_id
    assert fresh_session_id is not None


async def test_close_session_with_discard_leaves_canonical(
    system_bundle, core_data_dir: Path
):
    system, _, _ = system_bundle

    await system.send_message("bump villa to 200")
    system.close_session(save_changes=False)

    on_disk = json.loads((core_data_dir / "leaderboard.json").read_text())
    assert on_disk["palio_leaderboard"]["villa"]["points"] == 0
    assert system.active_session is None
    assert system.remote_session_id is None
