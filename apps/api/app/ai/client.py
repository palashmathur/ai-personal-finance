# The single entry point for every Anthropic API call in the app.
#
# Why centralise here instead of calling anthropic.messages.create() directly?
# Two reasons:
#   1. Audit log — every call records tokens and latency to ai_calls automatically.
#      Without this, cost regressions are invisible until the bill arrives.
#   2. Prompt caching wiring — cache_control is applied consistently so we don't
#      accidentally forget it on a new feature and pay full price.
#
# Think of this like a Spring @Aspect that wraps every service method call:
# you annotate once here and every caller gets observability for free.

import time
from typing import Any, Optional

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AICall

# Module-level Anthropic client — created once, reused for every call.
# This is the equivalent of a Spring singleton bean: one instance per app lifecycle.
# The client manages its own HTTP connection pool internally.
_anthropic = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def call_llm(
    *,
    feature: str,
    model: str,
    system: list[dict],
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[dict] = None,
    max_tokens: int = 4096,
    db: Session,
) -> anthropic.types.Message:
    """
    Call the LLM and record the call in the audit log.

    All AI features call this function — never the Anthropic client directly.
    This guarantees every call is tracked without any feature having to remember
    to do it themselves.

    Parameters:
        feature     — slug identifying the calling feature, e.g. "categorize", "nl_input".
                      Used to group usage stats by feature in GET /api/ai/usage.
        model       — Claude model ID, e.g. "claude-haiku-4-5", "claude-sonnet-4-6".
        system      — List of system prompt content blocks. Pass them as dicts with
                      cache_control already set if you want prompt caching on that block.
                      Example: [{"type": "text", "text": "...",
                      "cache_control": {"type": "ephemeral"}}]
        messages    — Conversation history in Anthropic's message format.
        tools       — Optional tool schemas for tool-use calls.
        tool_choice — Optional dict to force a specific tool, e.g. {"type": "tool", "name": "..."}.
        max_tokens  — Cap on output tokens. Default 4096 is fine for most features.
        db          — Active SQLAlchemy session. The audit row is committed inside this call.

    Returns:
        The raw anthropic.types.Message response. The agent loop (agent.py) reads
        stop_reason and content blocks directly from this object.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    # Record wall-clock time around the API call so we can spot slow prompts.
    started_at = time.monotonic()
    response = _anthropic.messages.create(**kwargs)
    latency_ms = int((time.monotonic() - started_at) * 1000)

    # The usage object tells us exactly how many tokens were billed.
    # cache_read_input_tokens and cache_creation_input_tokens are only present
    # when prompt caching is active — getattr with a default of 0 handles both cases.
    usage = response.usage
    audit = AICall(
        feature=feature,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        latency_ms=latency_ms,
    )
    db.add(audit)
    db.commit()

    return response
