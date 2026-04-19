"""Investigator sub-graph — Planner, Tool Executor, Evaluator, Hypothesizer, Verifier.

Implemented in Phase 6. This is the HARD PART.
"""


async def planner_node(state: dict) -> dict:
    """Choose the next single tool call based on current evidence."""
    raise NotImplementedError("Phase 6")


async def tool_executor_node(state: dict) -> dict:
    """Execute the tool call chosen by the Planner."""
    raise NotImplementedError("Phase 6")


async def evaluator_node(state: dict) -> dict:
    """Decide: continue, hypothesize, or give_up."""
    raise NotImplementedError("Phase 6")


async def hypothesizer_node(state: dict) -> dict:
    """Synthesize evidence into a single falsifiable hypothesis."""
    raise NotImplementedError("Phase 6")


async def verifier_node(state: dict) -> dict:
    """Generate a minimal reproduction script."""
    raise NotImplementedError("Phase 6")
