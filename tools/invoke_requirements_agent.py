#!/usr/bin/env python3
"""
tools/invoke_requirements_agent.py

A deliberately small-ish invocation script for the Requirements Agent.

Goals:
- Run the agent in either review or integrate mode (auto-detected).
- Apply agent output safely (supports a tolerant "section patch" format).
- Bump document version on every successful change.
- Commit (and optionally push) docs/requirements.md when it changes.

Design rules (so this doesn't become a 2700-line horror story again):
- Single file change target by default: docs/requirements.md
- No test harness generation, no extra docs, no helper-module sprawl.
- If you want new capabilities, add a flag first, not 400 new functions.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# -----------------------------
# Config
# -----------------------------

DEFAULT_REQUIREMENTS_PATH = Path("docs/requirements.md")
DEFAULT_AGENT_PROFILE_PATH = Path("agent-profiles/requirements-agent.md")
MODEL = os.environ.get("REQUIREMENTS_AGENT_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS = int(os.environ.get("REQUIREMENTS_AGENT_MAX_TOKENS", "6000"))

# Output markers (case-insensitive tolerated)
REVIEW_MARKER = "REVIEW_OUTPUT"
INTEGRATE_MARKER = "INTEGRATION_OUTPUT"

# -----------------------------
# Utilities
# -----------------------------

def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}")
    raise SystemExit(code)

def run(cmd: List[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=capture)

def git_available() -> bool:
    try:
        run(["git", "--version"], check=True, capture=True)
        return True
    except Exception:
        return False

def git_is_clean() -> bool:
    out = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    return out == ""

def git_branch() -> str:
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True).stdout.strip()

def git_changed_files() -> List[str]:
    out = run(["git", "status", "--porcelain"], capture=True).stdout.splitlines()
    files = []
    for line in out:
        if not line.strip():
            continue
        # format: XY path
        files.append(line[3:].strip())
    return files

def today_iso() -> str:
    return _dt.date.today().isoformat()

# -----------------------------
# Requirements doc parsing/updating
# -----------------------------

_VERSION_RE = re.compile(r"^\*\*Version:\*\*\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE)
_DOC_CONTROL_VERSION_RE = re.compile(r"^\|\s*Current Version\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$", re.MULTILINE)
_VERSION_HISTORY_TABLE_RE = re.compile(
    r"(^\|\s*Version\s*\|\s*Date\s*\|\s*Author\s*\|\s*Changes\s*\|\s*$\n"
    r"^\|\s*-+\s*\|\s*-+\s*\|\s*-+\s*\|\s*-+\s*\|\s*$\n)",
    re.MULTILINE
)

def parse_version(text: str) -> Optional[str]:
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None

def bump_version(ver: str) -> str:
    # Keep it simple: bump by 0.1 and keep one decimal if possible.
    # If version has two decimals, bump the last decimal place.
    parts = ver.split(".")
    if len(parts) == 1:
        return f"{int(parts[0]) + 1}.0"
    if len(parts) == 2:
        major = int(parts[0])
        minor = int(parts[1])
        minor += 1
        if minor >= 10:
            major += 1
            minor = 0
        return f"{major}.{minor}"
    # fallback
    try:
        f = float(ver)
        return f"{f + 0.1:.1f}".rstrip("0").rstrip(".")
    except Exception:
        return ver

def set_single_version_fields(text: str, new_ver: str) -> str:
    # Replace the first **Version:** line; remove duplicates if any.
    lines = text.splitlines()
    out = []
    version_seen = 0
    for line in lines:
        if re.match(r"^\*\*Version:\*\*\s*", line):
            version_seen += 1
            if version_seen == 1:
                out.append(f"**Version:** {new_ver}")
            # skip duplicates
            continue
        out.append(line)
    text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    # Document Control table: enforce a single Current Version row
    lines = text.splitlines()
    out = []
    cv_seen = 0
    for line in lines:
        if re.match(r"^\|\s*Current Version\s*\|", line):
            cv_seen += 1
            if cv_seen == 1:
                out.append(f"| Current Version | {new_ver} |")
            # skip duplicates
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")

def append_version_history(text: str, new_ver: str, mode: str) -> str:
    m = _VERSION_HISTORY_TABLE_RE.search(text)
    if not m:
        # Don't invent new structure. If missing, just leave it and let review catch it.
        return text
    insert_at = m.end(1)
    entry = f"| {new_ver} | {today_iso()} | Requirements Agent | {mode} pass |"
    return text[:insert_at] + entry + "\n" + text[insert_at:]

# -----------------------------
# Agent output handling
# -----------------------------

@dataclass
class SectionPatch:
    heading: str
    new_body: str

_SECTION_BLOCK_RE = re.compile(
    r"^###\s*SECTION:\s*(?P<head>.+?)\s*$\n"
    r"^```(?:md|markdown)?\s*$\n"
    r"(?P<body>.*?)\n"
    r"^```\s*$",
    re.MULTILINE | re.DOTALL
)

def detect_mode(requirements_text: str) -> str:
    """
    Mode heuristic:
    - integrate if there is any Open Question with Status: Open and a non-empty Answer:
    - otherwise review
    This keeps you from having to remember "integrate" vs "review".
    """
    # Very tolerant scan. If you change the format later, keep this simple.
    open_q_with_answer = re.search(
        r"^####\s*Q-\d{3}.*?$.*?^\\*\\*Status:\\*\\*\\s*Open\\b.*?$.*?^\\*\\*Answer:\\*\\*\\s*(?!\\s*$)(.+)$",
        requirements_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return "integrate" if open_q_with_answer else "review"

def validate_agent_output(mode: str, text: str) -> None:
    # Minimal validation: it must contain the marker and at least one SECTION block.
    marker = REVIEW_MARKER if mode == "review" else INTEGRATE_MARKER
    if re.search(rf"^##\s*{re.escape(marker)}\s*$", text, re.IGNORECASE | re.MULTILINE) is None:
        die(f"Agent output missing required top-level marker '## {marker}'.")
    if not _SECTION_BLOCK_RE.search(text):
        die("Agent output contained no SECTION blocks. Expected '### SECTION: <Heading>' blocks with fenced markdown.")

def apply_section_patches(requirements_text: str, patches: List[SectionPatch]) -> Tuple[str, List[str]]:
    """
    Replace the body of named sections, preserving the exact '## <Heading>' line.
    This avoids fragile diff application and stops the agent from rewriting the world.
    """
    changed_sections = []
    text = requirements_text

    for p in patches:
        # Find exact section start by heading (tolerate extra whitespace and optional numbering)
        # Example headings: "2. Problem Statement" or "Problem Statement"
        # We'll match by "##" line containing the heading text.
        # If the agent gives "Section 2: Problem Statement", we normalize.
        head = p.heading.strip()
        head_norm = re.sub(r"^Section\s+\d+\s*:\s*", "", head, flags=re.IGNORECASE).strip()

        # Regex to find section by heading text on a "##" line
        # Capture from after heading line to before next "## " or end.
        pattern = re.compile(
            rf"(^##\s+.*{re.escape(head_norm)}.*\n)(.*?)(?=^##\s+|\Z)",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(text)
        if not m:
            # If not found, skip; review pass should catch missing sections.
            continue

        before = text[: m.end(1)]
        after = text[m.end(2) :]

        new_body = p.new_body.strip("\n") + "\n\n"
        old_body = m.group(2)
        if old_body != new_body:
            changed_sections.append(head_norm)
            text = text[: m.start(1)] + m.group(1) + new_body + after

    return text, changed_sections

def extract_section_patches(agent_output: str) -> List[SectionPatch]:
    patches: List[SectionPatch] = []
    for m in _SECTION_BLOCK_RE.finditer(agent_output):
        patches.append(SectionPatch(heading=m.group("head").strip(), new_body=m.group("body").rstrip()))
    return patches

# -----------------------------
# Anthropic call
# -----------------------------

def call_agent(agent_profile: str, requirements: str, user_context: str, mode: str) -> str:
    instructions = get_agent_instructions(mode)
    prompt = f"""You are the Requirements Agent.

Agent profile:
---
{agent_profile}
---

Current requirements document:
---
{requirements}
---

Human context:
---
{user_context}
---

{instructions}

CRITICAL OUTPUT REQUIREMENTS:
- Output ONLY the structured patch format described in the agent profile.
- Do NOT output the full requirements document.
"""
    print(f"\n[Agent] Calling {MODEL}...")
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError:
        die("anthropic package not installed. Install with: pip install anthropic")

    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text

def get_agent_instructions(mode: str) -> str:
    if mode == "review":
        return (
            "Produce a review-only output: identify gaps/risks and create/maintain Open Questions. "
            "Do not mark questions resolved unless their integration targets are actually updated."
        )
    return (
        "Integrate answered Open Questions into their Integration Target sections. "
        "Update only the sections you touch, and keep changes minimal and schema-safe."
    )

# -----------------------------
# Main
# -----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS_PATH))
    ap.add_argument("--profile", default=str(DEFAULT_AGENT_PROFILE_PATH))
    ap.add_argument("--no-commit", action="store_true", help="Do not git commit changes.")
    ap.add_argument("--no-push", action="store_true", help="Do not git push after commit.")
    ap.add_argument("--force-mode", choices=["review", "integrate"], default=None, help="Override mode detection.")
    args = ap.parse_args()

    req_path = Path(args.requirements)
    prof_path = Path(args.profile)

    if not req_path.exists():
        die(f"Requirements file not found: {req_path}")
    if not prof_path.exists():
        die(f"Agent profile not found: {prof_path}")

    if git_available():
        print("[Pre-flight] Checking git working tree...")
        if not git_is_clean():
            die("Working tree is not clean. Commit or stash changes before running the agent.")
        print(f"✓ Clean. Branch: {git_branch()}")
    else:
        print("[Pre-flight] git not found; running without commit support.")

    requirements = req_path.read_text(encoding="utf-8")
    agent_profile = prof_path.read_text(encoding="utf-8")

    mode = args.force_mode or detect_mode(requirements)
    print(f"[Mode] Running in {mode} mode")

    print("\nOptional context (Ctrl+D to finish):\n")
    user_context = sys.stdin.read().strip()

    agent_output = call_agent(agent_profile, requirements, user_context, mode)
    validate_agent_output(mode, agent_output)
    print("✓ Agent output validated")

    patches = extract_section_patches(agent_output)
    new_text, changed_sections = apply_section_patches(requirements, patches)

    if not changed_sections:
        print("[Patching] WARNING: No sections matched; nothing to apply.")
        print("[Commit] No changes detected; skipping commit")
        return

    # bump version on every successful change
    old_ver = parse_version(new_text) or parse_version(requirements) or "0.0"
    new_ver = bump_version(old_ver)
    new_text = set_single_version_fields(new_text, new_ver)
    new_text = append_version_history(new_text, new_ver, mode)

    req_path.write_text(new_text, encoding="utf-8")
    print(f"[Patching] Updated sections: {', '.join(changed_sections)}")
    print(f"[Version] Bumped {old_ver} -> {new_ver}")

    if not git_available() or args.no_commit:
        print("[Commit] Skipped")
        return

    # Commit only the requirements doc
    changed = git_changed_files()
    if changed and changed != [str(req_path)] and changed != [req_path.as_posix()]:
        die(f"Unexpected file changes detected: {changed}. Aborting commit for safety.")

    run(["git", "add", str(req_path)])
    msg = f"requirements: {mode} pass (v{new_ver})"
    run(["git", "commit", "-m", msg])
    print(f"[Commit] Created commit: {msg}")

    if not args.no_push:
        try:
            run(["git", "push", "origin", "HEAD"])
            print("[Push] Pushed to origin")
        except Exception as e:
            print(f"[Push] WARNING: push failed ({e}). Commit still exists locally.")

if __name__ == "__main__":
    main()
