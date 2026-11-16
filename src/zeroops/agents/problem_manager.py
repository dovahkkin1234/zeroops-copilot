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

    # Graph hint: files previously seen with this pattern (from resolved incidents)
    graph_known_files: list[str] = []
    try:
        from ..memory.graph_store import get_graph
        graph_known_files = get_graph().get_files_with_pattern(pattern)
    except Exception:
        pass

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
    graph_files_str = (
        f"Graph memory: these files were previously flagged for the '{pattern}' pattern "
        f"in past incidents: {', '.join(graph_known_files)}. Check these first."
        if graph_known_files else ""
    )

    prompt = _prompt.format(
        hypothesis=json.dumps(hypothesis, indent=2, default=str),
        pattern=pattern,
        root_cause=root_cause,
        repo_path=settings.repo_path,
        grep_results=grep_str,
        graph_files_str=graph_files_str,
    )

    ticket_objs = await run_as_json_list(
        settings.pydantic_ai_model,
        "You are a problem manager. Return a valid JSON array of PreventionTicket objects.",
        prompt,
        PreventionTicket,
    )

    # Filter out the incident file itself — it's the bug we just resolved,
    # not a *different* instance of the pattern.
    incident_file = _extract_incident_file(state.get("error_text", ""))
    if incident_file:
        ticket_objs = [
            t for t in ticket_objs
            if not t.location.startswith(incident_file)
        ]

    return {"prevention_tickets": [t.model_dump() for t in ticket_objs]}


def _extract_incident_file(error_text: str) -> str | None:
    """Return the basename of the file in the traceback (the incident file)."""
    import re
    from pathlib import Path as _Path
    matches = re.findall(r'File ["\']([^"\']+)["\']', error_text)
    if matches:
        return _Path(matches[-1]).name
    return None


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
