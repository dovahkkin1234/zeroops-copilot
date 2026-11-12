"""Tests for src/zeroops/state.py — AgentState TypedDict structure."""

from operator import add

from zeroops.state import AgentState


def test_agent_state_minimal():
    state: AgentState = {
        "error_text": "AttributeError: module 'auth' has no attribute 'validate_token'",
        "triage": None,
        "current_plan": None,
        "evidence": [],
        "tool_history": [],
        "iteration": 0,
        "max_iterations": 8,
        "evaluator_decision": None,
        "hypothesis": None,
        "repro": None,
        "prevention_tickets": [],
        "postmortem": None,
        "duration_seconds": None,
    }
    assert state["error_text"].startswith("AttributeError")
    assert state["iteration"] == 0


def test_evidence_accumulates_with_add():
    # Annotated[list, add] uses the `add` reducer — simulates LangGraph merge
    a = [{"source": "file", "reference": "auth.py", "observation": "x", "relevance": 0.9}]
    b = [{"source": "git_commit", "reference": "abc123", "observation": "y", "relevance": 0.8}]
    merged = add(a, b)
    assert len(merged) == 2
    assert merged[0]["source"] == "file"
    assert merged[1]["source"] == "git_commit"


def test_tool_history_accumulates_with_add():
    h1 = [{"tool": "read_file", "args": {"path": "auth.py"}, "result_summary": "content"}]
    h2 = [{"tool": "git_log", "args": {"path": "auth.py"}, "result_summary": "2 commits"}]
    merged = add(h1, h2)
    assert len(merged) == 2


def test_prevention_tickets_accumulates_with_add():
    t1 = [{"location": "db.py:2", "pattern_match": "stale", "proposed_fix": "fix", "confidence": 0.8}]
    t2 = [{"location": "tests/test_auth.py:1", "pattern_match": "stale", "proposed_fix": "fix", "confidence": 0.7}]
    assert len(add(t1, t2)) == 2
