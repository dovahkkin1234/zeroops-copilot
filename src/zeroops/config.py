"""Settings via pydantic-settings. All env vars loaded from .env."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_PROVIDERS = {"anthropic", "ollama", "google-gla"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    google_api_key: str = ""
    llm_provider: str = "anthropic"           # "anthropic" | "ollama" | "google-gla"
    llm_model: str = "claude-opus-4-7"
    utility_model: str = "claude-haiku-4-5-20251001"
    ollama_base_url: str = "http://localhost:11434/v1"
    embed_model: str = "all-MiniLM-L6-v2"
    db_path: str = "./incidents.db"
    repo_path: str = "./demo_repo"
    max_investigation_loops: int = 8
    repro_execution_enabled: bool = False

    @property
    def pydantic_ai_model(self) -> str:
        """Return PydanticAI model string with provider prefix.

        Ollama uses PydanticAI's OpenAI-compatible backend: the model string
        is 'openai:<model>' and OPENAI_BASE_URL / OPENAI_API_KEY are set
        below so the client resolves to the local Ollama endpoint.
        """
        if self.llm_provider == "ollama":
            return f"openai:{self.llm_model}"
        return f"{self.llm_provider}:{self.llm_model}"

    @property
    def pydantic_ai_utility_model(self) -> str:
        """Utility model (cheaper, non-reasoning tasks)."""
        if self.llm_provider == "ollama":
            return f"openai:{self.utility_model}"
        return f"{self.llm_provider}:{self.utility_model}"


settings = Settings()

# pydantic-settings reads .env into the model but does NOT write to os.environ.
# Sync keys that provider clients resolve from os.environ.
if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

if settings.llm_provider == "ollama":
    # PydanticAI's 'openai:' provider reads these two env vars to route
    # to the Ollama endpoint instead of api.openai.com.
    if not os.environ.get("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = settings.ollama_base_url
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "ollama"

if settings.google_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
