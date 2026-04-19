"""Triage agent node — classifies incoming errors and routes to resolution path.

Loads prompt from prompts/triage.md. Uses PydanticAI with TriageDecision output.
Searches past incidents for semantic matches before classification.
"""

import json
from pathlib import Path

from pydantic_ai import Agent
from pydantic import ValidationError

from ..config import settings
from ..models import TriageDecision
from ..tools.memory import search_past_incidents

_prompt = (Path(__file__).parent.parent / "prompts" / "triage.md").read_text(encoding="utf-8")


async def triage_node(state: dict) -> dict:
    """Classify error as known_pattern, novel, or insufficient_info."""

    error_text = state["error_text"]

    # Search past incidents for similar patterns
    past_matches = search_past_incidents(error_text, k=3)
    past_matches_str = json.dumps(past_matches, indent=2, default=str) if past_matches else "No past incidents in memory."

    prompt = _prompt.format(
        error_text=error_text,
        past_matches=past_matches_str,
    )

    agent = Agent(
        settings.pydantic_ai_model,
        output_type=TriageDecision,
        system_prompt="You are a triage agent. Return valid JSON only.",
    )

    # Retry once on validation failure
    try:
        result = await agent.run(prompt)
    except (ValidationError, Exception) as first_error:
        repair_prompt = (
            f"Your previous response failed validation. "
            f"Return ONLY valid JSON matching the TriageDecision schema. "
            f"Error: {first_error}\n\n{prompt}"
        )
        result = await agent.run(repair_prompt)

    triage = result.output.model_dump()

    # If known_pattern with high confidence, we'll route to reporter directly
    # via the graph's conditional edges
    return {
        "triage": triage,
        "iteration": 0,
        "max_iterations": settings.max_investigation_loops,
    }
