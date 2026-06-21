"""Application settings.

We use pydantic-settings so configuration is loaded from a `.env` file (or real
environment variables) and validated once at startup. Importing `settings` from
anywhere gives every module the same, already-validated config object.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read from a local .env file; ignore unknown keys so the file can hold notes.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude
    anthropic_api_key: str = ""

    # Google Calendar
    google_credentials_file: str = "credentials.json"
    google_token_file: str = "token.json"
    calendar_id: str = "primary"

    # Local database
    database_url: str = "sqlite:///./secretary.db"

    # Local LLM (Ollama) — used for the M6 email→schedule extraction so it runs
    # off-Claude (free, private, on the user's GPU). Swap the model here without
    # touching code; the extractor falls back gracefully if Ollama is down.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "scb10x/llama3.1-typhoon2-8b-instruct"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so we build Settings exactly once per process."""
    return Settings()


settings = get_settings()
