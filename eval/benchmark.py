"""Benchmark harness — runs agent on 5 seeded bugs and reports metrics.

Must run with: uv run python -m eval.benchmark

Benchmark execution order (stateful — critical):
Phase A (cold start): Run bugs 1, 2, 3, 5 against empty memory.
Phase B (warm memory): Run bug 4 against populated memory (should hit L0 path).
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box

# Add src to path since we're running from eval/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zeroops.graph import build_graph
from zeroops.config import settings
from zeroops.memory.store import init_db, reset_db

console = Console()

# Bug definitions with expected outcomes
BUGS = {
    "bug1": {
        "name": "auth.validate_token → verify_token (middleware)",
        "file": "bug1_error.txt",
        "expected_pattern": "incomplete_symbol_rename",
        "expected_file": "middleware.py",
        "phase": "A",
    },
    "bug2": {
        "name": "utils.normalize_string → normalize_text (db)",
        "file": "bug2_error.txt",
        "expected_pattern": "incomplete_symbol_rename",
        "expected_file": "db.py",
        "phase": "A",
    },
    "bug3": {
        "name": "unchecked None from parse_date (app)",
        "file": "bug3_error.txt",
        "expected_pattern": "unchecked_none_return",
        "expected_file": "app.py",
        "phase": "A",
    },
    "bug4": {
        "name": "validate_token variant (L0 test, handlers)",
        "file": "bug4_error.txt",
        "expected_pattern": "incomplete_symbol_rename",
        "expected_file": "handlers.py",
        "expected_triage": "known_pattern",
        "phase": "B",
    },
    "bug5": {
        "name": "stale import in test_auth.py",
        "file": "bug5_error.txt",
        "expected_pattern": "stale_import",
        "expected_file": "tests/test_auth.py",
        "phase": "A",
    },
}


def _score_result(bug_def: dict, state: dict) -> dict:
    """Score an individual benchmark result."""
    postmortem = state.get("postmortem", {})
    hypothesis = state.get("hypothesis", {})
    triage = state.get("triage", {})

    scores = {}

    # 1. Triage accuracy — did we route correctly?
    expected_triage = bug_def.get("expected_triage")
    if expected_triage:
        actual_triage = triage.get("classification", "")
        scores["triage_correct"] = actual_triage == expected_triage
    else:
        scores["triage_correct"] = triage.get("classification") in ("novel", "known_pattern")

    # 2. Root cause pattern match
    actual_pattern = hypothesis.get("pattern", "") if hypothesis else ""
    scores["pattern_correct"] = actual_pattern == bug_def["expected_pattern"]

    # 3. File identification — did we find the right file?
    evidence = state.get("evidence", [])
    found_files = set()
    for ev in evidence:
        ref = ev.get("reference", "")
        if ref:
            found_files.add(ref.replace("\\", "/"))
    scores["file_found"] = any(
        bug_def["expected_file"] in f for f in found_files
    )

    # 4. Confidence
    scores["confidence"] = postmortem.get("confidence", 0.0) if postmortem else 0.0

    # 5. Resolution status
    scores["resolution_status"] = postmortem.get("resolution_status", "unknown") if postmortem else "unknown"

    # 6. Tools called
    scores["tools_called"] = len(state.get("tool_history", []))

    # 7. Duration
    scores["duration"] = state.get("duration_seconds", 0.0)

    # 8. Prevention tickets generated
    scores["prevention_tickets"] = len(state.get("prevention_tickets", []))

    return scores


async def run_benchmark():
    """Run the full benchmark suite."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    console.print()
    console.print("[bold cyan]═══ ZeroOps Copilot Benchmark ═══[/]")
    console.print()

    # Reset memory for clean slate
    init_db()
    reset_db()

    graph = build_graph()
    results = {}

    # Phase A: cold start (bugs 1, 2, 3, 5)
    console.print("[bold yellow]Phase A: Cold Start[/] (empty memory)")
    console.print("─" * 50)

    phase_a_bugs = {k: v for k, v in BUGS.items() if v["phase"] == "A"}
    for bug_id, bug_def in phase_a_bugs.items():
        error_file = fixtures_dir / bug_def["file"]
        error_text = error_file.read_text(encoding="utf-8").strip()

        console.print(f"\n[cyan]Running {bug_id}:[/] {bug_def['name']}")
        start = time.time()

        try:
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

            final_state = await graph.ainvoke(initial_state)
            final_state["duration_seconds"] = time.time() - start
            scores = _score_result(bug_def, final_state)
            results[bug_id] = scores
            console.print(f"  ✅ Completed in {scores['duration']:.1f}s — "
                         f"pattern={'✓' if scores['pattern_correct'] else '✗'} "
                         f"file={'✓' if scores['file_found'] else '✗'} "
                         f"confidence={scores['confidence']:.0%}")

        except Exception as e:
            console.print(f"  [red]❌ Failed: {e}[/]")
            results[bug_id] = {
                "triage_correct": False, "pattern_correct": False,
                "file_found": False, "confidence": 0.0,
                "resolution_status": "error", "tools_called": 0,
                "duration": time.time() - start, "prevention_tickets": 0,
                "error": str(e),
            }

    # Phase B: warm memory (bug 4 — L0 test)
    console.print(f"\n[bold yellow]Phase B: Warm Memory[/] (bug4 should hit L0)")
    console.print("─" * 50)

    for bug_id, bug_def in BUGS.items():
        if bug_def["phase"] != "B":
            continue

        error_file = fixtures_dir / bug_def["file"]
        error_text = error_file.read_text(encoding="utf-8").strip()

        console.print(f"\n[cyan]Running {bug_id}:[/] {bug_def['name']}")
        start = time.time()

        try:
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

            final_state = await graph.ainvoke(initial_state)
            final_state["duration_seconds"] = time.time() - start
            scores = _score_result(bug_def, final_state)
            results[bug_id] = scores

            l0_hit = "✓ L0!" if scores.get("triage_correct") else "✗ missed L0"
            console.print(f"  ✅ Completed in {scores['duration']:.1f}s — {l0_hit}")

        except Exception as e:
            console.print(f"  [red]❌ Failed: {e}[/]")
            results[bug_id] = {
                "triage_correct": False, "pattern_correct": False,
                "file_found": False, "confidence": 0.0,
                "resolution_status": "error", "tools_called": 0,
                "duration": time.time() - start, "prevention_tickets": 0,
                "error": str(e),
            }

    # Print results table
    _print_results_table(results)

    return results


def _print_results_table(results: dict):
    """Print a rich table with benchmark results."""
    console.print()
    console.print("[bold cyan]═══ Results ═══[/]")

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Bug", style="white", width=6)
    table.add_column("Name", style="dim", width=40)
    table.add_column("Triage", justify="center", width=7)
    table.add_column("Pattern", justify="center", width=8)
    table.add_column("File", justify="center", width=6)
    table.add_column("Confidence", justify="right", width=11)
    table.add_column("Tools", justify="right", width=6)
    table.add_column("Duration", justify="right", width=9)
    table.add_column("Tickets", justify="right", width=8)

    for bug_id in ["bug1", "bug2", "bug3", "bug4", "bug5"]:
        if bug_id not in results:
            continue
        r = results[bug_id]
        bug_def = BUGS[bug_id]

        table.add_row(
            bug_id,
            bug_def["name"][:38],
            "✅" if r.get("triage_correct") else "❌",
            "✅" if r.get("pattern_correct") else "❌",
            "✅" if r.get("file_found") else "❌",
            f"{r.get('confidence', 0):.0%}",
            str(r.get("tools_called", 0)),
            f"{r.get('duration', 0):.1f}s",
            str(r.get("prevention_tickets", 0)),
        )

    console.print(table)

    # Aggregate scores
    total = len(results)
    patterns_correct = sum(1 for r in results.values() if r.get("pattern_correct"))
    files_found = sum(1 for r in results.values() if r.get("file_found"))
    avg_confidence = sum(r.get("confidence", 0) for r in results.values()) / max(total, 1)
    total_tickets = sum(r.get("prevention_tickets", 0) for r in results.values())
    total_duration = sum(r.get("duration", 0) for r in results.values())

    console.print()
    console.print(f"[bold]Pattern accuracy:[/] {patterns_correct}/{total}")
    console.print(f"[bold]File identification:[/] {files_found}/{total}")
    console.print(f"[bold]Average confidence:[/] {avg_confidence:.0%}")
    console.print(f"[bold]Prevention tickets:[/] {total_tickets}")
    console.print(f"[bold]Total duration:[/] {total_duration:.1f}s")
    console.print()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
