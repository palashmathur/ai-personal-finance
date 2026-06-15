# Tests for the generic agent loop: app/ai/agent.py
#
# We never call the Anthropic API here. Instead, we patch call_llm and feed it
# pre-scripted fake responses. This lets us test every branch of the loop
# (end_turn, single tool, multiple tools, max_steps exceeded, unknown tool)
# without a network connection or API key.
#
# PF-21 update: tools are now Tool objects instead of separate schema dicts +
# handler dicts. _ADD_NUMBERS_TOOL below is the single source of truth for both
# the schema and the handler used across all tests.

import dataclasses
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from app.ai.agent import AgentError, AgentResult, run_agent
from app.ai.tools import Tool

# ---------------------------------------------------------------------------
# Fake Anthropic response objects
# ---------------------------------------------------------------------------
# These match only the attributes that run_agent() actually reads, so we don't
# need to import anything from the anthropic package in this test file.


@dataclasses.dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclasses.dataclass
class FakeToolUseBlock:
    name: str
    input: dict
    id: str = "toolu_01"
    type: str = "tool_use"


@dataclasses.dataclass
class FakeMessage:
    stop_reason: str
    content: list


# ---------------------------------------------------------------------------
# Builder helpers — make test cases read like plain English
# ---------------------------------------------------------------------------


def _end_turn(text: str = "Done.") -> FakeMessage:
    return FakeMessage(stop_reason="end_turn", content=[FakeTextBlock(text=text)])


def _tool_use(name: str, tool_input: dict, tool_id: str = "toolu_01") -> FakeMessage:
    return FakeMessage(
        stop_reason="tool_use",
        content=[FakeToolUseBlock(id=tool_id, name=name, input=tool_input)],
    )


# ---------------------------------------------------------------------------
# Test tool — replaces the old _TOOLS dict + _HANDLERS dict
# ---------------------------------------------------------------------------
# Tool objects bundle schema + handler together (that's the whole point of PF-21).
# We create a simple add_numbers Tool directly so no TOOL_REGISTRY side effects
# bleed between test modules.


class _AddInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


def _add_numbers_handler(params: _AddInput) -> int:
    return params.a + params.b


_ADD_NUMBERS_TOOL = Tool(
    name="add_numbers",
    description="Add two integers.",
    input_model=_AddInput,
    handler=_add_numbers_handler,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SYSTEM = [{"type": "text", "text": "You are a test assistant."}]
_MESSAGES = [{"role": "user", "content": "Hello"}]


def _run(**kwargs):
    """Thin wrapper so tests don't have to repeat boilerplate kwargs."""
    defaults = dict(
        feature="test",
        messages=_MESSAGES,
        system=_SYSTEM,
        tools=[_ADD_NUMBERS_TOOL],
        model="claude-haiku-4-5",
        db=MagicMock(),
    )
    defaults.update(kwargs)
    return run_agent(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("app.ai.agent.call_llm")
def test_end_turn_immediately(mock_call_llm):
    """Claude answers without calling any tool — loop runs exactly once."""
    mock_call_llm.return_value = _end_turn("Hello back.")

    result = _run()

    assert isinstance(result, AgentResult)
    assert result.text == "Hello back."
    assert result.steps == []
    assert mock_call_llm.call_count == 1


@patch("app.ai.agent.call_llm")
def test_single_tool_call(mock_call_llm):
    """Claude calls one tool then ends — two call_llm invocations total."""
    mock_call_llm.side_effect = [
        _tool_use("add_numbers", {"a": 3, "b": 4}),
        _end_turn("The answer is 7."),
    ]

    result = _run()

    assert result.text == "The answer is 7."
    assert len(result.steps) == 1

    step = result.steps[0]
    assert step.tool_name == "add_numbers"
    assert step.tool_input == {"a": 3, "b": 4}
    assert step.tool_result == 7

    assert mock_call_llm.call_count == 2


@patch("app.ai.agent.call_llm")
def test_two_sequential_tool_calls(mock_call_llm):
    """Claude calls a tool twice in separate turns, each with different args."""
    mock_call_llm.side_effect = [
        _tool_use("add_numbers", {"a": 1, "b": 2}, tool_id="toolu_01"),
        _tool_use("add_numbers", {"a": 10, "b": 20}, tool_id="toolu_02"),
        _end_turn("All done."),
    ]

    result = _run()

    assert result.text == "All done."
    assert len(result.steps) == 2
    assert result.steps[0].tool_result == 3
    assert result.steps[1].tool_result == 30
    assert mock_call_llm.call_count == 3


@patch("app.ai.agent.call_llm")
def test_max_steps_raises_agent_error(mock_call_llm):
    """Loop never reaches end_turn → AgentError raised after max_steps iterations."""
    # Always returns tool_use so the loop never exits naturally.
    mock_call_llm.return_value = _tool_use("add_numbers", {"a": 1, "b": 1})

    with pytest.raises(AgentError):
        _run(max_steps=3)

    # Should have called call_llm exactly max_steps times before giving up.
    assert mock_call_llm.call_count == 3


@patch("app.ai.agent.call_llm")
def test_unknown_tool_records_error_and_continues(mock_call_llm):
    """Calling a tool not in the tools list records an error result — loop continues."""
    mock_call_llm.side_effect = [
        _tool_use("nonexistent_tool", {"x": 99}),
        _end_turn("Handled gracefully."),
    ]

    result = _run(tools=[])  # empty list — no tools registered

    assert result.text == "Handled gracefully."
    assert len(result.steps) == 1
    assert result.steps[0].tool_name == "nonexistent_tool"
    assert "error" in result.steps[0].tool_result


@patch("app.ai.agent.call_llm")
def test_steps_passed_to_call_llm_on_second_iteration(mock_call_llm):
    """After a tool call, the next call_llm receives a longer message list with the tool result."""
    mock_call_llm.side_effect = [
        _tool_use("add_numbers", {"a": 5, "b": 5}),
        _end_turn("10."),
    ]

    _run()

    # Second call must include more messages than the first (assistant + tool_result appended).
    first_call_messages = mock_call_llm.call_args_list[0].kwargs["messages"]
    second_call_messages = mock_call_llm.call_args_list[1].kwargs["messages"]
    assert len(second_call_messages) > len(first_call_messages)
