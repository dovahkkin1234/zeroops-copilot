"""Reporter agent — produces final Postmortem + Markdown report.

Handles three resolution paths:
- resolved: full investigation completed successfully
- known_pattern: L0 fast-path from triage match
- uncertain: give_up path with honest failure documentation

Design: the LLM writes only 3 narrative text fields (root_cause,
proposed_fix, proposed_diff). Everything else is assembled in Python
from the structured state. Markdown is rendered deterministically.
This avoids asking the model to produce a large nested JSON object.
"""

import json
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ..config import settings
from ..models import Postmortem, Hypothesis, ReproScript, PreventionTicket, TriageDecision, Severity, TicketTier
from ..tools.memory import save_incident
from ._llm import run_as_json

_prompt = (Path(__file__).parent.parent / "prompts" / "reporter.md").read_text(encoding="utf-8")


class _NarrativeFields(BaseModel):
    """The only fields the LLM needs to generate — everything else comes from state."""
    root_cause: str
    proposed_fix: str
    proposed_diff: Optional[str] = None


async def reporter_node(state: dict) -> dict:
    """Produce Postmortem JSON and rendered Markdown report."""

    triage = state.get("triage", {})
    hypothesis = state.get("hypothesis")
    repro = state.get("repro")
    evidence = state.get("evidence", [])
    prevention_tickets = state.get("prevention_tickets", [])
    evaluator_decision = state.get("evaluator_decision")
    tool_history = state.get("tool_history", [])

    # Duration: computed from start_time in state if available, else fallback
    start_time = state.get("start_time")
    if start_time:
        duration = time.time() - start_time
    else:
        duration = state.get("duration_seconds", 0.0)

    # Determine resolution status
    if triage.get("classification") == "known_pattern":
        resolution_status = "known_pattern"
    elif evaluator_decision == "give_up":
        resolution_status = "uncertain"
    else:
        resolution_status = "resolved"

    # Ask LLM only for the 3 narrative text fields
    narrative = await _get_narrative(state, resolution_status, hypothesis, evidence)

    # Assemble Postmortem entirely in Python from structured state
    postmortem_dict = _assemble_postmortem(
        state=state,
        resolution_status=resolution_status,
        narrative=narrative,
        duration=duration,
    )

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


async def _get_narrative(
    state: dict,
    resolution_status: str,
    hypothesis: Optional[dict],
    evidence: list,
) -> _NarrativeFields:
    """Ask LLM for root_cause, proposed_fix, proposed_diff only."""
    # For known_pattern, derive from matched incident — no LLM needed
    if resolution_status == "known_pattern":
        triage = state.get("triage", {})
        return _NarrativeFields(
            root_cause=triage.get("routing_reason", "Known pattern matched from memory."),
            proposed_fix="Apply the fix from the matched past incident.",
        )

    # For give_up, describe what was attempted
    if resolution_status == "uncertain":
        tried = ", ".join(
            e.get("tool", "unknown") for e in state.get("tool_history", [])
        )
        return _NarrativeFields(
            root_cause=f"Investigation could not reach a confident conclusion. Tools tried: {tried}.",
            proposed_fix="Manual investigation required.",
        )

    # resolved path — ask LLM for the 3 fields with a simple prompt
    hyp_text = hypothesis.get("statement", "") if hypothesis else ""
    ev_text = json.dumps(evidence, indent=2, default=str)[:2000] if evidence else "[]"

    prompt = _prompt.format(
        hypothesis=hyp_text,
        evidence=ev_text,
        error_text=state.get("error_text", ""),
        triage=json.dumps(state.get("triage", {}), indent=2, default=str),
        repro=json.dumps(state.get("repro"), indent=2, default=str) if state.get("repro") else "None",
        prevention_tickets=json.dumps(state.get("prevention_tickets", []), indent=2, default=str),
        resolution_status=resolution_status,
        tools_called=len(state.get("tool_history", [])),
        duration_seconds=0,  # placeholder; not used in narrative fields
    )

    try:
        return await run_as_json(
            settings.pydantic_ai_model,
            "You write root cause analysis. Return valid JSON only.",
            prompt,
            _NarrativeFields,
        )
    except Exception:
        # Fallback: derive from hypothesis directly
        return _NarrativeFields(
            root_cause=hyp_text or "Root cause could not be generated.",
            proposed_fix=(
                f"Update all callers of the renamed symbol per the "
                f"{hypothesis.get('pattern', 'unknown')} pattern."
                if hypothesis else "Manual fix required."
            ),
        )


def _assemble_postmortem(
    state: dict,
    resolution_status: str,
    narrative: _NarrativeFields,
    duration: float,
) -> dict:
    """Build the full Postmortem dict from structured state + narrative text."""
    triage_data = state.get("triage", {})
    hypothesis = state.get("hypothesis")
    repro = state.get("repro")
    evidence = state.get("evidence", [])
    prevention_tickets = state.get("prevention_tickets", [])
    tool_history = state.get("tool_history", [])

    # Derive confidence
    if hypothesis:
        confidence = hypothesis.get("confidence", 0.7)
    elif resolution_status == "known_pattern":
        confidence = triage_data.get("match_confidence", 0.9)
    else:
        confidence = 0.4

    # Build triage object
    try:
        triage_obj = TriageDecision(**triage_data)
    except Exception:
        triage_obj = TriageDecision(
            classification=triage_data.get("classification", "novel"),
            match_confidence=triage_data.get("match_confidence", 0.0),
            error_type=triage_data.get("error_type", "unknown"),
            suggested_tier=TicketTier.L2_ANALYSIS,
            severity=Severity.SEV3,
            routing_reason=triage_data.get("routing_reason", ""),
        )

    # Build timeline from tool_history — clean one-line entry per tool call
    timeline = []
    for i, t in enumerate(tool_history, 1):
        tool = t.get("tool", "unknown")
        args = t.get("args", {})
        # Pick the most descriptive arg (path, pattern, commit_hash)
        arg_str = (
            args.get("path")
            or args.get("pattern")
            or args.get("commit_hash")
            or args.get("function_name")
            or str(args)[:40]
        )
        # Result: first meaningful line, strip line numbers and JSON noise
        raw = t.get("result_summary", "")
        first_line = raw.split("\n")[0].strip().lstrip("0123456789: ").strip()[:80]
        result_hint = f"→ {first_line}" if first_line and first_line not in ("[]", "ERROR") else ""
        timeline.append(f"Step {i}: `{tool}({arg_str})` {result_hint}")
    if not timeline:
        timeline = ["Investigation completed via memory match." if resolution_status == "known_pattern"
                    else "Investigation completed."]

    # Build hypothesis and repro objects if present
    hyp_obj = None
    if hypothesis:
        try:
            hyp_obj = Hypothesis(**hypothesis)
        except Exception:
            pass

    repro_obj = None
    if repro:
        try:
            repro_obj = ReproScript(**repro)
        except Exception:
            pass

    # Build prevention ticket objects
    ticket_objs = []
    for t in prevention_tickets:
        if isinstance(t, dict):
            try:
                ticket_objs.append(PreventionTicket(**t))
            except Exception:
                pass
        elif isinstance(t, PreventionTicket):
            ticket_objs.append(t)

    postmortem = Postmortem(
        incident_id=0,  # filled in after save
        resolution_status=resolution_status,
        triage=triage_obj,
        timeline=timeline,
        hypothesis=hyp_obj,
        repro=repro_obj,
        root_cause=narrative.root_cause,
        proposed_fix=narrative.proposed_fix,
        proposed_diff=narrative.proposed_diff,
        prevention_tickets=ticket_objs,
        confidence=confidence,
        failure_reason=(
            "Investigation exhausted budget without reaching a confident conclusion."
            if resolution_status == "uncertain" else None
        ),
        tools_called=len(tool_history),
        duration_seconds=duration,
        markdown="",  # filled below
    )

    # Render markdown deterministically from structured fields
    postmortem.markdown = _render_markdown(postmortem)

    return postmortem.model_dump()


def _render_markdown(pm: Postmortem) -> str:
    """Render the full 9-section postmortem report from structured fields."""
    lines = []

    # 1. Incident Summary
    lines.append("## Incident Summary")
    triage = pm.triage
    err_type = triage.error_type if triage else "Unknown"
    sev = triage.severity.value if triage and triage.severity else "?"
    article = "An" if err_type and err_type[0].upper() in "AEIOU" else "A"
    lines.append(
        f"{article} **{err_type}** was detected with severity **{sev}**. "
        f"Resolution status: **{pm.resolution_status}** (confidence: {pm.confidence:.0%})."
    )
    lines.append("")

    # 2. Severity and Tier
    lines.append("## Severity and Tier")
    tier = triage.suggested_tier.value if triage else "?"
    lines.append(f"**{sev}**, Tier **{tier}**.")
    if sev == "SEV2":
        lines.append("SLA implication: major functionality blocked; response within 4 hours.")
    elif sev == "SEV1":
        lines.append("SLA implication: service outage; immediate response required.")
    elif sev == "SEV3":
        lines.append("SLA implication: minor impact; workaround available.")
    else:
        lines.append("SLA implication: cosmetic or low-impact issue.")
    lines.append("")

    # 3. Timeline
    lines.append("## Timeline")
    for step in pm.timeline:
        lines.append(f"- {step}")
    lines.append("")

    # 4. Root Cause
    lines.append("## Root Cause")
    lines.append(pm.root_cause)
    lines.append("")

    # 5. Evidence
    lines.append("## Evidence")
    if pm.hypothesis and pm.hypothesis.evidence:
        lines.append("| Source | Observation | Relevance |")
        lines.append("|--------|-------------|-----------|")
        for ev in pm.hypothesis.evidence[:6]:
            src = ev.source
            obs = ev.observation[:80].replace("|", "/")
            rel = f"{ev.relevance:.2f}"
            lines.append(f"| {src} | {obs} | {rel} |")
    else:
        lines.append("No structured evidence collected (L0 or give_up path).")
    lines.append("")

    # 6. Proposed Fix
    lines.append("## Proposed Fix")
    lines.append(pm.proposed_fix)
    if pm.proposed_diff:
        lines.append("")
        lines.append("```diff")
        lines.append(pm.proposed_diff)
        lines.append("```")
    lines.append("")

    # 7. Reproduction
    lines.append("## Reproduction")
    if pm.repro:
        executed = "verified ✅" if pm.repro.reproduced else (
            "executed but not reproduced ❌" if pm.repro.executed else "not executed (disabled)")
        lines.append(f"Script language: `{pm.repro.language}`. Status: {executed}.")
        lines.append("")
        lines.append(f"```{pm.repro.language}")
        lines.append(pm.repro.code)
        lines.append("```")
    else:
        lines.append("No reproduction script generated.")
    lines.append("")

    # 8. Prevention Tickets
    lines.append("## Prevention Tickets")
    if pm.prevention_tickets:
        for ticket in pm.prevention_tickets:
            lines.append(f"### `{ticket.location}`")
            lines.append(f"**Pattern:** {ticket.pattern_match}")
            lines.append(f"**Proposed fix:** {ticket.proposed_fix}")
            if ticket.proposed_diff:
                lines.append("")
                lines.append("```diff")
                lines.append(ticket.proposed_diff)
                lines.append("```")
            lines.append("")
    else:
        lines.append("No similar patterns found in the codebase.")
    lines.append("")

    # 9. What This Tells Us
    lines.append("## What This Tells Us")
    if pm.resolution_status == "known_pattern":
        lines.append(
            "This incident was resolved automatically via the L0 fast-path: "
            "the pattern was recognized from a previous investigation, requiring "
            "zero human intervention. That is the ZeroOps shift-left in action."
        )
    elif pm.resolution_status == "uncertain":
        lines.append(
            f"The investigation exhausted its budget ({pm.tools_called} tool calls) "
            "without reaching a confident conclusion. This is an honest outcome — "
            "the system escalates to human review rather than fabricating an answer."
        )
    else:
        n = len(pm.prevention_tickets)
        if n > 0:
            lines.append(
                f"The `{pm.hypothesis.pattern if pm.hypothesis else 'unknown'}` pattern "
                f"found here also exists in {n} other location(s). "
                f"This incident made the system safer — {n} future incident(s) prevented."
            )
        else:
            lines.append(
                "No other instances of this pattern were found in the codebase. "
                "The fix here closes the only known occurrence."
            )
    lines.append("")
    lines.append(f"*Investigation duration: {pm.duration_seconds:.1f}s | "
                 f"Tools called: {pm.tools_called} | "
                 f"Confidence: {pm.confidence:.0%}*")

    return "\n".join(lines)
