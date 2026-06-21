# Application configuration loaded from environment variables and the .env file.
# Uses pydantic-settings, which reads .env automatically and validates the values.
# Think of this like Spring Boot's @ConfigurationProperties — one place to declare
# all the env vars the app needs, with type checking and a clear error if one is missing.

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


# Module-level singleton — imported everywhere that needs a config value.
# This pattern mirrors Spring's @Value injection but without the magic:
# import settings; settings.anthropic_api_key
settings = Settings()
