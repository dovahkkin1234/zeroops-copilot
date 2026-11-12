"""Assembles the full LangGraph state machine.

Three agents, one graph, shared substrate:
- Triage → routes to Investigator or Reporter (L0 fast-path)
- Investigator → Planner → Tool Executor → Evaluator loop
- Evaluator → Hypothesizer → Verifier → Problem Manager → Reporter
"""

from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .agents.triage import triage_node
from .agents.investigator import (
    planner_node, tool_executor_node, evaluator_node,
    hypothesizer_node, verifier_node
)
from .agents.problem_manager import problem_manager_node
from .agents.reporter import reporter_node


def route_from_triage(state: AgentState) -> str:
    """Route based on triage classification."""
    triage = state.get("triage") or {}
    if triage.get("classification") == "known_pattern":
        return "reporter"        # L0 fast path
    return "planner"


def route_from_evaluator(state: AgentState) -> str:
    """Route based on evaluator decision."""
    decision = state.get("evaluator_decision")
    if decision == "continue":
        return "planner"
    if decision == "hypothesize":
        return "hypothesizer"
    return "reporter"            # give_up routes to reporter with uncertainty


def build_graph():
    """Assemble and compile the full LangGraph."""
    g = StateGraph(AgentState)

    # Add all nodes
    g.add_node("triage", triage_node)
    g.add_node("planner", planner_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("hypothesizer", hypothesizer_node)
    g.add_node("verifier", verifier_node)
    g.add_node("problem_manager", problem_manager_node)
    g.add_node("reporter", reporter_node)

    # Entry point
    g.add_edge(START, "triage")

    # Triage routes to either reporter (L0) or planner (investigation)
    g.add_conditional_edges("triage", route_from_triage,
                            {"reporter": "reporter", "planner": "planner"})

    # Investigation loop
    g.add_edge("planner", "tool_executor")
    g.add_edge("tool_executor", "evaluator")

    # Evaluator decides: continue loop, hypothesize, or give up
    g.add_conditional_edges("evaluator", route_from_evaluator, {
        "planner": "planner",
        "hypothesizer": "hypothesizer",
        "reporter": "reporter",
    })

    # Hypothesis → verification → problem scan → report
    g.add_edge("hypothesizer", "verifier")
    g.add_edge("verifier", "problem_manager")
    g.add_edge("problem_manager", "reporter")
    g.add_edge("reporter", END)

    return g.compile()
