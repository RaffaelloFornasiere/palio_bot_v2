"""Tests for the Agent tool-execution loop."""

import pytest

from palio_bot.agent.agent import Agent
from palio_bot.agent.models import (
    Message,
    TextContent,
    ToolResult,
    ToolResultContent,
    ToolUseContent,
    Tool,
)


def _echo_tool() -> Tool:
    """A trivial tool that echoes its args back as data."""

    def echo(**kwargs):
        return ToolResult(success=True, data=kwargs)

    return Tool(
        name="echo",
        description="Echo arguments back",
        parameters_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        function=echo,
    )


def _raising_tool() -> Tool:
    def boom(**kwargs):
        raise RuntimeError("boom")

    return Tool(
        name="boom",
        description="Always raises",
        parameters_schema={"type": "object", "properties": {}},
        function=boom,
    )


async def _consume(agent: Agent, user_text: str) -> list[Message]:
    user_msg = Message.text(role="user", text=user_text)
    return [msg async for msg in agent.run([user_msg])]


async def test_loop_terminates_on_text_only_response(scripted_llm_client):
    """LLM responds with text → loop ends immediately."""
    llm = scripted_llm_client([Message.text(role="assistant", text="done")])
    agent = Agent(llm_client=llm, tools={"echo": _echo_tool()})

    out = await _consume(agent, "hello")

    assert len(out) == 1
    assert isinstance(out[0].content[0], TextContent)
    assert len(llm.calls) == 1


async def test_loop_executes_tool_then_ends(scripted_llm_client):
    """LLM asks for tool → agent executes → LLM sees result → responds with text."""
    llm = scripted_llm_client(
        [
            Message(
                role="assistant",
                content=[
                    ToolUseContent(
                        tool_name="echo",
                        tool_parameters={"msg": "hi"},
                        tool_use_id="t1",
                    )
                ],
            ),
            Message.text(role="assistant", text="ok"),
        ]
    )
    agent = Agent(llm_client=llm, tools={"echo": _echo_tool()})

    out = await _consume(agent, "do it")

    assert len(out) == 3  # tool-use msg, tool-result msg, final text
    assert isinstance(out[0].content[0], ToolUseContent)
    assert isinstance(out[1].content[0], ToolResultContent)
    assert out[1].content[0].tool_result.success
    assert isinstance(out[2].content[0], TextContent)


async def test_tool_exception_becomes_tool_result_error(scripted_llm_client):
    llm = scripted_llm_client(
        [
            Message(
                role="assistant",
                content=[
                    ToolUseContent(
                        tool_name="boom", tool_parameters={}, tool_use_id="t1"
                    )
                ],
            ),
            Message.text(role="assistant", text="handled"),
        ]
    )
    agent = Agent(llm_client=llm, tools={"boom": _raising_tool()})

    out = await _consume(agent, "trigger boom")

    tool_result_msgs = [
        m for m in out if m.content and isinstance(m.content[0], ToolResultContent)
    ]
    assert len(tool_result_msgs) == 1
    assert not tool_result_msgs[0].content[0].tool_result.success
    assert "boom" in tool_result_msgs[0].content[0].tool_result.error


async def test_unknown_tool_returns_error_not_crash(scripted_llm_client):
    llm = scripted_llm_client(
        [
            Message(
                role="assistant",
                content=[
                    ToolUseContent(
                        tool_name="does_not_exist",
                        tool_parameters={},
                        tool_use_id="t1",
                    )
                ],
            ),
            Message.text(role="assistant", text="recovered"),
        ]
    )
    agent = Agent(llm_client=llm, tools={"echo": _echo_tool()})

    out = await _consume(agent, "bad tool")

    tool_result_msgs = [
        m for m in out if m.content and isinstance(m.content[0], ToolResultContent)
    ]
    assert len(tool_result_msgs) == 1
    assert not tool_result_msgs[0].content[0].tool_result.success


async def test_cancellation_stops_loop_before_llm(scripted_llm_client):
    llm = scripted_llm_client([])  # should never be called
    agent = Agent(llm_client=llm, tools={"echo": _echo_tool()})

    user_msg = Message.text(role="user", text="hello")
    out = [msg async for msg in agent.run([user_msg], cancellation_check=lambda: True)]

    assert len(out) == 1
    assert "cancelled" in out[0].content[0].text.lower()
    assert llm.calls == []


async def test_cancellation_stops_between_tool_uses(scripted_llm_client):
    """Cancellation after first LLM response interrupts the loop before executing tools."""
    fired = {"count": 0}

    def check():
        fired["count"] += 1
        return fired["count"] > 1  # cancel after first check (before LLM call #2)

    llm = scripted_llm_client(
        [
            Message(
                role="assistant",
                content=[
                    ToolUseContent(
                        tool_name="echo", tool_parameters={"msg": "x"}, tool_use_id="t1"
                    )
                ],
            ),
        ]
    )
    agent = Agent(llm_client=llm, tools={"echo": _echo_tool()})

    user_msg = Message.text(role="user", text="hello")
    out = [msg async for msg in agent.run([user_msg], cancellation_check=check)]

    # LLM called once, tool executed, then cancel detected → cancellation message yielded
    assert any("cancelled" in (c.text if isinstance(c, TextContent) else "").lower()
               for msg in out for c in msg.content)
