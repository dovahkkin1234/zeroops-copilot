"""Reproduction tools: run_repro.

The Verifier node generates the script via LLM; this function only runs it.
Execution is gated by REPRO_EXECUTION_ENABLED.
"""

import subprocess
import tempfile
from pathlib import Path

from ..config import settings


def run_repro(script: str, language: str = "python",
              timeout: int = 5) -> dict:
    """Execute repro in subprocess. Returns {success, stdout, stderr,
    exit_code}. Only runs if REPRO_EXECUTION_ENABLED=true.
    If false, returns {executed: false, reason: 'disabled'}."""

    if not settings.repro_execution_enabled:
        return {
            "executed": False,
            "reason": "disabled",
            "stdout": "",
            "stderr": "",
        }

    # Write script to a temp file
    suffix = ".py" if language == "python" else ".sh"
    tmp_dir = Path(tempfile.mkdtemp())
    script_path = tmp_dir / f"repro{suffix}"
    script_path.write_text(script, encoding="utf-8")

    try:
        if language == "python":
            cmd = ["python", str(script_path)]
        else:
            cmd = ["bash", str(script_path)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(settings.repo_path).resolve()),
        )

        return {
            "executed": True,
            "success": result.returncode == 0,
            "stdout": result.stdout[:2000],  # cap output size
            "stderr": result.stderr[:2000],
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "executed": True,
            "success": False,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "executed": True,
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        }
    finally:
        # Clean up
        try:
            script_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except Exception:
            pass
