# The generic agent loop — manages the back-and-forth between Claude and your tools.
#
# The Anthropic API doesn't run tools for you. When Claude wants to call a tool,
# it returns stop_reason="tool_use" instead of a final answer. This loop executes
# the tool, sends the result back, and keeps going until Claude says "end_turn"
# or we hit max_steps and give up.
#
# Tools are passed as a list[Tool] — each Tool object carries both the Anthropic
# schema (what Claude sees) and the handler (what we run). One object, one place
# to look, instead of keeping a schema list and a handler dict in sync separately.

import dataclasses
import json
from typing import Any

from sqlalchemy.orm import Session

from app.ai.client import call_llm
from app.ai.tools import Tool


class AgentError(Exception):
    """Raised when the loop hits max_steps without Claude reaching end_turn."""


@dataclasses.dataclass
class AgentStep:
    """One tool call made during a run_agent() execution."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_result: Any


@dataclasses.dataclass
class AgentResult:
    """What run_agent() returns: Claude's final text plus a trace of every tool call."""

    text: str
    steps: list[AgentStep]


def run_agent(
    *,
    feature: str,
    messages: list[dict],
    system: list[dict],
    tools: list[Tool],
    model: str,
    max_steps: int = 8,
    db: Session,
) -> AgentResult:
    """Run the tool-use loop until Claude says end_turn or max_steps is exceeded.

    tools — list of Tool objects. Each Tool carries both the Anthropic schema
            (what Claude sees) and the handler (what we run when Claude calls it).
    """
    steps: list[AgentStep] = []
    history = list(messages)  # copy so we don't mutate the caller's list

    # Build a name → Tool lookup once so each iteration is O(1).
    # tool_schemas is what we send to Claude; tool_map is what we use to run handlers.
    tool_map: dict[str, Tool] = {t.name: t for t in tools}
    tool_schemas = [t.schema for t in tools] if tools else None

    for _ in range(max_steps):
        response = call_llm(
            feature=feature,
            model=model,
            system=system,
            messages=list(history),  # snapshot per iteration
            tools=tool_schemas,
            db=db,
        )

        # Any stop reason other than "tool_use" means Claude is done.
        # This covers "end_turn" (normal finish) and "max_tokens" (truncated).
        if response.stop_reason != "tool_use":
            return AgentResult(text=_extract_text(response.content), steps=steps)

        # Claude wants to call one or more tools. Run each one and collect results.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _run_tool(block.name, dict(block.input), tool_map)
            steps.append(AgentStep(
                tool_name=block.name,
                tool_input=dict(block.input),
                tool_result=result,
            ))
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": _to_str(result),
            })

        # Add the assistant's response and tool results to history so the
        # next Claude call has the full picture of what just happened.
        history += [
            {"role": "assistant", "content": _blocks_to_dicts(response.content)},
            {"role": "user", "content": tool_results},
        ]

    raise AgentError(
        f"Agent loop exceeded max_steps={max_steps} without reaching end_turn."
    )


def _run_tool(name: str, tool_input: dict, tool_map: dict) -> Any:
    """Call the named tool's run() method, or return an error dict if unknown.

    Returning an error dict (instead of raising) lets Claude see the error message
    and potentially react — e.g. try a different tool or ask the user to clarify.
    """
    t = tool_map.get(name)
    if t is None:
        return {"error": f"Unknown tool: {name}"}
    return t.run(**tool_input)


def _extract_text(content: list) -> str:
    """Join all TextBlock.text values from a response content list."""
    return "\n".join(block.text for block in content if block.type == "text")


def _to_str(result: Any) -> str:
    """Serialize a tool result to a string for the tool_result message."""
    if isinstance(result, (dict, list)):
        return json.dumps(result)
    return str(result)


def _blocks_to_dicts(content: list) -> list[dict]:
    """Convert SDK content blocks to plain dicts so message history stays SDK-free."""
    out = []
    for block in content:
        if block.type == "text":
            out.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            out.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": dict(block.input),
            })
    return out
