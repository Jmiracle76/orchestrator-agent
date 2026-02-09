#!/usr/bin/env python3
"""Requirements Agent invoker (minimal, no env-var games).

You already do:
  source ~/ai-runner/config/anthropic.env
  source ~/ai-runner/venv/bin/activate

This script should *not* require any additional env vars.

Defaults:
- Agent profile: agent-profiles/requirements-agent.md
- Requirements doc: docs/requirements.md

It supports two agent output formats:
1) SECTION blocks (preferred):
   ### SECTION: <Exact Heading>
   ```md
   <new section content>
   ```
2) REVIEW-only: If no sections are emitted, we save the raw output and fail with a clear error.

No helper-module sprawl. If you want sprawl, do it on purpose.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_PROFILE = REPO_ROOT / "agent-profiles" / "requirements-agent.md"
DEFAULT_REQUIREMENTS_DOC = REPO_ROOT / "docs" / "requirements.md"
LAST_OUTPUT_PATH = REPO_ROOT / ".requirements_agent_last_output.md"


# --------------------------- git helpers ---------------------------

def run(cmd: List[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def git_current_branch() -> str:
    cp = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return (cp.stdout or "").strip()


def git_is_clean() -> bool:
    cp = run(["git", "status", "--porcelain"])
    return (cp.stdout or "").strip() == ""


def git_changed_files() -> List[str]:
    cp = run(["git", "status", "--porcelain"])
    files: List[str] = []
    for line in (cp.stdout or "").splitlines():
        # porcelain: XY <path>
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def git_commit(message: str, paths: List[Path]) -> None:
    run(["git", "add", "--"] + [str(p) for p in paths], capture=True)
    run(["git", "commit", "-m", message], capture=True)


def git_push(remote: str = "origin", branch: str = "main") -> None:
    run(["git", "push", remote, branch], capture=True)


# --------------------------- parsing & patching ---------------------------

SECTION_RE = re.compile(
    r"^###\\s+SECTION:\\s*(?P<title>.+?)\\s*$"  # title line
    r"\\n```(?:md|markdown)?\\n"               # fenced start
    r"(?P<body>.*?)"                           # body
    r"\\n```\\s*$",                            # fenced end
    re.MULTILINE | re.DOTALL,
)


def parse_section_blocks(agent_text: str) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    for m in SECTION_RE.finditer(agent_text):
        title = m.group("title").strip()
        body = m.group("body").rstrip() + "\n"
        blocks.append((title, body))
    return blocks


def replace_section(doc_text: str, heading: str, new_body: str) -> Tuple[str, bool]:
    """Replace the content under a markdown heading with new_body.

    Heading match is exact on the heading text, but tolerant on heading level:
    - Matches lines like "## 2. Problem Statement" etc.

    Replaces from heading line up to (but not including) next heading of same or higher level.
    """
    # Find a heading line containing the given heading string (exact text after hashes)
    # Example: doc has "## 2. Problem Statement". Heading passed should match that line's text.
    lines = doc_text.splitlines(keepends=True)

    def heading_line_text(line: str) -> str | None:
        hm = re.match(r"^(#{1,6})\\s+(.*?)(\\s+#+\\s*)?$", line.strip())
        if not hm:
            return None
        return hm.group(2).strip()

    start_idx = None
    start_level = None
    for i, line in enumerate(lines):
        txt = heading_line_text(line)
        if txt is not None and txt == heading:
            start_idx = i
            start_level = len(re.match(r"^(#{1,6})", line.strip()).group(1))  # type: ignore
            break

    if start_idx is None or start_level is None:
        return doc_text, False

    # Find end idx: next heading with level <= start_level
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        hm = re.match(r"^(#{1,6})\\s+", lines[j].lstrip())
        if hm:
            level = len(hm.group(1))
            if level <= start_level:
                end_idx = j
                break

    # Build replacement: keep heading line, then blank line, then new body, then ensure blank line
    heading_line = lines[start_idx]
    replacement = heading_line
    if not replacement.endswith("\n"):
        replacement += "\n"
    replacement += "\n" if not replacement.endswith("\n\n") else ""
    replacement += new_body
    if not replacement.endswith("\n"):
        replacement += "\n"
    replacement += "\n"

    new_lines = lines[: start_idx] + [replacement] + lines[end_idx:]
    return "".join(new_lines), True


# --------------------------- agent calling ---------------------------

@dataclass
class AgentResult:
    text: str
    model: str


def call_agent_via_anthropic(system_prompt: str, user_prompt: str, model: str) -> AgentResult:
    try:
        import anthropic  # type: ignore
    except Exception as e:
        raise RuntimeError(f"anthropic package not available: {e}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Did you source anthropic.env?")

    client = anthropic.Anthropic(api_key=api_key)

    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # SDK returns content blocks; join text blocks
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return AgentResult(text="\n".join(parts).strip() + "\n", model=model)


def call_agent_via_subprocess(agent_cmd: str, system_prompt: str, user_prompt: str, model: str) -> AgentResult:
    """Run an external command that reads prompts from stdin and prints response to stdout.

    agent_cmd is a shell string (kept simple on purpose).
    We pass MODEL in env as ANTHROPIC_MODEL for convenience.
    """
    env = os.environ.copy()
    env.setdefault("ANTHROPIC_MODEL", model)

    payload = f"# SYSTEM\n{system_prompt}\n\n# USER\n{user_prompt}\n"

    cp = subprocess.run(
        agent_cmd,
        cwd=str(REPO_ROOT),
        shell=True,
        text=True,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"Agent subprocess failed ({cp.returncode}):\n{cp.stderr}")
    return AgentResult(text=(cp.stdout or "").strip() + "\n", model=model)


# --------------------------- main workflow ---------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=str(DEFAULT_REQUIREMENTS_DOC), help="Path to requirements.md")
    ap.add_argument("--profile", default=str(DEFAULT_AGENT_PROFILE), help="Path to agent profile markdown")
    ap.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"))
    ap.add_argument(
        "--agent-cmd",
        default="",
        help=(
            "Optional subprocess command to call the agent. If not provided, uses Anthropic SDK directly. "
            "Example: --agent-cmd 'python tools/run_claude.py'"
        ),
    )
    ap.add_argument("--no-push", action="store_true", help="Commit but do not push")
    args = ap.parse_args()

    doc_path = Path(args.doc).resolve()
    profile_path = Path(args.profile).resolve()

    if not doc_path.exists():
        print(f"ERROR: requirements doc not found: {doc_path}")
        return 2
    if not profile_path.exists():
        print(f"ERROR: agent profile not found: {profile_path}")
        return 2

    print("[Pre-flight] Checking git working tree...")
    if not git_is_clean():
        print("ERROR: Working tree is not clean. Commit/stash your changes first.")
        return 2
    branch = git_current_branch()
    print(f"✓ Clean. Branch: {branch}")

    # Human optional context
    print("\nOptional context (Ctrl+D to finish):\n")
    try:
        human_context = sys.stdin.read()
    except KeyboardInterrupt:
        human_context = ""

    req_text = doc_path.read_text(encoding="utf-8")
    profile_text = profile_path.read_text(encoding="utf-8")

    system_prompt = profile_text
    user_prompt = (
        "You are updating the repository requirements document.\n\n"
        "Return updates ONLY in SECTION blocks when you are modifying sections.\n"
        "If you are not modifying any sections, return a short explanation and no SECTION blocks.\n\n"
        "# REQUIREMENTS_DOCUMENT\n"
        f"{req_text}\n\n"
        "# OPTIONAL_HUMAN_CONTEXT\n"
        f"{human_context.strip()}\n"
    )

    print("\n[Agent] Calling model...")
    try:
        if args.agent_cmd.strip():
            result = call_agent_via_subprocess(args.agent_cmd.strip(), system_prompt, user_prompt, args.model)
        else:
            result = call_agent_via_anthropic(system_prompt, user_prompt, args.model)
    except Exception as e:
        print(f"ERROR: Agent call failed: {e}")
        return 3

    LAST_OUTPUT_PATH.write_text(result.text, encoding="utf-8")
    print(f"✓ Agent responded (saved raw output to {LAST_OUTPUT_PATH.name})")

    blocks = parse_section_blocks(result.text)
    if not blocks:
        print("ERROR: Agent output contained no SECTION blocks.\n"
              "Expected '### SECTION: <Heading>' blocks with fenced markdown.\n"
              f"Raw output saved to: {LAST_OUTPUT_PATH}")
        return 4

    updated = req_text
    applied_any = False
    missing: List[str] = []
    for heading, body in blocks:
        updated, ok = replace_section(updated, heading, body)
        if ok:
            applied_any = True
        else:
            missing.append(heading)

    if missing:
        print("ERROR: Some SECTION headings were not found in the document. Refusing to apply partial patch.")
        for h in missing:
            print(f" - {h}")
        print(f"Raw output saved to: {LAST_OUTPUT_PATH}")
        return 4

    if not applied_any or updated == req_text:
        print("[Commit] No changes detected; skipping commit")
        return 0

    doc_path.write_text(updated, encoding="utf-8")

    # Ensure only the doc changed
    changed = git_changed_files()
    rel_doc = os.path.relpath(doc_path, REPO_ROOT)
    unexpected = [f for f in changed if f != rel_doc]
    if unexpected:
        print("ERROR: Unexpected file changes detected after applying patch:")
        for f in unexpected:
            print(f" - {f}")
        print("Refusing to commit.")
        return 5

    msg = "requirements: agent update"
    git_commit(msg, [doc_path])
    print("✓ Committed changes")

    if not args.no_push:
        # Push to current branch
        git_push("origin", branch)
        print("✓ Pushed to origin")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
