from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List


def git_status_porcelain(repo_root: Path) -> str:
    """Return git status output in porcelain format for machine parsing."""
    return subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root).decode()


def is_working_tree_clean(repo_root: Path) -> bool:
    """True if there are no uncommitted changes in the repo."""
    return not git_status_porcelain(repo_root).strip()


def get_modified_files(repo_root: Path) -> List[str]:
    """List modified file paths based on porcelain output."""
    status = git_status_porcelain(repo_root)
    files: List[str] = []
    for line in status.strip().splitlines():
        if not line.strip():
            continue
        # Porcelain format is two status columns followed by the path.
        rest = line[2:].strip()
        # Normalize renames to the destination filename.
        if " -> " in rest:
            rest = rest.split(" -> ")[-1]
        files.append(str(Path(rest).as_posix()))
    return files


def commit_and_push(repo_root: Path, commit_message: str, allow_files: List[str]) -> None:
    """Commit and push only the allowed files, rejecting unexpected changes."""
    modified = get_modified_files(repo_root)
    if not modified:
        return
    unexpected = [f for f in modified if f not in allow_files]
    if unexpected:
        raise RuntimeError(f"Unexpected files modified: {unexpected}. Allowed: {allow_files}")
    for f in allow_files:
        subprocess.check_call(["git", "add", f], cwd=repo_root)
    subprocess.check_call(["git", "commit", "-m", commit_message], cwd=repo_root)
    subprocess.check_call(["git", "push"], cwd=repo_root)
