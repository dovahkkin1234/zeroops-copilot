"""Reproduction tools: run_repro. The Verifier node generates the script;
this function only runs it.

Implemented in Phase 4.
"""


def run_repro(script: str, language: str = "python",
              timeout: int = 5) -> dict:
    """Execute repro in subprocess. Returns {success, stdout, stderr,
    exit_code}. Only runs if REPRO_EXECUTION_ENABLED=true.
    If false, returns {executed: false, reason: 'disabled'}."""
    raise NotImplementedError("Phase 4")
