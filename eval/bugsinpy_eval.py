#!/usr/bin/env python3
"""
BugsInPy fault-localization evaluation.

Evaluates the ZeroOps Investigator on real bugs from the BugsInPy dataset
(https://github.com/soarsmu/BugsInPy). Ground truth: the files changed in
the fix commit. Metric: did the agent mention a changed file in its evidence?

Three modes:
  --setup      Download BugsInPy metadata and project URLs (no git clones).
  --collect    Clone each project at the buggy commit, run the failing test to
               capture the error trace, record ground-truth diff. Requires git,
               pip, and the project's dependencies to be installable.
  --run        Load cached traces from eval/bugsinpy_data/traces/ and run the
               ZeroOps agent on each. Grades fault localization, saves results.
               --run is the only mode that calls the LLM.

Typical owner workflow (all on the Windows host that has Ollama):
    uv run python -m eval.bugsinpy_eval --setup
    uv run python -m eval.bugsinpy_eval --collect     # ~20 min, no LLM
    uv run python -m eval.bugsinpy_eval --run         # ~30 min with qwen3:8b

Attribution: BugsInPy is CC BY 4.0 by Widyasari et al.
  https://github.com/soarsmu/BugsInPy
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import venv
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── project imports ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
DATA_DIR     = ROOT / "eval" / "bugsinpy_data"
TRACES_DIR   = DATA_DIR / "traces"
REPOS_DIR    = DATA_DIR / "repos"
RESULTS_DIR  = ROOT / "eval" / "results"
BUGSINPY_API = "https://api.github.com/repos/soarsmu/BugsInPy"

# ── target projects ───────────────────────────────────────────────────────────
# Small-to-medium pure-Python projects. Each entry has the GitHub URL and
# the max number of bugs to collect (from BugsInPy's catalogue).
TARGET_PROJECTS: dict[str, dict] = {
    "tqdm": {
        "url": "https://github.com/tqdm/tqdm",
        "max_bugs": 4,
    },
    "luigi": {
        "url": "https://github.com/spotify/luigi",
        "max_bugs": 5,
    },
    "black": {
        "url": "https://github.com/psf/black",
        "max_bugs": 5,
    },
    "httpie": {
        "url": "https://github.com/httpie/httpie",
        "max_bugs": 5,
    },
    "thefuck": {
        "url": "https://github.com/nvbn/thefuck",
        "max_bugs": 5,
    },
}


# ── GitHub API helper ─────────────────────────────────────────────────────────

def _gh_get(url: str, params: dict | None = None) -> dict | list:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, params=params or {}, headers=headers, timeout=20)
    if resp.status_code == 403:
        print(f"[warn] GitHub rate-limit ({resp.headers.get('X-RateLimit-Remaining', '?')} remaining). "
              f"Set GITHUB_TOKEN env var for 5000 req/h (unauthenticated: 60/h).")
    resp.raise_for_status()
    return resp.json()


def _gh_file(path: str) -> str:
    """Fetch a file's decoded content from the BugsInPy repository."""
    import base64
    data = _gh_get(f"{BUGSINPY_API}/contents/{path}")
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


# ── BugsInPy metadata parsing ─────────────────────────────────────────────────

def _parse_bug_info(text: str) -> dict:
    """Parse a BugsInPy bug.info file into a dict."""
    out: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


# ── PHASE 1: setup ────────────────────────────────────────────────────────────

def cmd_setup() -> None:
    """Download BugsInPy metadata for all target projects."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = DATA_DIR / "metadata.json"

    print("[setup] Fetching BugsInPy metadata …")
    all_meta: dict = {}

    for project, proj_cfg in TARGET_PROJECTS.items():
        print(f"  {project} …", end=" ", flush=True)
        bugs: dict = {}
        for bug_id in range(1, proj_cfg["max_bugs"] + 1):
            info_path = f"projects/{project}/{bug_id}/bug.info"
            try:
                raw = _gh_file(info_path)
                bugs[str(bug_id)] = _parse_bug_info(raw)
            except Exception:
                break  # bug_id doesn't exist in BugsInPy for this project
            time.sleep(0.3)  # stay under anonymous rate limit

        all_meta[project] = {
            "url": proj_cfg["url"],
            "bugs": bugs,
        }
        print(f"{len(bugs)} bugs")

    metadata_path.write_text(
        json.dumps(all_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[setup] Saved {sum(len(v['bugs']) for v in all_meta.values())} "
          f"bug records → {metadata_path}")
    print("[setup] Next: run with --collect to clone repos and capture error traces.")


# ── PHASE 2: collect ──────────────────────────────────────────────────────────

def _run_cmd(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"[timeout after {timeout}s]"
    except Exception as e:
        return -1, "", str(e)


def _git_diff_files(repo_dir: Path, from_commit: str, to_commit: str) -> list[str]:
    """Return list of .py files changed between two commits."""
    rc, out, _ = _run_cmd(
        ["git", "diff", "--name-only", from_commit, to_commit],
        cwd=repo_dir,
    )
    if rc != 0:
        return []
    return [f for f in out.splitlines() if f.strip().endswith(".py")]


def cmd_collect(dry_run: bool = False) -> None:
    """Clone target projects, run failing tests, capture error traces."""
    meta_path = DATA_DIR / "metadata.json"
    if not meta_path.exists():
        print("[error] metadata.json not found — run --setup first")
        sys.exit(1)

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    collected = 0
    for project, proj_data in metadata.items():
        repo_url = proj_data["url"]
        for bug_id, bug_info in proj_data["bugs"].items():
            trace_path = TRACES_DIR / f"{project}_{bug_id}.json"
            if trace_path.exists():
                print(f"[skip] {project}/{bug_id} — already collected")
                collected += 1
                continue

            buggy = bug_info.get("buggy_commit_id", "")
            fixed = bug_info.get("fixed_commit_id", "")
            test_cases = bug_info.get("test_cases", "")
            if not buggy or not fixed or not test_cases:
                print(f"[skip] {project}/{bug_id} — incomplete bug.info")
                continue

            if dry_run:
                print(f"[dry-run] would collect {project}/{bug_id}: {buggy[:8]} → {fixed[:8]}")
                continue

            print(f"\n[collect] {project}/{bug_id}  buggy={buggy[:8]} fixed={fixed[:8]}")

            # Clone or reuse repo
            repo_dir = REPOS_DIR / f"{project}"
            if not (repo_dir / ".git").exists():
                print(f"  cloning {repo_url} …")
                rc, _, err = _run_cmd(["git", "clone", "--quiet", repo_url, str(repo_dir)],
                                      cwd=REPOS_DIR, timeout=300)
                if rc != 0:
                    print(f"  [error] clone failed: {err[:200]}")
                    continue
            else:
                print(f"  repo already cloned")

            # Checkout the buggy commit
            rc, _, err = _run_cmd(["git", "checkout", "-f", buggy], cwd=repo_dir)
            if rc != 0:
                print(f"  [error] checkout {buggy[:8]} failed: {err[:200]}")
                continue

            # Install the project (best-effort)
            print("  installing …")
            _run_cmd([sys.executable, "-m", "pip", "install", "-e", ".", "-q"],
                     cwd=repo_dir, timeout=120)
            _run_cmd([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                     cwd=repo_dir, timeout=120)

            # Run the failing test
            print(f"  running: pytest {test_cases} …")
            rc, out, err = _run_cmd(
                [sys.executable, "-m", "pytest", test_cases, "--tb=short", "-q", "--no-header"],
                cwd=repo_dir, timeout=60,
            )
            test_output = (out + "\n" + err).strip()

            # Extract the traceback / error section
            error_trace = _extract_traceback(test_output)
            if not error_trace:
                print(f"  [warn] no traceback found — test output: {test_output[:200]}")
                error_trace = test_output[:1000]  # use raw output as fallback

            # Ground-truth: which .py files changed in the fix?
            changed_files = _git_diff_files(repo_dir, buggy, fixed)
            if not changed_files:
                print(f"  [warn] no .py files found in diff {buggy[:8]}..{fixed[:8]}")

            # Save trace record
            record = {
                "project":       project,
                "bug_id":        bug_id,
                "buggy_commit":  buggy,
                "fixed_commit":  fixed,
                "test_cases":    test_cases,
                "error_trace":   error_trace,
                "changed_files": changed_files,
                "test_exit_code": rc,
                "source":        "BugsInPy (CC BY 4.0)",
            }
            trace_path.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
            print(f"  → saved {trace_path.name}  "
                  f"(exit={rc}, changed={changed_files})")
            collected += 1

    print(f"\n[collect] {collected} traces ready in {TRACES_DIR}")
    if collected > 0:
        print("[collect] Next: run with --run to evaluate the agent.")


def _extract_traceback(text: str) -> str:
    """Pull the most useful error section from pytest output."""
    lines = text.splitlines()

    # Find the last 'FAILED' marker and work backwards to the traceback
    # Also look for standalone 'ERROR' sections
    tb_start = None
    for i, line in enumerate(lines):
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            # Look back for the traceback header
            for j in range(max(0, i - 50), i):
                if "_ _ _" in lines[j] or "Traceback" in lines[j]:
                    tb_start = j
                    break
            if tb_start is not None:
                break

    if tb_start is None:
        # Try to find any Traceback block
        for i, line in enumerate(lines):
            if "Traceback (most recent call last)" in line:
                tb_start = i
                break

    if tb_start is None:
        return text[-2000:]  # last 2000 chars if no traceback found

    return "\n".join(lines[tb_start:tb_start + 50])


# ── PHASE 3: run agent ────────────────────────────────────────────────────────

async def _run_one(graph, trace_record: dict) -> dict:
    """Run the agent on one error trace; return a graded result dict."""
    from zeroops.config import settings

    # Point the agent at the cloned repo for this project
    project = trace_record["project"]
    repo_dir = REPOS_DIR / project
    old_repo_path = settings.repo_path
    settings.repo_path = str(repo_dir)

    start = time.time()
    try:
        initial_state = {
            "error_text":       trace_record["error_trace"],
            "triage":           None,
            "current_plan":     None,
            "evidence":         [],
            "tool_history":     [],
            "iteration":        0,
            "max_iterations":   settings.max_investigation_loops,
            "evaluator_decision": None,
            "hypothesis":       None,
            "repro":            None,
            "prevention_tickets": [],
            "postmortem":       None,
            "duration_seconds": 0.0,
        }
        final_state = await graph.ainvoke(initial_state)
        duration = time.time() - start
        final_state["duration_seconds"] = duration

        # Grade: did agent mention any of the changed files?
        changed = set(trace_record.get("changed_files", []))
        evidence = final_state.get("evidence", [])
        agent_files: set[str] = set()
        for ev in evidence:
            ref = ev.get("reference", "").replace("\\", "/")
            if ref:
                agent_files.add(ref)
        # Also check hypothesis statement and root_cause for file mentions
        postmortem = final_state.get("postmortem", {}) or {}
        combined_text = (
            (postmortem.get("root_cause") or "") + " " +
            (postmortem.get("proposed_fix") or "")
        )

        file_hit = any(
            any(c in f or f in c for c in changed)
            for f in agent_files
        ) or any(Path(c).name in combined_text for c in changed)

        return {
            "project":          project,
            "bug_id":           trace_record["bug_id"],
            "file_localization": file_hit,
            "pattern":          (final_state.get("hypothesis") or {}).get("pattern", ""),
            "resolution_status": postmortem.get("resolution_status", "unknown"),
            "confidence":       postmortem.get("confidence", 0.0),
            "tools_called":     len(final_state.get("tool_history", [])),
            "duration_seconds": duration,
            "changed_files":    list(changed),
            "agent_evidence_files": list(agent_files),
            "model":            settings.pydantic_ai_model,
            "error":            None,
        }

    except Exception as exc:
        return {
            "project":    project,
            "bug_id":     trace_record["bug_id"],
            "file_localization": False,
            "pattern":    "",
            "resolution_status": "error",
            "confidence": 0.0,
            "tools_called": 0,
            "duration_seconds": time.time() - start,
            "changed_files": trace_record.get("changed_files", []),
            "agent_evidence_files": [],
            "model": settings.pydantic_ai_model,
            "error": str(exc),
        }
    finally:
        settings.repo_path = old_repo_path


async def cmd_run(bugs_filter: str = "") -> None:
    """Run the ZeroOps agent on collected BugsInPy traces and grade results."""
    if not TRACES_DIR.exists():
        print("[error] No traces found — run --collect first")
        sys.exit(1)

    trace_files = sorted(TRACES_DIR.glob("*.json"))
    if not trace_files:
        print("[error] No .json files in", TRACES_DIR)
        sys.exit(1)

    # Optional filter: "tqdm_1,luigi_2"
    if bugs_filter:
        wanted = set(bugs_filter.split(","))
        trace_files = [f for f in trace_files if f.stem in wanted]

    # Lazy import — keep LLM imports out of --setup / --collect paths
    from zeroops.graph import build_graph
    from zeroops.config import settings
    from zeroops.memory.store import init_db, reset_db

    init_db()
    reset_db()
    graph = build_graph()

    print(f"[run] Evaluating {len(trace_files)} bugs  model={settings.pydantic_ai_model}")
    print("─" * 60)

    all_results: list[dict] = []
    for tf in trace_files:
        record = json.loads(tf.read_text(encoding="utf-8"))
        label = f"{record['project']}/{record['bug_id']}"
        print(f"  {label} … ", end="", flush=True)
        result = await _run_one(graph, record)
        all_results.append(result)
        status = "✓" if result["file_localization"] else "✗"
        print(f"{status}  {result['duration_seconds']:.1f}s  "
              f"pattern={result['pattern'] or '—'}")

    # Summary
    n = len(all_results)
    hits = sum(1 for r in all_results if r["file_localization"])
    errors = sum(1 for r in all_results if r["error"])
    avg_dur = sum(r["duration_seconds"] for r in all_results) / max(n, 1)

    print()
    print("═" * 60)
    print(f"  Fault localization: {hits}/{n}  ({hits/max(n,1):.1%})")
    print(f"  Errors:             {errors}/{n}")
    print(f"  Avg duration:       {avg_dur:.1f}s")
    print("═" * 60)

    # Save results
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RESULTS_DIR / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    result_obj = {
        "timestamp":   ts,
        "experiment":  "bugsinpy_fault_localization",
        "source":      "BugsInPy (CC BY 4.0, Widyasari et al.)",
        "model":       all_results[0]["model"] if all_results else "unknown",
        "n_bugs":      n,
        "metric":      "file_localization@1 (agent evidence ∩ changed files ≠ ∅)",
        "results": {
            "fault_localization_fraction": f"{hits}/{n}",
            "fault_localization_rate":     round(hits / max(n, 1), 4),
            "error_count":                 errors,
            "avg_duration_seconds":        round(avg_dur, 2),
        },
        "per_bug": all_results,
        "notes": (
            "Ground truth: Python files changed between buggy_commit and fixed_commit. "
            "Hit: at least one file in the agent's evidence references overlaps with "
            "the ground-truth changed files. "
            "'Fault localization' = file-level, not function-level."
        ),
    }
    out_path = out_dir / "bugsinpy_eval.json"
    out_path.write_text(json.dumps(result_obj, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"[saved] {out_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--setup", action="store_true",
                       help="Download BugsInPy metadata (no cloning, no LLM).")
    group.add_argument("--collect", action="store_true",
                       help="Clone repos, run failing tests, capture error traces.")
    group.add_argument("--run", action="store_true",
                       help="Run ZeroOps agent on collected traces (needs LLM).")
    ap.add_argument("--dry-run", action="store_true",
                    help="With --collect: show what would be collected, do nothing.")
    ap.add_argument("--bugs", default="",
                    help="With --run: comma-separated trace stems to evaluate "
                         "(e.g. tqdm_1,luigi_2). Runs all when omitted.")
    args = ap.parse_args()

    if args.setup:
        cmd_setup()
    elif args.collect:
        cmd_collect(dry_run=args.dry_run)
    elif args.run:
        asyncio.run(cmd_run(bugs_filter=args.bugs))
    else:
        ap.print_help()
        print("\nTypical workflow:")
        print("  uv run python -m eval.bugsinpy_eval --setup")
        print("  uv run python -m eval.bugsinpy_eval --collect")
        print("  uv run python -m eval.bugsinpy_eval --run")


if __name__ == "__main__":
    main()
