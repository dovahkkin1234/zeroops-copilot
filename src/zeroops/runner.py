"""CLI entry point with rich-formatted streaming output.

This is the primary demo surface. Streams each node's output as a
rich.panel.Panel as it executes. Uses LangGraph node-level step
rendering — prints after each node returns.

Usage:
    python -m zeroops.runner --error-file path.txt
    python -m zeroops.runner --error "text"
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich import box

from .graph import build_graph
from .config import settings
from .memory.store import init_db

app = typer.Typer(help="ZeroOps Copilot — AI-powered incident investigation")
console = Console()

# Node display config
NODE_STYLES = {
    "triage": {"title": "🔍 Triage Agent", "border_style": "cyan"},
    "planner": {"title": "📋 Planner", "border_style": "blue"},
    "tool_executor": {"title": "🔧 Tool Executor", "border_style": "green"},
    "evaluator": {"title": "⚖️  Evaluator", "border_style": "yellow"},
    "hypothesizer": {"title": "💡 Hypothesizer", "border_style": "magenta"},
    "verifier": {"title": "🧪 Verifier", "border_style": "red"},
    "problem_manager": {"title": "🛡️  Problem Manager", "border_style": "bright_blue"},
    "reporter": {"title": "📝 Reporter", "border_style": "bright_green"},
}


def _format_node_output(node_name: str, state: dict) -> str:
    """Format a node's output for display in a panel."""
    if node_name == "triage":
        triage = state.get("triage", {})
        lines = [
            f"Classification: **{triage.get('classification', '?')}**",
            f"Error Type: {triage.get('error_type', '?')}",
            f"Severity: {triage.get('severity', '?')}",
            f"Tier: {triage.get('suggested_tier', '?')}",
            f"Reason: {triage.get('routing_reason', '?')[:200]}",
        ]
        if triage.get("matched_incident_id"):
            lines.append(f"Matched Incident: #{triage['matched_incident_id']}")
        return "\n".join(lines)

    elif node_name == "planner":
        plan = state.get("current_plan", {})
        return f"Tool: {plan.get('tool', '?')}\nArgs: {json.dumps(plan.get('arguments', {}))}\nReason: {plan.get('reasoning', '?')}"

    elif node_name == "tool_executor":
        history = state.get("tool_history", [])
        if history:
            last = history[-1] if isinstance(history[-1], dict) else history[-1]
            return f"Executed: {last.get('tool', '?')}\nResult: {last.get('result_summary', '?')[:300]}"
        return "No tool executed"

    elif node_name == "evaluator":
        return f"Decision: **{state.get('evaluator_decision', '?')}**\nIteration: {state.get('iteration', '?')}/{state.get('max_iterations', '?')}"

    elif node_name == "hypothesizer":
        hyp = state.get("hypothesis", {})
        return f"Pattern: **{hyp.get('pattern', '?')}**\nStatement: {hyp.get('statement', '?')[:300]}\nConfidence: {hyp.get('confidence', '?')}"

    elif node_name == "verifier":
        repro = state.get("repro", {})
        code = repro.get("code", "")[:200]
        executed = "Yes ✅" if repro.get("executed") else "No (disabled)"
        return f"Language: {repro.get('language', '?')}\nExecuted: {executed}\n```\n{code}\n```"

    elif node_name == "problem_manager":
        tickets = state.get("prevention_tickets", [])
        if tickets:
            lines = [f"Found {len(tickets)} prevention ticket(s):"]
            for t in tickets[:5]:
                if isinstance(t, dict):
                    lines.append(f"  📌 {t.get('location', '?')}: {t.get('pattern_match', '?')[:100]}")
            return "\n".join(lines)
        return "No additional vulnerable locations found."

    elif node_name == "reporter":
        pm = state.get("postmortem", {})
        return f"Status: **{pm.get('resolution_status', '?')}**\nConfidence: {pm.get('confidence', '?')}\nTools used: {pm.get('tools_called', '?')}"

    return json.dumps(state, indent=2, default=str)[:500]


async def run_investigation(error_text: str) -> dict:
    """Run the full investigation pipeline with live streaming output."""

    # Initialize DB
    init_db()

    console.print()
    console.print(Panel(
        error_text[:500],
        title="🚨 Incoming Error",
        border_style="red",
        box=box.DOUBLE,
    ))
    console.print()

    # Build and run graph
    graph = build_graph()
    start_time = time.time()

    # Track which nodes we've displayed
    displayed_states = set()

    # Run with streaming — iterate over graph steps
    initial_state = {
        "error_text": error_text,
        "triage": None,
        "current_plan": None,
        "evidence": [],
        "tool_history": [],
        "iteration": 0,
        "max_iterations": settings.max_investigation_loops,
        "evaluator_decision": None,
        "hypothesis": None,
        "repro": None,
        "prevention_tickets": [],
        "postmortem": None,
        "duration_seconds": 0.0,
    }

    final_state = None

    async for event in graph.astream(initial_state, stream_mode="updates"):
        for node_name, node_output in event.items():
            elapsed = time.time() - start_time
            style = NODE_STYLES.get(node_name, {"title": node_name, "border_style": "white"})

            # Merge node output into a running view for formatting
            if final_state is None:
                final_state = {**initial_state}
            if isinstance(node_output, dict):
                final_state.update(node_output)

            # Update duration
            final_state["duration_seconds"] = elapsed

            output_text = _format_node_output(node_name, final_state)

            console.print(Panel(
                output_text,
                title=f"{style['title']}  [{elapsed:.1f}s]",
                border_style=style["border_style"],
                box=box.ROUNDED,
            ))

    if final_state is None:
        final_state = initial_state

    total_time = time.time() - start_time
    final_state["duration_seconds"] = total_time

    # Print the final markdown report
    postmortem = final_state.get("postmortem", {})
    if postmortem and postmortem.get("markdown"):
        console.print()
        console.print(Panel(
            Markdown(postmortem["markdown"]),
            title="📋 Postmortem Report",
            border_style="bright_green",
            box=box.DOUBLE,
        ))

    # Final summary line
    tickets = len(final_state.get("prevention_tickets", []))
    confidence = postmortem.get("confidence", 0) if postmortem else 0
    console.print()
    console.print(
        f"[bold green]Tickets prevented:[/] {tickets} │ "
        f"[bold blue]Total duration:[/] {total_time:.1f}s │ "
        f"[bold yellow]Confidence:[/] {confidence:.0%}"
    )
    console.print()

    return final_state


@app.command()
def investigate(
    error_file: str = typer.Option(None, "--error-file", "-f",
                                    help="Path to file containing error text"),
    error: str = typer.Option(None, "--error", "-e",
                               help="Error text directly"),
):
    """Investigate an incident from error text or file."""
    if error_file:
        path = Path(error_file)
        if not path.exists():
            console.print(f"[red]Error file not found: {error_file}[/]")
            raise typer.Exit(1)
        error_text = path.read_text(encoding="utf-8").strip()
    elif error:
        error_text = error
    else:
        console.print("[red]Provide --error-file or --error[/]")
        raise typer.Exit(1)

    asyncio.run(run_investigation(error_text))


def main():
    app()


if __name__ == "__main__":
    main()
