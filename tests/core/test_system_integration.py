"""System ↔ core end-to-end via CoreProcess + StreamClient.

Uses a scripted LLM that views leaderboard, sets a field, returns text.
Verifies System creates a remote session, the tool's edits land in the
session's staged content, `save_session` commits to canonical, and all
events flow through the unified WS bus.
"""

import json
from pathlib import Path

import pytest

from palio_bot.agent.agent import Agent
from palio_bot.agent.models import Message, ToolUseContent
from palio_bot.config import Config
from palio_bot.core_client.client import CoreClient
from palio_bot.core_client.file_store_remote import RemoteFileStore
from palio_bot.core_client.stream_client import StreamClient
from palio_bot.core_client.subprocess import CoreProcess
from palio_bot.system import System
from palio_bot.tools.file_registry import FileConfig, FileRegistry
from palio_bot.tools.multi_json_editor_tool import create_multi_json_editor_tools

from tests.core.conftest import (
    GAMES_STATUS_SEED,
    LEADERBOARD_SEED,
    PALIO_SEED,
)


def _seed_data_dir(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "palio.json").write_text(json.dumps(PALIO_SEED))
    (data_dir / "leaderboard.json").write_text(json.dumps(LEADERBOARD_SEED))
    (data_dir / "palio_games_status.json").write_text(json.dumps(GAMES_STATUS_SEED))


@pytest.fixture
async def system_bundle(tmp_path: Path, scripted_llm_client):
    data_dir = tmp_path / "data"
    _seed_data_dir(data_dir)

    updated_leaderboard = {
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
                            "value": updated_leaderboard["palio_leaderboard"],
                        },
                        tool_use_id="t2",
                    )
                ],
            ),
            Message.text(role="assistant", text="Done."),
        ]
    )

    with CoreProcess(data_dir=data_dir) as core:
        core_client = CoreClient(base_url=core.base_url)
        remote_store = RemoteFileStore(core_client)

        registry = FileRegistry()
        registry.register(
            "palio",
            FileConfig(path=data_dir / "palio.json", allow_edit=False),
        )
        registry.register(
            "palio_games_status",
            FileConfig(path=data_dir / "palio_games_status.json", allow_edit=True),
        )
        registry.register(
            "leaderboard",
            FileConfig(path=data_dir / "leaderboard.json", allow_edit=True),
        )

        tools_dict = create_multi_json_editor_tools(registry, file_store=remote_store)
        agent = Agent(llm_client=llm, tools=tools_dict)

        stream = StreamClient(core.base_url)
        await stream.start_processing()

        sys_config = Config(
            palio_core_url=core.base_url,
            session_file_path=tmp_path / "session.json",
            openrouter_api_key="dummy",
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

        try:
            yield system, core_client, data_dir
        finally:
            await stream.stop_processing()
            core_client.close()


async def test_system_commits_through_core(system_bundle):
    system, _, data_dir = system_bundle
    assert system.remote_session_id is None

    await system.send_message("bump villa to 200")
    assert system.remote_session_id is not None

    pre = json.loads((data_dir / "leaderboard.json").read_text())
    assert pre["palio_leaderboard"]["villa"]["points"] == 0

    system.save_session()
    post = json.loads((data_dir / "leaderboard.json").read_text())
    assert post["palio_leaderboard"]["villa"]["points"] == 200
    assert system.remote_session_id is not None


async def test_close_session_with_discard_leaves_canonical(system_bundle):
    system, _, data_dir = system_bundle

    await system.send_message("bump villa to 200")
    system.close_session(save_changes=False)

    on_disk = json.loads((data_dir / "leaderboard.json").read_text())
    assert on_disk["palio_leaderboard"]["villa"]["points"] == 0
    assert system.active_session is None
    assert system.remote_session_id is None
