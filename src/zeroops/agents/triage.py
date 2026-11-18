"""Triage agent node — classifies incoming errors and routes to resolution path."""

import json
import re
from pathlib import Path

from ..config import settings
from ..models import TriageDecision
from ..memory.store import get_by_id
from ..tools.memory import search_past_incidents_with_graph
from ._llm import run_as_json

_prompt = (Path(__file__).parent.parent / "prompts" / "triage.md").read_text(encoding="utf-8")


def _extract_error_type(error_text: str) -> str:
    """Parse the exception class from the last line of a traceback."""
    for line in reversed(error_text.strip().splitlines()):
        line = line.strip()
        if line and ":" in line:
            candidate = line.split(":")[0].strip()
            if candidate and " " not in candidate:
                return candidate
    return ""


def _extract_failing_file(error_text: str) -> str:
    """Return the basename of the file in the traceback (last File entry)."""
    matches = re.findall(r'File ["\']([^"\']+)["\']', error_text)
    if matches:
        return Path(matches[-1]).name
    return ""


async def triage_node(state: dict) -> dict:
    """Classify error as known_pattern, novel, or insufficient_info."""

    error_text = state["error_text"]

    # Graph-augmented search: include file and error_type hints
    file_hint = _extract_failing_file(error_text)
    error_type_hint = _extract_error_type(error_text)

    past_matches = search_past_incidents_with_graph(
        error_text,
        file_hint=file_hint,
        error_type_hint=error_type_hint,
        k=3,
    )
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

    triage_dict = triage_obj.model_dump()

    # For L0 hits, store the retrieved incident's pattern/files so the
    # grader can apply uniform scoring (rule G1/G2 in eval/grading_rules.md).
    if triage_obj.classification == "known_pattern" and triage_obj.matched_incident_id:
        matched = get_by_id(triage_obj.matched_incident_id)
        if matched:
            triage_dict["matched_pattern"] = matched.get("root_cause_pattern")
            raw_files = matched.get("affected_files")
            if isinstance(raw_files, str):
                try:
                    import json as _json
                    raw_files = _json.loads(raw_files)
                except Exception:
                    raw_files = [raw_files]
            triage_dict["matched_files"] = raw_files or []

    return {
        "triage": triage_dict,
        "iteration": 0,
        "max_iterations": settings.max_investigation_loops,
    }
