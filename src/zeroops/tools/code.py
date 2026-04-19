"""Code inspection tools: read_file, grep_code, find_tests.

Implemented in Phase 4.
"""


def read_file(path: str, start_line: int | None = None,
              end_line: int | None = None) -> str:
    """Read a file slice. Returns content with line numbers prefixed.
    Paths are resolved relative to REPO_PATH."""
    raise NotImplementedError("Phase 4")


def grep_code(pattern: str, path_glob: str = "**/*.py") -> list[dict]:
    """Search for regex pattern across files matching glob.
    Returns list of {file, line, text} matches with 2 lines of context."""
    raise NotImplementedError("Phase 4")


def find_tests(function_name: str) -> list[str]:
    """Find test files containing references to a function name.
    Returns list of file paths."""
    raise NotImplementedError("Phase 4")
