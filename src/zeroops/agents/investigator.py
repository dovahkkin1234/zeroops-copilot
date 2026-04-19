"""Investigator sub-graph — Planner, Tool Executor, Evaluator, Hypothesizer, Verifier.

Each node loads its prompt from src/zeroops/prompts/ at import time.
Each LLM call uses PydanticAI with output_type set to the appropriate model.
Retry policy: 1 automatic retry on validation failure with repair prefix.
"""

import json
import traceback
from pathlib import Path

from pydantic_ai import Agent
from pydantic import ValidationError

from ..config import settings
from ..models import (
    PlannerDecision,
    EvaluatorDecision,
    Hypothesis,
    ReproScript,
    EvidenceItem,
)
from ..tools.code import read_file, grep_code, find_tests
from ..tools.git import git_log, git_show
from ..tools.repro import run_repro

# Load prompts at import time
_prompts_dir = Path(__file__).parent.parent / "prompts"
_planner_prompt = (_prompts_dir / "planner.md").read_text(encoding="utf-8")
_evaluator_prompt = (_prompts_dir / "evaluator.md").read_text(encoding="utf-8")
_hypothesizer_prompt = (_prompts_dir / "hypothesizer.md").read_text(encoding="utf-8")
_verifier_prompt = (_prompts_dir / "verifier.md").read_text(encoding="utf-8")

# Tool dispatch table
TOOLS = {
    "read_file": read_file,
    "grep_code": grep_code,
    "find_tests": find_tests,
    "git_log": git_log,
    "git_show": git_show,
}


def _format_evidence(evidence: list) -> str:
    """Format evidence list for prompt injection."""
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
    """Format tool history for prompt injection."""
    if not tool_history:
        return "No tools called yet."
    parts = []
    for entry in tool_history:
        tool = entry.get("tool", "unknown")
        args = entry.get("args", {})
        parts.append(f"- {tool}({args})")
    return "\n".join(parts)


async def _call_with_retry(agent: Agent, prompt: str, max_retries: int = 1):
    """Call PydanticAI agent with retry on validation failure."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0 and last_error:
                prompt = (
                    f"Your previous response failed validation. "
                    f"Return ONLY valid JSON matching the schema. "
                    f"Error: {last_error}\n\n{prompt}"
                )
            result = await agent.run(prompt)
            return result
        except ValidationError as e:
            last_error = str(e)
            if attempt >= max_retries:
                raise
        except Exception as e:
            if "validation" in str(e).lower() and attempt < max_retries:
                last_error = str(e)
                continue
            raise
    raise RuntimeError(f"Retry exhausted. Last error: {last_error}")


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

    agent = Agent(
        settings.pydantic_ai_model,
        output_type=PlannerDecision,
        system_prompt="You are an investigation planner. Return valid JSON only.",
    )

    result = await _call_with_retry(agent, prompt)
    plan = result.output.model_dump()

    return {"current_plan": plan}


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

    # Format result as observation
    if isinstance(result, str):
        observation = result[:2000]  # cap long outputs
    elif isinstance(result, list):
        observation = json.dumps(result, indent=2, default=str)[:2000]
    elif isinstance(result, dict):
        observation = json.dumps(result, indent=2, default=str)[:2000]
    else:
        observation = str(result)[:2000]

    # Determine source type
    source = "file"
    if tool_name.startswith("git_"):
        source = "git_commit"
    elif tool_name == "find_tests":
        source = "test"

    reference = ""
    if "path" in arguments:
        reference = arguments["path"]
    elif "commit_hash" in arguments:
        reference = arguments["commit_hash"]
    elif "pattern" in arguments:
        reference = f"grep:{arguments['pattern']}"
    elif "function_name" in arguments:
        reference = f"tests_for:{arguments['function_name']}"

    evidence_item = {
        "source": source,
        "reference": reference,
        "observation": observation,
        "relevance": 0.7,  # default, evaluator will judge
    }

    tool_record = {
        "tool": tool_name,
        "args": arguments,
        "result_summary": observation[:200],
    }

    return {
        "evidence": [evidence_item],
        "tool_history": [tool_record],
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

    agent = Agent(
        settings.pydantic_ai_model,
        output_type=EvaluatorDecision,
        system_prompt="You are an investigation evaluator. Return valid JSON only.",
    )

    result = await _call_with_retry(agent, prompt)
    decision = result.output

    return {"evaluator_decision": decision.decision}


async def hypothesizer_node(state: dict) -> dict:
    """Synthesize evidence into a single falsifiable hypothesis."""
    prompt = _hypothesizer_prompt.format(
        error_text=state["error_text"],
        evidence=_format_evidence(state.get("evidence", [])),
    )

    agent = Agent(
        settings.pydantic_ai_model,
        output_type=Hypothesis,
        system_prompt="You are a hypothesis synthesizer. Return valid JSON only.",
    )

    result = await _call_with_retry(agent, prompt)
    hypothesis = result.output.model_dump()

    return {"hypothesis": hypothesis}


async def verifier_node(state: dict) -> dict:
    """Generate a minimal reproduction script."""
    hypothesis = state.get("hypothesis", {})

    # Gather relevant code snippets from evidence
    code_snippets = []
    for ev in state.get("evidence", []):
        if ev.get("source") == "file":
            code_snippets.append(ev.get("observation", "")[:500])

    relevant_code = "\n---\n".join(code_snippets) if code_snippets else "No code snippets available."

    prompt = _verifier_prompt.format(
        hypothesis=json.dumps(hypothesis, indent=2, default=str),
        relevant_code=relevant_code,
    )

    agent = Agent(
        settings.pydantic_ai_model,
        output_type=ReproScript,
        system_prompt="You are a reproduction script generator. Return valid JSON only.",
    )

    result = await _call_with_retry(agent, prompt)
    repro = result.output.model_dump()

    # Optionally execute the repro
    if settings.repro_execution_enabled and repro.get("code"):
        exec_result = run_repro(repro["code"], repro.get("language", "python"))
        repro["executed"] = exec_result.get("executed", False)
        repro["execution_stdout"] = exec_result.get("stdout", "")
        repro["execution_stderr"] = exec_result.get("stderr", "")
        repro["reproduced"] = exec_result.get("success") is False  # error = reproduced

    return {"repro": repro}
