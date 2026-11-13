"""Benchmark harness — runs agent on 5 seeded bugs and reports metrics.

Usage:
    uv run python -m eval.benchmark                # default (with memory)
    uv run python -m eval.benchmark --no-memory    # ablation: memory disabled for bug4

Benchmark execution order (stateful — critical):
Phase A (cold start): Run bugs 1, 2, 3, 5 against empty memory.
Phase B (warm memory): Run bug 4 against populated memory (should hit L0 path).

With --no-memory the DB is temporarily cleared before bug4 so the agent
must re-investigate the same error without the memory shortcut.
Results are written to eval/results/<UTC-timestamp>/ as results.json + results.md.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box

# Add src to path so eval/ imports from src/zeroops
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydantic_ai.exceptions import ModelHTTPError

from zeroops.graph import build_graph
from zeroops.config import settings
from zeroops.memory.store import init_db, reset_db


# ── 429 / rate-limit retry ────────────────────────────────────────────────────

def _is_retryable(exc: BaseException) -> tuple[bool, str]:
    """Return (should_retry, label) for transient API errors.

    429 = rate limit / quota     → short backoff, base 2s
    503 = server overloaded      → longer backoff, base 15s
    504 = deadline exceeded      → longer backoff, base 15s
    """
    if isinstance(exc, ModelHTTPError):
        if exc.status_code == 429:
            return True, "429 rate-limit"
        if exc.status_code in (503, 504):
            return True, f"{exc.status_code} server unavailable"
    msg = str(exc).lower()
    if any(k in msg for k in ("rate limit", "resource exhausted", "quota")):
        return True, "rate-limit"
    if any(k in msg for k in ("unavailable", "deadline exceeded", "overloaded")):
        return True, "server unavailable"
    return False, ""


async def _invoke_with_retry(graph, state: dict, max_retries: int = 6) -> dict:
    """Invoke the graph, retrying transient errors with exponential backoff.

    429 (rate limit): 2s, 4s, 8s, 16s, 32s, 64s
    503/504 (overload): 15s, 30s, 60s, 60s, 60s, 60s  (capped at 60s)
    """
    for attempt in range(max_retries + 1):
        try:
            return await graph.ainvoke(state)
        except Exception as exc:
            retryable, label = _is_retryable(exc)
            if attempt < max_retries and retryable:
                is_overload = isinstance(exc, ModelHTTPError) and exc.status_code in (503, 504)
                base = 15.0 if is_overload else 2.0
                delay = min(base * (2 ** attempt), 60.0)
                console.print(f"  [yellow]{label} (attempt {attempt+1}/{max_retries}), retrying in {delay:.0f}s…[/]")
                await asyncio.sleep(delay)
            else:
                raise

console = Console()

RESULTS_DIR = Path(__file__).parent / "results"

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


def _get_git_hash() -> str:
    """Return the current HEAD commit hash (short form), or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
            cwd=Path(__file__).parent.parent,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


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

    # 3. File identification — did we find the right file in evidence?
    evidence = state.get("evidence", [])
    found_files = set()
    for ev in evidence:
        ref = ev.get("reference", "")
        if ref:
            found_files.add(ref.replace("\\", "/"))
    scores["file_found"] = any(bug_def["expected_file"] in f for f in found_files)

    # 4. Confidence
    scores["confidence"] = postmortem.get("confidence", 0.0) if postmortem else 0.0

    # 5. Resolution status
    scores["resolution_status"] = postmortem.get("resolution_status", "unknown") if postmortem else "unknown"

    # 6. Tools called
    scores["tools_called"] = len(state.get("tool_history", []))

    # 7. Duration
    scores["duration_seconds"] = state.get("duration_seconds", 0.0)

    # 8. Prevention tickets generated
    scores["prevention_tickets"] = len(state.get("prevention_tickets", []))

    return scores


def _build_initial_state() -> dict:
    return {
        "error_text": "",
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


async def _run_bug(graph, bug_id: str, bug_def: dict, fixtures_dir: Path,
                   checkpoint_path: Path | None = None) -> dict:
    """Run a single bug through the agent graph. Returns scores dict.

    If checkpoint_path is given, appends this bug's result to the checkpoint
    file immediately after completion so a mid-run crash loses no work.
    """
    error_file = fixtures_dir / bug_def["file"]
    error_text = error_file.read_text(encoding="utf-8").strip()

    console.print(f"\n[cyan]Running {bug_id}:[/] {bug_def['name']}")
    start = time.time()

    try:
        initial_state = _build_initial_state()
        initial_state["error_text"] = error_text

        final_state = await _invoke_with_retry(graph, initial_state)
        final_state["duration_seconds"] = time.time() - start
        scores = _score_result(bug_def, final_state)

        console.print(
            f"  ✅ Completed in {scores['duration_seconds']:.1f}s — "
            f"pattern={'✓' if scores['pattern_correct'] else '✗'} "
            f"file={'✓' if scores['file_found'] else '✗'} "
            f"confidence={scores['confidence']:.0%}"
        )

    except Exception as e:
        duration = time.time() - start
        console.print(f"  [red]❌ Failed: {e}[/]")
        scores = {
            "triage_correct": False, "pattern_correct": False,
            "file_found": False, "confidence": 0.0,
            "resolution_status": "error", "tools_called": 0,
            "duration_seconds": duration, "prevention_tickets": 0,
            "error": str(e),
        }

    # Checkpoint: persist this bug's result immediately
    if checkpoint_path is not None:
        _write_checkpoint(checkpoint_path, bug_id, scores)

    return scores


def _write_checkpoint(path: Path, bug_id: str, scores: dict) -> None:
    """Append one bug result to the checkpoint file (creates or updates)."""
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing[bug_id] = scores
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


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
            f"{r.get('duration_seconds', 0):.1f}s",
            str(r.get("prevention_tickets", 0)),
        )

    console.print(table)

    total = len(results)
    patterns_correct = sum(1 for r in results.values() if r.get("pattern_correct"))
    files_found = sum(1 for r in results.values() if r.get("file_found"))
    avg_confidence = sum(r.get("confidence", 0) for r in results.values()) / max(total, 1)
    total_tickets = sum(r.get("prevention_tickets", 0) for r in results.values())
    total_duration = sum(r.get("duration_seconds", 0) for r in results.values())

    console.print()
    console.print(f"[bold]Pattern accuracy:[/] {patterns_correct}/{total}")
    console.print(f"[bold]File identification:[/] {files_found}/{total}")
    console.print(f"[bold]Average confidence:[/] {avg_confidence:.0%}")
    console.print(f"[bold]Prevention tickets:[/] {total_tickets}")
    console.print(f"[bold]Total duration:[/] {total_duration:.1f}s")
    console.print()


def _persist_results(results: dict, condition: str, timestamp: str,
                     out_dir: Path | None = None):
    """Write results.json and results.md to eval/results/<timestamp>/."""
    if out_dir is None:
        out_dir = RESULTS_DIR / timestamp
        out_dir.mkdir(parents=True, exist_ok=True)

    total = len(results)
    patterns_correct = sum(1 for r in results.values() if r.get("pattern_correct"))
    files_found = sum(1 for r in results.values() if r.get("file_found"))
    avg_confidence = sum(r.get("confidence", 0) for r in results.values()) / max(total, 1)
    total_tickets = sum(r.get("prevention_tickets", 0) for r in results.values())
    total_duration = sum(r.get("duration_seconds", 0) for r in results.values())

    payload = {
        "metadata": {
            "timestamp": timestamp,
            "git_commit": _get_git_hash(),
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "utility_model": settings.utility_model,
            "embed_model": settings.embed_model,
            "max_investigation_loops": settings.max_investigation_loops,
            "condition": condition,
            # Token tracking: PydanticAI per-node usage is not propagated through
            # LangGraph state in this version. Field left null; wire in if needed.
            "token_tracking": None,
        },
        "per_bug_prices_usd_per_1k_tokens": None,  # populate when tracking is wired
        "results": results,
        "aggregate": {
            "pattern_accuracy_fraction": f"{patterns_correct}/{total}",
            "file_identification_fraction": f"{files_found}/{total}",
            "avg_confidence": round(avg_confidence, 4),
            "total_prevention_tickets": total_tickets,
            "total_duration_seconds": round(total_duration, 2),
        },
    }

    # Write JSON
    (out_dir / "results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    # Write Markdown table
    md_lines = [
        f"# ZeroOps Benchmark Results",
        f"",
        f"**Run:** {timestamp}  ",
        f"**Commit:** {payload['metadata']['git_commit']}  ",
        f"**Provider:** {settings.llm_provider}  ",
        f"**Model:** {settings.llm_model}  ",
        f"**Condition:** {condition}  ",
        f"",
        f"| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |",
        f"|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|",
    ]

    for bug_id in ["bug1", "bug2", "bug3", "bug4", "bug5"]:
        if bug_id not in results:
            continue
        r = results[bug_id]
        b = BUGS[bug_id]
        md_lines.append(
            f"| {bug_id} | {b['name'][:38]} "
            f"| {'✅' if r.get('triage_correct') else '❌'} "
            f"| {'✅' if r.get('pattern_correct') else '❌'} "
            f"| {'✅' if r.get('file_found') else '❌'} "
            f"| {r.get('confidence', 0):.0%} "
            f"| {r.get('tools_called', 0)} "
            f"| {r.get('duration_seconds', 0):.1f}s "
            f"| {r.get('prevention_tickets', 0)} |"
        )

    md_lines += [
        f"",
        f"**Pattern accuracy:** {patterns_correct}/{total}  ",
        f"**File identification:** {files_found}/{total}  ",
        f"**Average confidence:** {avg_confidence:.0%}  ",
        f"**Prevention tickets:** {total_tickets}  ",
        f"**Total duration:** {total_duration:.1f}s  ",
        f"",
        f"> Sample size: n={total} seeded bugs, synthetic, authored by the builder.",
        f"> Confidence values are model self-reported, not externally calibrated.",
    ]

    (out_dir / "results.md").write_text("\n".join(md_lines), encoding="utf-8")

    console.print(f"[dim]Results written to eval/results/{timestamp}/[/]")
    return out_dir


async def run_benchmark(no_memory: bool = False):
    """Run the full benchmark suite.

    Args:
        no_memory: If True, temporarily clear memory before Phase B so bug4
                   must be investigated from scratch (ablation condition).
    """
    fixtures_dir = Path(__file__).parent / "fixtures"
    condition = "no_memory" if no_memory else "with_memory"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Create the output dir early so checkpoints land there from the first bug
    out_dir = RESULTS_DIR / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out_dir / "checkpoint.json"

    console.print()
    console.print(f"[bold cyan]═══ ZeroOps Copilot Benchmark ═══[/] condition=[yellow]{condition}[/]")
    console.print(f"[dim]Results → {out_dir}[/]")
    console.print()

    # Reset memory for clean slate
    init_db()
    reset_db()

    graph = build_graph()
    results = {}

    # ── Phase A: cold start (bugs 1, 2, 3, 5) ────────────────────────────────
    console.print("[bold yellow]Phase A: Cold Start[/] (empty memory)")
    console.print("─" * 50)

    phase_a_bugs = {k: v for k, v in BUGS.items() if v["phase"] == "A"}
    for bug_id, bug_def in phase_a_bugs.items():
        results[bug_id] = await _run_bug(
            graph, bug_id, bug_def, fixtures_dir, checkpoint_path
        )

    # ── Phase B: warm (or cleared) memory — bug4 ─────────────────────────────
    label = "Cleared Memory (ablation)" if no_memory else "Warm Memory"
    expected = "→ full investigation" if no_memory else "→ bug4 should hit L0"
    console.print(f"\n[bold yellow]Phase B: {label}[/] ({expected})")
    console.print("─" * 50)

    if no_memory:
        reset_db()
        console.print("[dim]  Memory cleared for ablation run.[/]")

    for bug_id, bug_def in BUGS.items():
        if bug_def["phase"] != "B":
            continue
        scores = await _run_bug(
            graph, bug_id, bug_def, fixtures_dir, checkpoint_path
        )
        results[bug_id] = scores

        if not no_memory:
            l0_hit = "✓ L0!" if scores.get("triage_correct") else "✗ missed L0"
            console.print(f"  → Triage: {l0_hit}")

    # ── Print and persist ─────────────────────────────────────────────────────
    _print_results_table(results)
    _persist_results(results, condition, timestamp, out_dir)
    console.print(f"[bold green]Done.[/] Results saved to {out_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="ZeroOps Copilot benchmark harness"
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help=(
            "Ablation: clear memory before Phase B so bug4 must be investigated "
            "from scratch instead of hitting the L0 fast-path. Condition label: no_memory."
        ),
    )
    args = parser.parse_args()
    asyncio.run(run_benchmark(no_memory=args.no_memory))


if __name__ == "__main__":
    main()
