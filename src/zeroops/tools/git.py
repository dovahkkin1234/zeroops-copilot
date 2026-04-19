"""Git inspection tools: git_log, git_show. Uses gitpython.

Plain functions. Operate on REPO_PATH.
"""

from pathlib import Path
from git import Repo

from ..config import settings


def _get_repo() -> Repo:
    """Get the git.Repo object for REPO_PATH."""
    repo_path = Path(settings.repo_path).resolve()
    return Repo(repo_path)


def git_log(path: str, n: int = 10) -> list[dict]:
    """Return last N commits touching path.
    Each commit: {hash, author, date, subject}."""
    repo = _get_repo()
    results = []

    try:
        commits = list(repo.iter_commits(paths=path, max_count=n))
    except Exception as e:
        return [{"error": str(e)}]

    for commit in commits:
        results.append({
            "hash": commit.hexsha[:8],
            "author": str(commit.author),
            "date": commit.committed_datetime.isoformat(),
            "subject": commit.summary,
        })

    return results


def git_show(commit_hash: str) -> dict:
    """Return {hash, subject, message, diff, files_changed}."""
    repo = _get_repo()

    try:
        commit = repo.commit(commit_hash)
    except Exception as e:
        return {"error": f"Commit not found: {commit_hash} — {e}"}

    # Get diff against parent
    if commit.parents:
        diff_text = repo.git.diff(commit.parents[0].hexsha, commit.hexsha)
        files_changed = [
            d.a_path or d.b_path
            for d in commit.parents[0].diff(commit)
        ]
    else:
        # Initial commit — diff against empty tree
        diff_text = repo.git.show(commit.hexsha, format="", p=True)
        files_changed = list(commit.stats.files.keys())

    return {
        "hash": commit.hexsha[:8],
        "subject": commit.summary,
        "message": commit.message.strip(),
        "diff": diff_text,
        "files_changed": files_changed,
    }
