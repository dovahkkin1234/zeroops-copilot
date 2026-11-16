"""PydanticAI schemas — all structured outputs for the agent graph.

Every LLM call in the agent graph produces a PydanticAI-validated object.
No free-form text outputs in the agent graph. Free-form rendering happens
only in the final Reporter node, which still returns a Postmortem object
plus a Markdown string.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Any, Literal, Optional
from enum import Enum


def _unwrap_enum(v: Any) -> Any:
    """Unwrap {"enum": ["value"]} → "value".

    Some local LLMs (e.g. qwen2.5) return the JSON Schema enum constraint
    as an object instead of the plain string value. This pre-processor
    normalises those values before Pydantic field validation runs.
    """
    if (
        isinstance(v, dict)
        and set(v.keys()) <= {"enum", "type", "description"}
        and isinstance(v.get("enum"), list)
        and v["enum"]
    ):
        return v["enum"][0]
    return v


class _Base(BaseModel):
    """Base class that handles local-model enum-wrapping quirks."""

    @model_validator(mode="before")
    @classmethod
    def _fix_enum_wrappers(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: _unwrap_enum(v) for k, v in data.items()}
        return data


class TicketTier(str, Enum):
    L0_SELFSERVE = "L0"
    L1_TRIAGE = "L1"
    L2_ANALYSIS = "L2"
    L3_DEEPDIVE = "L3"


class Severity(str, Enum):
    SEV1 = "SEV1"  # outage, data loss, security breach
    SEV2 = "SEV2"  # major feature broken, many users affected
    SEV3 = "SEV3"  # minor feature broken, workaround exists
    SEV4 = "SEV4"  # cosmetic, log noise


class TriageDecision(_Base):
    classification: Literal["known_pattern", "novel", "insufficient_info"]
    matched_incident_id: Optional[int] = None
    match_confidence: float = Field(ge=0.0, le=1.0)
    error_type: str
    suggested_tier: TicketTier
    severity: Severity
    routing_reason: str


class EvidenceItem(_Base):
    source: Literal["file", "git_commit", "test", "past_incident"]
    reference: str
    observation: str
    relevance: float = Field(ge=0.0, le=1.0)


class PlannerDecision(_Base):
    tool: Literal["read_file", "grep_code", "find_tests", "git_log", "git_show"]
    arguments: dict
    reasoning: str


class EvaluatorDecision(_Base):
    decision: Literal["continue", "hypothesize", "give_up"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class Hypothesis(_Base):
    statement: str
    pattern: Optional[str] = None
    evidence: list[EvidenceItem]
    confidence: float = Field(ge=0.0, le=1.0)


class ReproScript(_Base):
    language: Literal["python", "bash"]
    code: str
    expected_error: str
    executed: bool = False
    execution_stdout: Optional[str] = None
    execution_stderr: Optional[str] = None
    reproduced: Optional[bool] = None


class PreventionTicket(_Base):
    location: str                        # "file.py:42"
    pattern_match: str                   # why we flagged this
    proposed_fix: str                    # textual description
    proposed_diff: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class Postmortem(_Base):
    incident_id: int
    resolution_status: Literal["resolved", "known_pattern", "uncertain"]
    triage: TriageDecision
    timeline: list[str]
    hypothesis: Optional[Hypothesis] = None   # None for L0 fast-path
    repro: Optional[ReproScript] = None
    root_cause: str
    proposed_fix: str
    proposed_diff: Optional[str] = None       # None for L0 and uncertain paths
    prevention_tickets: list[PreventionTicket] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    failure_reason: Optional[str] = None      # populated when resolution_status == "uncertain"
    tools_called: int                         # derived from len(tool_history) in state
    duration_seconds: float
    markdown: str                             # human-readable render
