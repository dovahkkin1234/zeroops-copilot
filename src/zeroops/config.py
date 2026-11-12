"""Settings via pydantic-settings. All env vars loaded from .env."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-7"
    utility_model: str = "claude-haiku-4-5-20251001"
    embed_model: str = "all-MiniLM-L6-v2"
    db_path: str = "./incidents.db"
    repo_path: str = "./demo_repo"
    max_investigation_loops: int = 8
    repro_execution_enabled: bool = False

    @property
    def pydantic_ai_model(self) -> str:
        """PydanticAI needs 'anthropic:model-id' format."""
        return f"anthropic:{self.llm_model}"

    @property
    def pydantic_ai_utility_model(self) -> str:
        """Utility model for non-reasoning formatting tasks."""
        return f"anthropic:{self.utility_model}"


settings = Settings()

# pydantic-settings reads .env into the model but does NOT write to os.environ.
# PydanticAI's Anthropic client resolves the key from os.environ, so we sync it here.
if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
