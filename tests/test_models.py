"""Tests for src/zeroops/models.py — valid construction and validation rejection."""

import pytest
from pydantic import ValidationError

from zeroops.models import (
    EvaluatorDecision,
    EvidenceItem,
    Hypothesis,
    PlannerDecision,
    Postmortem,
    PreventionTicket,
    ReproScript,
    Severity,
    TicketTier,
    TriageDecision,
)


# ── TriageDecision ───────────────────────────────────────────────────────────

def test_triage_decision_valid():
    td = TriageDecision(
        classification="novel",
        match_confidence=0.42,
        error_type="AttributeError",
        suggested_tier=TicketTier.L2_ANALYSIS,
        severity=Severity.SEV3,
        routing_reason="no prior match",
    )
    assert td.classification == "novel"
    assert td.matched_incident_id is None


def test_triage_decision_known_pattern():
    td = TriageDecision(
        classification="known_pattern",
        matched_incident_id=7,
        match_confidence=0.91,
        error_type="AttributeError",
        suggested_tier=TicketTier.L0_SELFSERVE,
        severity=Severity.SEV2,
        routing_reason="high similarity match",
    )
    assert td.matched_incident_id == 7
    assert td.suggested_tier == TicketTier.L0_SELFSERVE


def test_triage_decision_invalid_classification():
    with pytest.raises(ValidationError):
        TriageDecision(
            classification="unknown",   # not in Literal
            match_confidence=0.5,
            error_type="X",
            suggested_tier=TicketTier.L1_TRIAGE,
            severity=Severity.SEV4,
            routing_reason="",
        )


def test_triage_decision_confidence_out_of_range():
    with pytest.raises(ValidationError):
        TriageDecision(
            classification="novel",
            match_confidence=1.5,   # > 1.0
            error_type="X",
            suggested_tier=TicketTier.L1_TRIAGE,
            severity=Severity.SEV4,
            routing_reason="",
        )


def test_triage_decision_confidence_negative():
    with pytest.raises(ValidationError):
        TriageDecision(
            classification="novel",
            match_confidence=-0.1,  # < 0.0
            error_type="X",
            suggested_tier=TicketTier.L1_TRIAGE,
            severity=Severity.SEV4,
            routing_reason="",
        )


# ── EvidenceItem ─────────────────────────────────────────────────────────────

def test_evidence_item_valid():
    ei = EvidenceItem(
        source="file",
        reference="auth.py",
        observation="validate_token not found",
        relevance=0.9,
    )
    assert ei.source == "file"
    assert ei.relevance == 0.9


def test_evidence_item_invalid_source():
    with pytest.raises(ValidationError):
        EvidenceItem(source="database", reference="x", observation="y", relevance=0.5)


def test_evidence_item_relevance_too_high():
    with pytest.raises(ValidationError):
        EvidenceItem(source="file", reference="x", observation="y", relevance=1.1)


# ── EvaluatorDecision ────────────────────────────────────────────────────────

def test_evaluator_decision_valid_give_up():
    ed = EvaluatorDecision(decision="give_up", confidence=0.2, reasoning="too many contradictions")
    assert ed.decision == "give_up"


def test_evaluator_decision_invalid():
    with pytest.raises(ValidationError):
        EvaluatorDecision(decision="skip", confidence=0.5, reasoning="")


def test_evaluator_decision_confidence_range():
    with pytest.raises(ValidationError):
        EvaluatorDecision(decision="continue", confidence=2.0, reasoning="")


# ── PlannerDecision ──────────────────────────────────────────────────────────

def test_planner_decision_valid():
    pd = PlannerDecision(
        tool="read_file",
        arguments={"path": "auth.py"},
        reasoning="check if validate_token exists",
    )
    assert pd.tool == "read_file"


def test_planner_decision_invalid_tool():
    with pytest.raises(ValidationError):
        PlannerDecision(tool="run_shell", arguments={}, reasoning="x")


# ── Hypothesis ───────────────────────────────────────────────────────────────

def test_hypothesis_valid():
    h = Hypothesis(
        statement="validate_token was renamed to verify_token",
        pattern="incomplete_symbol_rename",
        evidence=[],
        confidence=0.85,
    )
    assert h.pattern == "incomplete_symbol_rename"


def test_hypothesis_confidence_range():
    with pytest.raises(ValidationError):
        Hypothesis(statement="x", evidence=[], confidence=-0.5)


# ── ReproScript ──────────────────────────────────────────────────────────────

def test_repro_script_defaults():
    rs = ReproScript(language="python", code="import auth", expected_error="AttributeError")
    assert rs.executed is False
    assert rs.reproduced is None


def test_repro_script_invalid_language():
    with pytest.raises(ValidationError):
        ReproScript(language="javascript", code="", expected_error="")


# ── PreventionTicket ─────────────────────────────────────────────────────────

def test_prevention_ticket_valid():
    pt = PreventionTicket(
        location="db.py:2",
        pattern_match="stale import of normalize_string",
        proposed_fix="update import to normalize_text",
        confidence=0.78,
    )
    assert pt.proposed_diff is None


def test_prevention_ticket_confidence_range():
    with pytest.raises(ValidationError):
        PreventionTicket(location="x", pattern_match="y", proposed_fix="z", confidence=1.5)


# ── Postmortem ───────────────────────────────────────────────────────────────

def _make_triage():
    return TriageDecision(
        classification="novel",
        match_confidence=0.3,
        error_type="AttributeError",
        suggested_tier=TicketTier.L2_ANALYSIS,
        severity=Severity.SEV3,
        routing_reason="novel",
    )


def test_postmortem_valid():
    pm = Postmortem(
        incident_id=1,
        resolution_status="resolved",
        triage=_make_triage(),
        timeline=["step 1", "step 2"],
        root_cause="rename not completed",
        proposed_fix="update middleware.py",
        confidence=0.9,
        tools_called=4,
        duration_seconds=12.5,
        markdown="# Report",
    )
    assert pm.prevention_tickets == []
    assert pm.hypothesis is None


def test_postmortem_invalid_resolution():
    with pytest.raises(ValidationError):
        Postmortem(
            incident_id=1,
            resolution_status="maybe",  # not in Literal
            triage=_make_triage(),
            timeline=[],
            root_cause="x",
            proposed_fix="y",
            confidence=0.5,
            tools_called=1,
            duration_seconds=1.0,
            markdown="",
        )


def test_postmortem_confidence_range():
    with pytest.raises(ValidationError):
        Postmortem(
            incident_id=1,
            resolution_status="resolved",
            triage=_make_triage(),
            timeline=[],
            root_cause="x",
            proposed_fix="y",
            confidence=1.1,  # > 1.0
            tools_called=1,
            duration_seconds=1.0,
            markdown="",
        )
