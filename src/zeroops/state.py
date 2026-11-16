"""LangGraph AgentState definition.

The shared state TypedDict that flows through every node in the graph.
Uses Annotated[list, add] for append-only accumulation of evidence and
tool history across investigation loop iterations.
"""

from typing import TypedDict, Annotated, Optional
from operator import add


class AgentState(TypedDict):
    # Input
    error_text: str

    # Triage outputs
    triage: Optional[dict]               # TriageDecision as dict

    # Investigation state
    current_plan: Optional[dict]
    evidence: Annotated[list, add]
    tool_history: Annotated[list[dict], add]  # each entry: {tool, args, result_summary}

    # Loop control
    iteration: int
    max_iterations: int
    evaluator_decision: Optional[str]    # continue | hypothesize | give_up

    # Hypothesis + verification
    hypothesis: Optional[dict]
    repro: Optional[dict]

    # Problem manager output
    prevention_tickets: Annotated[list, add]

    # Final output
    postmortem: Optional[dict]
    duration_seconds: Optional[float]
    start_time: Optional[float]  # epoch seconds; used by reporter to compute duration
