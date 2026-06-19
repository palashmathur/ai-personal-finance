# Factory for LangChain chat-model instances.
#
# Every feature that needs an LLM goes through get_llm(). The factory hides
# two concerns from callers:
#   1. Constructing the chat model with the right API key, model ID, and limits.
#   2. Attaching the AuditCallbackHandler so every call writes one ai_calls row.
#
# Centralising the construction means cross-cutting concerns (audit, tracing
# metadata, retries, future provider routing) live in one place instead of
# being scattered across every feature module. Spring analogy: this is a
# @Bean-producing method on a @Configuration class — one place that knows how
# to assemble the dependency correctly, and callers just ask.

from langchain_anthropic import ChatAnthropic

from app.ai.audit import AuditCallbackHandler
from app.config import settings


def get_llm(
    model: str,
    feature: str,
    max_tokens: int = 4096,
) -> ChatAnthropic:
    """
    Build a chat-model instance pre-wired with auditing and a feature tag.

    Parameters
    ----------
    model       LLM model ID for the configured provider. Pick a model that
                matches the feature's needs — cheap/fast for high-volume routing
                tasks (categorize), stronger models for narration or reasoning
                (NL input, insights, chat), and the largest only when the user
                explicitly asks for deep analysis.
    feature     Slug identifying the caller — e.g. "categorize", "nl_input",
                "chat". Flows into:
                  - the ai_calls audit row (so GET /api/ai/usage can group by feature)
                  - the LangSmith trace metadata once tracing is enabled
    max_tokens  Cap on output tokens. 4096 covers every feature we have so far.

    Returns
    -------
    A chat-model instance you can call .invoke(messages) / .stream(messages) on.
    The audit callback fires automatically on every call — no extra wiring
    needed at the feature level.
    """
    return ChatAnthropic(
        model=model,
        anthropic_api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        # The callback fires on every .invoke() / .stream() of this instance
        # and writes one ai_calls row per call. Attaching it here means feature
        # code never has to remember to audit — by the time .invoke() returns,
        # the row exists.
        callbacks=[AuditCallbackHandler(feature=feature)],
        # metadata flows into the LangSmith trace context when tracing is
        # enabled. Tagging the feature here makes traces filterable by feature
        # in the LangSmith UI.
        metadata={"feature": feature},
    )
