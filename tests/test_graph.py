"""Tests for src/zeroops/graph.py — routing functions (no LLM calls)."""

from zeroops.graph import route_from_evaluator, route_from_triage


# ── route_from_triage ────────────────────────────────────────────────────────

def test_triage_known_pattern_routes_to_reporter():
    state = {"triage": {"classification": "known_pattern"}}
    assert route_from_triage(state) == "reporter"


def test_triage_novel_routes_to_planner():
    state = {"triage": {"classification": "novel"}}
    assert route_from_triage(state) == "planner"


def test_triage_insufficient_info_routes_to_planner():
    state = {"triage": {"classification": "insufficient_info"}}
    assert route_from_triage(state) == "planner"


def test_triage_missing_triage_routes_to_planner():
    # Defensive: triage key absent
    assert route_from_triage({}) == "planner"


def test_triage_none_triage_routes_to_planner():
    assert route_from_triage({"triage": None}) == "planner"


# ── route_from_evaluator ─────────────────────────────────────────────────────

def test_evaluator_continue_routes_to_planner():
    assert route_from_evaluator({"evaluator_decision": "continue"}) == "planner"


def test_evaluator_hypothesize_routes_to_hypothesizer():
    assert route_from_evaluator({"evaluator_decision": "hypothesize"}) == "hypothesizer"


def test_evaluator_give_up_routes_to_reporter():
    assert route_from_evaluator({"evaluator_decision": "give_up"}) == "reporter"


def test_evaluator_none_decision_routes_to_reporter():
    # give_up is the fallback for unexpected values
    assert route_from_evaluator({"evaluator_decision": None}) == "reporter"


def test_evaluator_missing_key_routes_to_reporter():
    assert route_from_evaluator({}) == "reporter"
