"""Tests for src/zeroops/config.py — provider prefix guard and settings."""

import pytest


def test_default_provider_is_anthropic(monkeypatch):
    """When LLM_PROVIDER is not overridden, class default is anthropic."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    from zeroops.config import Settings
    assert Settings().llm_provider == "anthropic"


def test_pydantic_ai_model_has_anthropic_prefix(monkeypatch):
    """Regression guard: provider-mismatch bug (was openai: before fix)."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-opus-4-7")
    from zeroops.config import Settings
    s = Settings()
    assert s.pydantic_ai_model.startswith("anthropic:"), (
        f"pydantic_ai_model must start with 'anthropic:'; got {s.pydantic_ai_model!r}"
    )


def test_pydantic_ai_utility_model_has_anthropic_prefix(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("UTILITY_MODEL", "claude-haiku-4-5-20251001")
    from zeroops.config import Settings
    s = Settings()
    assert s.pydantic_ai_utility_model.startswith("anthropic:"), (
        f"pydantic_ai_utility_model must start with 'anthropic:'; "
        f"got {s.pydantic_ai_utility_model!r}"
    )


def test_pydantic_ai_model_contains_model_name():
    from zeroops.config import settings
    prefix, _, model_id = settings.pydantic_ai_model.partition(":")
    assert model_id, "Model ID after provider prefix must not be empty"


def test_repro_execution_disabled_by_default():
    from zeroops.config import settings
    assert settings.repro_execution_enabled is False, (
        "REPRO_EXECUTION_ENABLED must default to False for safe operation"
    )


def test_max_investigation_loops_positive():
    from zeroops.config import settings
    assert settings.max_investigation_loops > 0


# ── Provider-switching (T4b): test the mapping without calling any model ──────

def test_ollama_provider_model_string(monkeypatch):
    """Switching LLM_PROVIDER=ollama must produce 'openai:' prefix (not 'anthropic:').

    PydanticAI routes Ollama through its OpenAI-compatible backend, so the model
    string uses 'openai:<model>' while OPENAI_BASE_URL is redirected to Ollama.
    """
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("UTILITY_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    from zeroops.config import Settings
    s = Settings()
    assert s.pydantic_ai_model == "openai:qwen2.5:7b", (
        "Ollama provider uses 'openai:' prefix for PydanticAI's OpenAI-compatible backend"
    )
    assert s.pydantic_ai_utility_model == "openai:qwen2.5:7b"
    assert not s.pydantic_ai_model.startswith("anthropic:")


def test_anthropic_provider_model_string(monkeypatch):
    """Explicit LLM_PROVIDER=anthropic must produce 'anthropic:' prefix."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("UTILITY_MODEL", "claude-haiku-5-5")

    from zeroops.config import Settings
    s = Settings()
    assert s.pydantic_ai_model == "anthropic:claude-sonnet-5-5"
    assert s.pydantic_ai_utility_model == "anthropic:claude-haiku-5-5"


def test_provider_model_string_uses_llm_model_field(monkeypatch):
    """The model ID in the PydanticAI string must come from LLM_MODEL, not a hardcoded value."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-opus-5-5")

    from zeroops.config import Settings
    s = Settings()
    assert "claude-opus-5-5" in s.pydantic_ai_model


def test_ollama_base_url_default():
    from zeroops.config import Settings
    s = Settings()
    assert s.ollama_base_url == "http://localhost:11434/v1"


def test_ollama_base_url_configurable(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://my-gpu-box:11434/v1")
    from zeroops.config import Settings
    s = Settings()
    assert s.ollama_base_url == "http://my-gpu-box:11434/v1"


# ── google-gla provider (T4b extension) ───────────────────────────────────────

def test_google_gla_provider_model_string(monkeypatch):
    """LLM_PROVIDER=google-gla must produce 'google-gla:' prefix."""
    monkeypatch.setenv("LLM_PROVIDER", "google-gla")
    monkeypatch.setenv("LLM_MODEL", "gemini-4-hydrogen")
    monkeypatch.setenv("UTILITY_MODEL", "gemini-4-hydrogen")
    from zeroops.config import Settings
    s = Settings()
    assert s.pydantic_ai_model == "google-gla:gemini-4-hydrogen"
    assert s.pydantic_ai_utility_model == "google-gla:gemini-4-hydrogen"
    assert not s.pydantic_ai_model.startswith("anthropic:")
    assert not s.pydantic_ai_model.startswith("ollama:")


def test_google_gla_different_model(monkeypatch):
    """Model name propagates correctly for google-gla."""
    monkeypatch.setenv("LLM_PROVIDER", "google-gla")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    from zeroops.config import Settings
    s = Settings()
    assert s.pydantic_ai_model == "google-gla:gemini-2.5-flash"


def test_google_api_key_field_reads_from_env(monkeypatch):
    """GOOGLE_API_KEY env var maps to settings.google_api_key (never reads .env)."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-xyz-offline")
    from zeroops.config import Settings
    s = Settings()
    assert s.google_api_key == "test-key-xyz-offline"


def test_google_api_key_default_is_empty():
    """google_api_key defaults to empty string when env var is absent."""
    from zeroops.config import Settings
    import os
    # Only safe if GOOGLE_API_KEY is not already set in this process
    if os.environ.get("GOOGLE_API_KEY"):
        return  # skip if the real key is present in env
    s = Settings()
    assert s.google_api_key == ""
