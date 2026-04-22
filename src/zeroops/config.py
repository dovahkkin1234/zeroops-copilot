"""Settings via pydantic-settings. All env vars loaded from .env."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    utility_model: str = "gpt-4o-mini"
    embed_model: str = "all-MiniLM-L6-v2"
    db_path: str = "./incidents.db"
    repo_path: str = "./demo_repo"
    max_investigation_loops: int = 8
    repro_execution_enabled: bool = False

    @property
    def pydantic_ai_model(self) -> str:
        """PydanticAI needs 'openai:model-id' format."""
        return f"openai:{self.llm_model}"

    @property
    def pydantic_ai_utility_model(self) -> str:
        """Utility model for non-reasoning formatting tasks."""
        return f"openai:{self.utility_model}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# pydantic-settings reads .env into the model but does NOT write to os.environ.
# PydanticAI's OpenAI client resolves the key from os.environ, so we sync it here.
if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
