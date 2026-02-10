from __future__ import annotations
import subprocess
from pathlib import Path
from typing import List

def git_status_porcelain(repo_root: Path) -> str:
    return subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root).decode()

def is_working_tree_clean(repo_root: Path) -> bool:
    return not git_status_porcelain(repo_root).strip()

def get_modified_files(repo_root: Path) -> List[str]:
    status = git_status_porcelain(repo_root)
    files: List[str] = []
    for line in status.strip().splitlines():
        if not line.strip():
            continue
        rest = line[2:].strip()
        if " -> " in rest:
            rest = rest.split(" -> ")[-1]
        files.append(str(Path(rest).as_posix()))
    return files

def commit_and_push(repo_root: Path, commit_message: str, allow_files: List[str]) -> None:
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
