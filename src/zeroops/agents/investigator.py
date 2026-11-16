"""Investigator sub-graph — Planner, Tool Executor, Evaluator, Hypothesizer, Verifier."""

import json
from pathlib import Path

from ..config import settings
from ..models import PlannerDecision, EvaluatorDecision, Hypothesis, ReproScript
from ..tools.code import read_file, grep_code, find_tests
from ..tools.git import git_log, git_show
from ..tools.repro import run_repro
from ._llm import run_as_json

_prompts_dir = Path(__file__).parent.parent / "prompts"
_planner_prompt = (_prompts_dir / "planner.md").read_text(encoding="utf-8")
_evaluator_prompt = (_prompts_dir / "evaluator.md").read_text(encoding="utf-8")
_hypothesizer_prompt = (_prompts_dir / "hypothesizer.md").read_text(encoding="utf-8")
_verifier_prompt = (_prompts_dir / "verifier.md").read_text(encoding="utf-8")

TOOLS = {
    "read_file": read_file,
    "grep_code": grep_code,
    "find_tests": find_tests,
    "git_log": git_log,
    "git_show": git_show,
}


def _format_evidence(evidence: list) -> str:
    if not evidence:
        return "No evidence collected yet."
    parts = []
    for i, ev in enumerate(evidence, 1):
        src = ev.get("source", "unknown")
        ref = ev.get("reference", "")
        obs = ev.get("observation", "")
        parts.append(f"{i}. [{src}] {ref}: {obs}")
    return "\n".join(parts)


def _format_tool_history(tool_history: list) -> str:
    if not tool_history:
        return "No tools called yet."
    return "\n".join(
        f"- {e.get('tool', 'unknown')}({e.get('args', {})})"
        for e in tool_history
    )


async def planner_node(state: dict) -> dict:
    """Choose the next single tool call based on current evidence."""
    triage = state.get("triage", {})
    prompt = _planner_prompt.format(
        error_text=state["error_text"],
        triage_routing_reason=triage.get("routing_reason", "No triage hint."),
        evidence=_format_evidence(state.get("evidence", [])),
        tool_history=_format_tool_history(state.get("tool_history", [])),
        iteration=state.get("iteration", 1),
        max_iterations=state.get("max_iterations", 8),
    )

    plan = await run_as_json(
        settings.pydantic_ai_model,
        "You are an investigation planner. Return valid JSON only.",
        prompt,
        PlannerDecision,
    )
    return {"current_plan": plan.model_dump()}


async def tool_executor_node(state: dict) -> dict:
    """Execute the tool call chosen by the Planner."""
    plan = state.get("current_plan")
    if not plan:
        return {
            "evidence": [{"source": "file", "reference": "error",
                          "observation": "No plan was set", "relevance": 0.0}],
            "tool_history": [{"tool": "none", "args": {}, "result_summary": "No plan"}],
        }

    tool_name = plan.get("tool", "")
    arguments = plan.get("arguments", {})

    tool_fn = TOOLS.get(tool_name)
    if not tool_fn:
        observation = f"Unknown tool: {tool_name}"
        return {
            "evidence": [{"source": "file", "reference": tool_name,
                          "observation": observation, "relevance": 0.0}],
            "tool_history": [{"tool": tool_name, "args": arguments,
                              "result_summary": observation}],
        }

    try:
        result = tool_fn(**arguments)
    except Exception as e:
        observation = f"Tool {tool_name} failed: {e}"
        return {
            "evidence": [{"source": "file", "reference": tool_name,
                          "observation": observation, "relevance": 0.3}],
            "tool_history": [{"tool": tool_name, "args": arguments,
                              "result_summary": observation}],
        }

    if isinstance(result, str):
        observation = result[:2000]
    elif isinstance(result, (list, dict)):
        observation = json.dumps(result, indent=2, default=str)[:2000]
    else:
        observation = str(result)[:2000]

    source = "file"
    if tool_name.startswith("git_"):
        source = "git_commit"
    elif tool_name == "find_tests":
        source = "test"

    reference = (
        arguments.get("path")
        or arguments.get("commit_hash")
        or (f"grep:{arguments['pattern']}" if "pattern" in arguments else "")
        or (f"tests_for:{arguments['function_name']}" if "function_name" in arguments else "")
    )

    return {
        "evidence": [{"source": source, "reference": reference,
                      "observation": observation, "relevance": 0.7}],
        "tool_history": [{"tool": tool_name, "args": arguments,
                          "result_summary": observation[:200]}],
        "iteration": state.get("iteration", 0) + 1,
    }


async def evaluator_node(state: dict) -> dict:
    """Decide: continue, hypothesize, or give_up."""
    prompt = _evaluator_prompt.format(
        error_text=state["error_text"],
        evidence=_format_evidence(state.get("evidence", [])),
        iteration=state.get("iteration", 1),
        max_iterations=state.get("max_iterations", 8),
    )

    decision = await run_as_json(
        settings.pydantic_ai_model,
        "You are an investigation evaluator. Return valid JSON only.",
        prompt,
        EvaluatorDecision,
    )
    return {"evaluator_decision": decision.decision}


async def hypothesizer_node(state: dict) -> dict:
    """Synthesize evidence into a single falsifiable hypothesis."""
    prompt = _hypothesizer_prompt.format(
        error_text=state["error_text"],
        evidence=_format_evidence(state.get("evidence", [])),
    )

    hypothesis = await run_as_json(
        settings.pydantic_ai_model,
        "You are a hypothesis synthesizer. Return valid JSON only.",
        prompt,
        Hypothesis,
    )
    return {"hypothesis": hypothesis.model_dump()}


async def verifier_node(state: dict) -> dict:
    """Generate a minimal reproduction script."""
    hypothesis = state.get("hypothesis", {})

    code_snippets = [
        ev.get("observation", "")[:500]
        for ev in state.get("evidence", [])
        if ev.get("source") == "file"
    ]
    relevant_code = "\n---\n".join(code_snippets) if code_snippets else "No code snippets available."

    prompt = _verifier_prompt.format(
        hypothesis=json.dumps(hypothesis, indent=2, default=str),
        relevant_code=relevant_code,
    )

    repro = await run_as_json(
        settings.pydantic_ai_model,
        "You are a reproduction script generator. Return valid JSON only.",
        prompt,
        ReproScript,
    )
    repro_dict = repro.model_dump()

    if settings.repro_execution_enabled and repro_dict.get("code"):
        exec_result = run_repro(repro_dict["code"], repro_dict.get("language", "python"))
        repro_dict["executed"] = exec_result.get("executed", False)
        repro_dict["execution_stdout"] = exec_result.get("stdout", "")
        repro_dict["execution_stderr"] = exec_result.get("stderr", "")
        repro_dict["reproduced"] = exec_result.get("success") is False

    return {"repro": repro_dict}
