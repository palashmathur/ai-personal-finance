# Factory for LangChain chat-model instances.
#
# Every feature that needs an LLM goes through get_llm(). The factory hides
# three concerns from callers:
#   1. Which provider/model to build — resolved from config, not hard-coded at
#      the call site. Feature code stays provider-agnostic: it asks for a model
#      by feature name and never imports or names a concrete provider.
#   2. Constructing the chat model with the right API key and limits.
#   3. Attaching the AuditCallbackHandler so every call writes one ai_calls row.
#
# This is the ONE place in the app that knows about concrete providers. To add a
# new provider, drop a builder in _PROVIDERS below and (optionally) a default
# model in _DEFAULT_MODEL — nothing else in the codebase changes. Spring analogy:
# a @Configuration class with a @Bean factory method that picks the right
# implementation based on a property, so the rest of the app just asks for the
# interface.

from typing import Callable, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel

from app.ai.audit import AuditCallbackHandler
from app.config import settings

# Default model id per provider — used when neither the get_llm(model=...) arg
# nor settings.llm_model is set. These (and the builders below) are the only
# spots that reference provider-specific identifiers.
_DEFAULT_MODEL = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-sonnet-4-6",
}


# Each builder takes the resolved arguments and returns a ready chat model.
# Imports are done lazily inside the builder so that a provider package which
# isn't installed (or isn't used) never breaks app startup.


def _build_groq(
    *,
    model: str,
    max_tokens: int,
    callbacks: list,
    metadata: dict,
) -> BaseChatModel:
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        max_tokens=max_tokens,
        callbacks=callbacks,
        metadata=metadata,
    )


def _build_anthropic(
    *,
    model: str,
    max_tokens: int,
    callbacks: list,
    metadata: dict,
) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        anthropic_api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        callbacks=callbacks,
        metadata=metadata,
    )


# Provider registry — the lookup table get_llm() routes through. Add a new
# provider here and feature code can use it immediately via config.
_PROVIDERS: dict[str, Callable[..., BaseChatModel]] = {
    "groq": _build_groq,
    "anthropic": _build_anthropic,
}


def get_llm(
    feature: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    max_tokens: int = 4096,
) -> BaseChatModel:
    """
    Build a chat-model instance pre-wired with auditing and a feature tag.

    Parameters
    ----------
    feature     Slug identifying the caller — e.g. "categorize", "nl_input",
                "chat". Flows into:
                  - the ai_calls audit row (so GET /api/ai/usage groups by feature)
                  - the trace metadata once tracing is enabled
    model       Optional model id override. Leave None to fall back to
                settings.llm_model, then to the provider's default model. Pass
                this only when a feature genuinely needs a specific model.
    provider    Optional provider override. Leave None to use settings.llm_provider.
                Upcoming features that must pin a provider can pass it here, but
                the default keeps call sites provider-agnostic.
    max_tokens  Cap on output tokens. 4096 covers every feature so far.

    Returns
    -------
    A LangChain chat model you can call .invoke(messages) / .stream(messages) on.
    The audit callback fires automatically on every call — no extra wiring needed
    at the feature level.
    """
    # Resolve provider: explicit arg wins, otherwise the app-wide config default.
    resolved_provider = (provider or settings.llm_provider).lower()
    builder = _PROVIDERS.get(resolved_provider)
    if builder is None:
        raise ValueError(
            f"Unknown LLM provider '{resolved_provider}'. "
            f"Registered providers: {sorted(_PROVIDERS)}."
        )

    # Resolve model: explicit arg → config override → provider default.
    resolved_model = model or settings.llm_model or _DEFAULT_MODEL.get(resolved_provider)
    if not resolved_model:
        raise ValueError(
            f"No model configured for provider '{resolved_provider}'. "
            "Set LLM_MODEL or add a default in _DEFAULT_MODEL."
        )

    # The callback fires on every .invoke() / .stream() of this instance and
    # writes one ai_calls row per call. Attaching it here means feature code
    # never has to remember to audit — by the time .invoke() returns, the row
    # exists. metadata.feature/provider also tag the trace context for filtering.
    callbacks: list[BaseCallbackHandler] = [AuditCallbackHandler(feature=feature)]
    metadata = {"feature": feature, "provider": resolved_provider}

    return builder(
        model=resolved_model,
        max_tokens=max_tokens,
        callbacks=callbacks,
        metadata=metadata,
    )
