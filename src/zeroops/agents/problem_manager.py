"""Problem Manager agent — scans codebase for same bug pattern elsewhere.

The proactive layer: reactive resolution -> proactive prevention.
Uses the hypothesis pattern tag to find similar vulnerable code and
produce Prevention Tickets.
"""

import json
from pathlib import Path

from ..config import settings
from ..models import PreventionTicket
from ..tools.code import grep_code, read_file
from ._llm import run_as_json_list

_prompt = (Path(__file__).parent.parent / "prompts" / "problem_manager.md").read_text(encoding="utf-8")


async def problem_manager_node(state: dict) -> dict:
    """Find other instances of the resolved bug pattern and produce Prevention Tickets."""

    hypothesis = state.get("hypothesis", {})
    if not hypothesis:
        return {"prevention_tickets": []}

    pattern = hypothesis.get("pattern", "")
    root_cause = state.get("hypothesis", {}).get("statement", "")

    # Pre-scan: grep for related patterns to give the LLM context
    grep_results = []
    if pattern in ("incomplete_symbol_rename", "stale_import"):
        # Try to find other files importing the old symbol
        evidence = state.get("evidence", [])
        for ev in evidence:
            obs = ev.get("observation", "")
            # Look for import-related observations
            if "import" in obs.lower():
                grep_results.append(ev)
        # Also grep for the problematic symbols
        old_symbols = _extract_old_symbols(state)
        for sym in old_symbols:
            results = grep_code(sym)
            if results and not any(r.get("error") for r in results):
                grep_results.extend(results)

    elif pattern == "unchecked_none_return":
        # Find callers of the function that returns None
        evidence = state.get("evidence", [])
        for ev in evidence:
            if "None" in ev.get("observation", ""):
                grep_results.append(ev)

    grep_str = json.dumps(grep_results, indent=2, default=str)[:3000] if grep_results else "No grep results."

    prompt = _prompt.format(
        hypothesis=json.dumps(hypothesis, indent=2, default=str),
        pattern=pattern,
        root_cause=root_cause,
        repo_path=settings.repo_path,
        grep_results=grep_str,
    )

    ticket_objs = await run_as_json_list(
        settings.pydantic_ai_model,
        "You are a problem manager. Return a valid JSON array of PreventionTicket objects.",
        prompt,
        PreventionTicket,
    )
    return {"prevention_tickets": [t.model_dump() for t in ticket_objs]}


def _extract_old_symbols(state: dict) -> list[str]:
    """Try to extract old symbol names from evidence (for grep scanning)."""
    symbols = []
    for ev in state.get("evidence", []):
        obs = ev.get("observation", "")
        # Look for patterns like "import X" or "attribute 'X'"
        json_str = obs
        if "validate_token" in obs:
            symbols.append("validate_token")
        if "normalize_string" in obs:
            symbols.append("normalize_string")
        # Generic: look for AttributeError/ImportError symbols
        if "has no attribute" in obs:
            parts = obs.split("'")
            if len(parts) >= 2:
                symbols.append(parts[-2])
        if "cannot import name" in obs:
            parts = obs.split("'")
            if len(parts) >= 2:
                symbols.append(parts[1])
    return list(set(symbols))
