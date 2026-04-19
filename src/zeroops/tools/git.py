"""Git inspection tools: git_log, git_show. Uses gitpython.

Implemented in Phase 4.
"""


def git_log(path: str, n: int = 10) -> list[dict]:
    """Return last N commits touching path.
    Each commit: {hash, author, date, subject}."""
    raise NotImplementedError("Phase 4")


def git_show(commit_hash: str) -> dict:
    """Return {hash, subject, message, diff, files_changed}."""
    raise NotImplementedError("Phase 4")
