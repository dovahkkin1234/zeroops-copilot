"""Code inspection tools: read_file, grep_code, find_tests.

Plain functions with type hints. They operate on REPO_PATH and do not
know about LangGraph. Nodes call them directly.
"""

import re
from pathlib import Path

from ..config import settings


def _resolve_path(path: str) -> Path:
    """Resolve a path relative to REPO_PATH. Prevent directory traversal."""
    repo = Path(settings.repo_path).resolve()
    target = (repo / path).resolve()
    if not str(target).startswith(str(repo)):
        raise ValueError(f"Path traversal blocked: {path}")
    return target


def read_file(path: str, start_line: int | None = None,
              end_line: int | None = None) -> str:
    """Read a file slice. Returns content with line numbers prefixed.
    Paths are resolved relative to REPO_PATH."""
    target = _resolve_path(path)
    if not target.exists():
        return f"ERROR: File not found: {path}"
    if not target.is_file():
        return f"ERROR: Not a file: {path}"

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()

    # Apply line range
    start = (start_line or 1) - 1  # convert to 0-indexed
    end = end_line or len(lines)
    selected = lines[start:end]

    # Prefix with line numbers
    numbered = []
    for i, line in enumerate(selected, start=start + 1):
        numbered.append(f"{i:4d}: {line}")

    return "\n".join(numbered)


def grep_code(pattern: str, path_glob: str = "**/*.py") -> list[dict]:
    """Search for regex pattern across files matching glob.
    Returns list of {file, line, text} matches with 2 lines of context."""
    repo = Path(settings.repo_path).resolve()
    results = []

    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return [{"error": f"Invalid regex: {e}"}]

    for filepath in repo.glob(path_glob):
        if not filepath.is_file():
            continue
        # Skip hidden dirs and __pycache__
        if any(part.startswith(".") or part == "__pycache__"
               for part in filepath.relative_to(repo).parts):
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = content.splitlines()
        for i, line in enumerate(lines):
            if compiled.search(line):
                # Gather context: 2 lines before and after
                ctx_start = max(0, i - 2)
                ctx_end = min(len(lines), i + 3)
                context = "\n".join(
                    f"{'>' if j == i else ' '} {j+1}: {lines[j]}"
                    for j in range(ctx_start, ctx_end)
                )
                results.append({
                    "file": str(filepath.relative_to(repo)),
                    "line": i + 1,
                    "text": line.strip(),
                    "context": context,
                })

    return results


def find_tests(function_name: str) -> list[str]:
    """Find test files containing references to a function name.
    Returns list of file paths relative to REPO_PATH."""
    repo = Path(settings.repo_path).resolve()
    matches = []

    for filepath in repo.glob("**/test_*.py"):
        if any(part.startswith(".") or part == "__pycache__"
               for part in filepath.relative_to(repo).parts):
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            if function_name in content:
                matches.append(str(filepath.relative_to(repo)))
        except Exception:
            continue

    return matches
