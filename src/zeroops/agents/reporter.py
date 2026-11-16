"""Reporter agent — produces final Postmortem + Markdown report.

Handles three resolution paths:
- resolved: full investigation completed successfully
- known_pattern: L0 fast-path from triage match
- uncertain: give_up path with honest failure documentation
"""

import json
import time
from pathlib import Path

from ..config import settings
from ..models import Postmortem
from ..tools.memory import save_incident
from ._llm import run_as_json

_prompt = (Path(__file__).parent.parent / "prompts" / "reporter.md").read_text(encoding="utf-8")


async def reporter_node(state: dict) -> dict:
    """Produce Postmortem JSON and rendered Markdown report."""

    triage = state.get("triage", {})
    hypothesis = state.get("hypothesis")
    repro = state.get("repro")
    evidence = state.get("evidence", [])
    prevention_tickets = state.get("prevention_tickets", [])
    evaluator_decision = state.get("evaluator_decision")
    tool_history = state.get("tool_history", [])
    duration = state.get("duration_seconds", 0.0)

    # Determine resolution status
    if triage.get("classification") == "known_pattern":
        resolution_status = "known_pattern"
    elif evaluator_decision == "give_up":
        resolution_status = "uncertain"
    else:
        resolution_status = "resolved"

    prompt = _prompt.format(
        triage=json.dumps(triage, indent=2, default=str),
        hypothesis=json.dumps(hypothesis, indent=2, default=str) if hypothesis else "None (L0 path or give_up)",
        repro=json.dumps(repro, indent=2, default=str) if repro else "None",
        evidence=json.dumps(evidence, indent=2, default=str)[:3000] if evidence else "[]",
        prevention_tickets=json.dumps(prevention_tickets, indent=2, default=str) if prevention_tickets else "[]",
        resolution_status=resolution_status,
        tools_called=len(tool_history),
        duration_seconds=round(duration, 2),
    )

    try:
        postmortem = await run_as_json(
            settings.pydantic_ai_model,
            "You are a postmortem reporter. Return valid JSON only.",
            prompt,
            Postmortem,
        )
    except Exception:
        postmortem = _build_fallback_postmortem(state, resolution_status, duration)

    postmortem_dict = postmortem.model_dump() if hasattr(postmortem, 'model_dump') else postmortem

    # Save resolved incidents to memory (enforces save contract)
    if resolution_status in ("resolved", "known_pattern"):
        try:
            saved_data = {
                **postmortem_dict,
                "error_text": state["error_text"],
            }
            incident_id = save_incident(saved_data)
            postmortem_dict["incident_id"] = incident_id
        except (ValueError, Exception):
            pass  # Save contract rejected it — that's fine

    return {
        "postmortem": postmortem_dict,
        "duration_seconds": duration,
    }


def _build_fallback_postmortem(state: dict, resolution_status: str,
                                duration: float) -> Postmortem:
    """Build a minimal postmortem when LLM fails."""
    from ..models import TriageDecision, Severity, TicketTier

    triage_data = state.get("triage", {})
    hypothesis = state.get("hypothesis")
    tool_history = state.get("tool_history", [])

    # Build triage decision from state
    try:
        triage_obj = TriageDecision(**triage_data)
    except Exception:
        triage_obj = TriageDecision(
            classification="novel",
            match_confidence=0.0,
            error_type="unknown",
            suggested_tier=TicketTier.L2_ANALYSIS,
            severity=Severity.SEV3,
            routing_reason="Fallback triage",
        )

    root_cause = "Unable to determine root cause via LLM."
    if hypothesis:
        root_cause = hypothesis.get("statement", root_cause)

    markdown = f"""# Incident Report

## Summary
Error investigated with {resolution_status} status.

## Root Cause
{root_cause}

## Tools Used
{len(tool_history)} tool calls made during investigation.

## Duration
{duration:.1f} seconds
"""

    return Postmortem(
        incident_id=0,
        resolution_status=resolution_status,
        triage=triage_obj,
        timeline=[f"Investigation completed in {duration:.1f}s"],
        hypothesis=None,
        repro=None,
        root_cause=root_cause,
        proposed_fix="See investigation evidence.",
        proposed_diff=None,
        prevention_tickets=[],
        confidence=0.3,
        failure_reason="LLM reporter failed; fallback report generated." if resolution_status == "uncertain" else None,
        tools_called=len(tool_history),
        duration_seconds=duration,
        markdown=markdown,
    )
