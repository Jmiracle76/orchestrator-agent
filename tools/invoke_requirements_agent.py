#!/usr/bin/env python3
"""
tools/invoke_requirements_agent.py

A minimal, repo-safe requirements-agent invoker.

Key goals (because humans are allergic to simplicity):
- Run the Requirements Agent in either review or integrate mode (auto-derived).
- Accept agent output in TWO formats:
  1) Preferred patch format:
     ## REVIEW_OUTPUT / ## INTEGRATE_OUTPUT (optional)
     ### SECTION: <Heading>
     ```md
     <full replacement content for that section>
     ```
  2) Fallback "full document" format:
     Agent outputs a markdown document with standard section headings (## 1. Document Control, etc.).
     We will extract sections by headings and apply replacements safely.

- Keep changes bounded to docs/requirements.md by default.
- Commit changes (optional) when modifications occur.

NOTE: This file is intentionally self-contained to avoid "helper script sprawl".
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


REQ_PATH_DEFAULT = "docs/requirements.md"

# Canonical section headings (level-2 "## " headings) expected in requirements doc
CANON_SECTIONS = [
    "## 1. Document Control",
    "## 2. Problem Statement",
    "## 3. Goals and Objectives",
    "## 4. Non-Goals",
    "## 5. Stakeholders and Users",
    "## 6. Assumptions",
    "## 7. Constraints",
    "## 8. Functional Requirements",
    "## 9. Non-Functional Requirements",
    "## 10. Interfaces and Integrations",
    "## 11. Data Considerations",
    "## 12. Risks and Open Issues",
    "## 13. Success Criteria and Acceptance",
    "## 14. Out of Scope",
    "## 15. Approval Record",
]

TOP_MARKERS = {"review": "## REVIEW_OUTPUT", "integrate": "## INTEGRATE_OUTPUT"}


class Fail(Exception):
    pass


def run(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def git_clean() -> Tuple[bool, str]:
    cp = run(["git", "status", "--porcelain"], check=True)
    return (cp.stdout.strip() == ""), cp.stdout.strip()


def git_branch() -> str:
    cp = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True)
    return cp.stdout.strip()


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def now_date() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d")


def derive_mode(doc: str) -> str:
    """
    Auto-derive mode:
    - integrate if there exist any Open Questions with Answer present AND Status not Resolved
    - else review
    This is intentionally simple and approximate.
    """
    # Look for Open Questions subsections: "#### Q-XXX"
    # and within each: "**Status:**", "**Answer:**"
    q_blocks = re.split(r"(?m)^####\s+Q-\d+\b", doc)
    # If no questions, review.
    if len(q_blocks) <= 1:
        return "review"

    # Find each question subsection content using finditer to keep IDs
    for m in re.finditer(r"(?m)^####\s+(Q-\d+)\b.*$", doc):
        q_id = m.group(1)
        start = m.start()
        # end at next #### or end of doc
        m2 = re.search(r"(?m)^####\s+Q-\d+\b", doc[m.end():])
        end = (m.end() + m2.start()) if m2 else len(doc)
        block = doc[start:end]

        status_m = re.search(r"(?mi)^\*\*Status:\*\*\s*(.+)\s*$", block)
        ans_m = re.search(r"(?mi)^\*\*Answer:\*\*\s*(.*)$", block)
        # Multi-line answer: take until next "**Integration Targets:**" or end
        ans_text = ""
        if ans_m:
            ans_start = ans_m.end()
            stop = re.search(r"(?mi)^\*\*Integration Targets:\*\*", block[ans_start:])
            ans_text = (block[ans_start: ans_start + stop.start()] if stop else block[ans_start:]).strip()

        status = (status_m.group(1).strip() if status_m else "").lower()
        has_answer = bool(ans_text and ans_text.strip() and ans_text.strip() != "[answer]")
        is_resolved = ("resolved" in status)

        if has_answer and not is_resolved:
            return "integrate"

    return "review"


@dataclass
class SectionPatch:
    heading: str   # exact "## ..." heading to replace
    content: str   # full replacement text INCLUDING heading line


def parse_section_blocks(agent_text: str) -> List[SectionPatch]:
    """
    Preferred format:
      ### SECTION: <Heading>
      ```md
      <content>
      ```
    Where <Heading> may be "## 2. Problem Statement" or just "2. Problem Statement".
    We normalize to exact canonical heading if possible.
    """
    patches: List[SectionPatch] = []
    # Find all SECTION blocks
    pattern = re.compile(r"(?s)###\s*SECTION:\s*(.+?)\s*\n```(?:md|markdown)?\s*\n(.*?)\n```\s*")
    for m in pattern.finditer(agent_text):
        raw_head = m.group(1).strip()
        body = m.group(2).rstrip()

        # Normalize heading
        if raw_head.startswith("## "):
            heading = raw_head
        elif raw_head.startswith("#"):
            heading = "## " + raw_head.lstrip("#").strip()
        else:
            heading = "## " + raw_head

        # If heading doesn't match canonical exactly, try fuzzy match by suffix
        if heading not in CANON_SECTIONS:
            cand = None
            for h in CANON_SECTIONS:
                if h.lower().endswith(heading.lower().lstrip("## ").strip()):
                    cand = h
                    break
            if cand:
                heading = cand

        if heading not in CANON_SECTIONS:
            # Ignore unknown sections rather than doing something dumb.
            continue

        # Ensure content includes heading line
        content = body
        if not content.lstrip().startswith("## "):
            content = heading + "\n\n" + body.strip() + "\n"
        else:
            # Trust the provided content
            content = content.strip() + "\n"

        patches.append(SectionPatch(heading=heading, content=content))

    return patches


def parse_full_document(agent_text: str) -> List[SectionPatch]:
    """
    Fallback: agent output is a markdown doc containing some canonical "## X. ..." headings.
    We extract each canonical section present and use it as a replacement patch.
    """
    # Build map of heading -> (start,end)
    # We look for level-2 headings only.
    headings = [(m.group(0), m.start()) for m in re.finditer(r"(?m)^##\s+\d+\.\s+.+$", agent_text)]
    if not headings:
        return []

    # Index by heading line normalized to canonical if possible
    found: List[Tuple[str, int]] = []
    for h, pos in headings:
        # Try direct canonical match
        h_norm = h.strip()
        if h_norm in CANON_SECTIONS:
            found.append((h_norm, pos))
            continue
        # Fuzzy by numeric prefix
        num_m = re.match(r"^##\s+(\d+)\.\s+(.+)$", h_norm)
        if num_m:
            n = int(num_m.group(1))
            if 1 <= n <= 15:
                canon = CANON_SECTIONS[n - 1]
                found.append((canon, pos))

    if not found:
        return []

    # Deduplicate by heading, keep first occurrence
    seen = set()
    found2 = []
    for h, pos in sorted(found, key=lambda x: x[1]):
        if h in seen:
            continue
        seen.add(h)
        found2.append((h, pos))

    # Determine section ranges by next found position
    patches: List[SectionPatch] = []
    for i, (h, start) in enumerate(found2):
        end = found2[i + 1][1] if i + 1 < len(found2) else len(agent_text)
        content = agent_text[start:end].rstrip() + "\n"
        # Ensure it starts with the canonical heading line
        if not content.startswith(h):
            # Replace first heading line with canonical
            content = re.sub(r"(?m)^##\s+\d+\.\s+.+$", h, content, count=1)
        patches.append(SectionPatch(heading=h, content=content))

    return patches


def apply_patches(doc: str, patches: List[SectionPatch]) -> str:
    """
    Replace each targeted section in the existing doc.
    A section is from its canonical heading line until the next canonical heading line.
    """
    if not patches:
        return doc

    # Build positions of canonical headings in existing doc
    positions: Dict[str, int] = {}
    for h in CANON_SECTIONS:
        m = re.search(re.escape(h) + r"\s*$", doc, flags=re.M)
        if m:
            positions[h] = m.start()

    # Apply patches in doc order, from bottom to top to keep indices stable
    # Only apply if the target section exists in the current doc
    # (If it's missing, we fail; the agent can repair via other mechanisms, but not here.)
    for p in sorted(patches, key=lambda x: positions.get(x.heading, -1), reverse=True):
        if p.heading not in positions:
            raise Fail(f"Target section missing in doc: {p.heading}")

        start = positions[p.heading]
        # Find next canonical heading after start
        next_pos = None
        for h2 in CANON_SECTIONS:
            pos2 = positions.get(h2)
            if pos2 is not None and pos2 > start:
                if next_pos is None or pos2 < next_pos:
                    next_pos = pos2
        end = next_pos if next_pos is not None else len(doc)

        doc = doc[:start] + p.content.rstrip() + "\n\n" + doc[end:].lstrip()

        # Recompute positions after modification? We apply bottom-up so earlier offsets are safe enough.
        # For safety, do nothing.

    return doc


def call_agent(profile_path: str, mode: str, req_text: str, extra_context: str) -> str:
    """
    Placeholder: the repo-specific implementation probably shells out to your LLM runner.
    This function assumes you already have a working 'ai-runner' style CLI or equivalent.

    We keep it dead simple:
    - Provide mode + current requirements doc + optional context.
    - Expect agent to return text to stdout.

    If your environment uses a different command, adjust AGENT_CMD env var.
    """
    cmd = os.environ.get("REQ_AGENT_CMD")
    if not cmd:
        # Default to the pattern you've been using in logs
        # You likely have a wrapper; set REQ_AGENT_CMD if different.
        cmd = "ai-runner agent"
    # Build a very plain prompt envelope
    prompt = f"""MODE: {mode}

AGENT PROFILE PATH: {profile_path}

REQUIREMENTS_DOC (current):
{req_text}

HUMAN_CONTEXT (optional):
{extra_context}
"""
    # Run command via shell so users can set complex commands (yes, it's gross).
    cp = subprocess.run(cmd, input=prompt, text=True, shell=True, capture_output=True)
    if cp.returncode != 0:
        raise Fail(f"Agent command failed ({cp.returncode}):\n{cp.stderr.strip()}")
    return cp.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requirements", default=REQ_PATH_DEFAULT)
    ap.add_argument("--profile", default="agent-profiles/requirements-agent.md")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--commit-message", default=None)
    args = ap.parse_args()

    req_path = Path(args.requirements)
    profile_path = args.profile

    print("[Pre-flight] Checking git working tree...")
    clean, details = git_clean()
    if not clean:
        print("ERROR: Working tree is not clean. Commit/stash first.\n" + details)
        return 2
    branch = git_branch()
    print(f"✓ Clean. Branch: {branch}")

    if not req_path.exists():
        print(f"ERROR: Requirements doc not found: {req_path}")
        return 2

    req_text = read_text(req_path)
    mode = derive_mode(req_text)
    print(f"[Mode] Running in {mode} mode\n")

    print("Optional context (Ctrl+D to finish):\n")
    try:
        extra_context = sys.stdin.read()
    except KeyboardInterrupt:
        extra_context = ""

    print("\n[Agent] Calling requirements agent...")
    agent_out = call_agent(profile_path, mode, req_text, extra_context)

    # Marker check: warn only
    marker = TOP_MARKERS.get(mode)
    if marker and marker not in agent_out:
        print(f"WARNING: Agent output missing expected marker '{marker}'. Attempting to parse anyway.")

    # Parse preferred blocks
    patches = parse_section_blocks(agent_out)

    # Fallback parse: full document
    if not patches:
        patches = parse_full_document(agent_out)

    if not patches:
        raise Fail("Agent output contained no SECTION blocks and no recognizable canonical '## X.' headings.")

    # Apply patches
    updated = apply_patches(req_text, patches)

    if updated == req_text:
        print("[Patching] No changes detected after applying patches; skipping commit")
        return 0

    write_text(req_path, updated)
    print(f"[Patching] Applied {len(patches)} section update(s) to {req_path}")

    if args.no_commit:
        print("[Commit] Skipped (disabled)")
        return 0

    # Commit only the requirements file
    run(["git", "add", str(req_path)])
    msg = args.commit_message
    if not msg:
        msg = f"requirements: {mode} pass ({now_date()})"
    run(["git", "commit", "-m", msg])
    print("[Commit] Committed changes")

    # Push (optional)
    try:
        run(["git", "push", "origin", branch], check=True)
        print("[Push] Pushed to origin")
    except subprocess.CalledProcessError as e:
        print("[Push] WARNING: Push failed. You can push manually.\n" + (e.stderr or "").strip())

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        print(f"ERROR: {e}")
        sys.exit(2)
