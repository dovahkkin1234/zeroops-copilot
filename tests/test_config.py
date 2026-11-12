"""Tests for src/zeroops/config.py — provider prefix guard and settings."""

import os
import pytest


def test_pydantic_ai_model_has_anthropic_prefix():
    """Regression guard: prevents the provider-mismatch bug (was openai: before fix)."""
    from zeroops.config import settings
    assert settings.pydantic_ai_model.startswith("anthropic:"), (
        f"pydantic_ai_model must start with 'anthropic:'; got {settings.pydantic_ai_model!r}"
    )


def test_pydantic_ai_utility_model_has_anthropic_prefix():
    from zeroops.config import settings
    assert settings.pydantic_ai_utility_model.startswith("anthropic:"), (
        f"pydantic_ai_utility_model must start with 'anthropic:'; "
        f"got {settings.pydantic_ai_utility_model!r}"
    )


def test_pydantic_ai_model_contains_model_name():
    from zeroops.config import settings
    # The model ID after the prefix must be non-empty
    prefix, _, model_id = settings.pydantic_ai_model.partition(":")
    assert model_id, "Model ID after 'anthropic:' must not be empty"


def test_repro_execution_disabled_by_default():
    from zeroops.config import settings
    assert settings.repro_execution_enabled is False, (
        "REPRO_EXECUTION_ENABLED must default to False for safe operation"
    )


def test_max_investigation_loops_positive():
    from zeroops.config import settings
    assert settings.max_investigation_loops > 0
