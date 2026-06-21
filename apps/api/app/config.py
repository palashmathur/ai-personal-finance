# Application configuration loaded from environment variables and the .env file.
# Uses pydantic-settings, which reads .env automatically and validates the values.
# Think of this like Spring Boot's @ConfigurationProperties — one place to declare
# all the env vars the app needs, with type checking and a clear error if one is missing.

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Holds every environment variable the app reads.

    pydantic-settings maps environment variable names (case-insensitive) to
    these fields. So ANTHROPIC_API_KEY in the .env file populates anthropic_api_key here.

    The .env file is optional — in production, set the real env vars instead.
    extra="ignore" means unknown variables in .env don't cause an error.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which LLM provider the get_llm() factory builds by default. Keep this the
    # single switch for "what LLM does the app use" — feature code never names a
    # provider, so changing this (or LLM_MODEL) reroutes every feature at once.
    # Must be a key registered in app/ai/llm.py's provider registry.
    llm_provider: str = "groq"

    # Optional global model override. Blank means "use the factory's default
    # model for the selected provider". Set this to pin a specific model id
    # without touching code.
    llm_model: str = ""

    # Per-provider API keys. Only the key for the active provider needs a value;
    # the others can stay blank. Loaded from the matching env var (e.g. GROQ_API_KEY).
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    # --- LangSmith tracing (PF-22c) ------------------------------------------
    # LangSmith is the hosted dashboard that records every LLM call as a
    # clickable trace (full prompt, response, tokens, latency) alongside our
    # local ai_calls table. It's opt-in: leave langchain_api_key blank and
    # tracing stays completely off (see the os.environ bridge below).
    #
    # The LangSmith API key. Blank = tracing disabled.
    langchain_api_key: str = ""
    # LangChain's on/off switch. It's a string, not a bool, because LangChain
    # reads it as a raw env var ("true"/"false"). Only takes effect once an API
    # key is present.
    langchain_tracing_v2: str = "true"
    # Groups all traces under this project name in the LangSmith UI.
    langchain_project: str = "personal-finance"


# Module-level singleton — imported everywhere that needs a config value.
# This pattern mirrors Spring's @Value injection but without the magic:
# import settings; settings.anthropic_api_key
settings = Settings()


def _export_langsmith_env(cfg: Settings) -> None:
    """
    Promote the LangSmith config values into os.environ.

    LangChain's tracer reads LANGCHAIN_* from os.environ *directly* —
    pydantic-settings only populates the `cfg` object, it never touches
    os.environ. So without this bridge, keys placed only in .env would be
    invisible to LangChain and no traces would ever be sent.

    Java analogy: a tiny @PostConstruct that copies a few
    @ConfigurationProperties into JVM system properties because a third-party
    library only reads System.getProperty(), not our bean.

    Guarded on the API key: no key → tracing stays fully off and LangSmith never
    attempts a network call. setdefault() means a real OS/shell env var always
    wins over the .env value (we don't clobber an explicit environment).
    """
    if not cfg.langchain_api_key:
        return
    os.environ.setdefault("LANGCHAIN_API_KEY", cfg.langchain_api_key)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", cfg.langchain_tracing_v2)
    os.environ.setdefault("LANGCHAIN_PROJECT", cfg.langchain_project)


# Run the bridge once at import time. app.config is imported during startup
# (app/ai/llm.py → get_llm), so this fires before any LLM is ever built.
_export_langsmith_env(settings)
