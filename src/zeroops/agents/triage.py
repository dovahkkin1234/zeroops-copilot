"""Triage agent node — classifies incoming errors and routes to resolution path."""

import json
from pathlib import Path

from ..config import settings
from ..models import TriageDecision
from ..tools.memory import search_past_incidents
from ._llm import run_as_json

_prompt = (Path(__file__).parent.parent / "prompts" / "triage.md").read_text(encoding="utf-8")


async def triage_node(state: dict) -> dict:
    """Classify error as known_pattern, novel, or insufficient_info."""

    error_text = state["error_text"]

    past_matches = search_past_incidents(error_text, k=3)
    past_matches_str = (
        json.dumps(past_matches, indent=2, default=str)
        if past_matches
        else "No past incidents in memory."
    )

    prompt = _prompt.format(
        error_text=error_text,
        past_matches=past_matches_str,
    )

    triage_obj = await run_as_json(
        settings.pydantic_ai_model,
        "You are a triage agent. Classify the error and return valid JSON only.",
        prompt,
        TriageDecision,
    )

    return {
        "triage": triage_obj.model_dump(),
        "iteration": 0,
        "max_iterations": settings.max_investigation_loops,
    }
