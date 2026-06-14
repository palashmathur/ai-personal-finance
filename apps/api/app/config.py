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

    # The Anthropic API key — required for all LLM calls.
    anthropic_api_key: str = ""


# Module-level singleton — imported everywhere that needs a config value.
# This pattern mirrors Spring's @Value injection but without the magic:
# import settings; settings.anthropic_api_key
settings = Settings()
