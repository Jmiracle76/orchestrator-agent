#!/usr/bin/env python3
"""
Minimal Deterministic Requirements Agent Invoker

This script is a thin, deterministic wrapper whose only job is patch-only
invocation and application. All document understanding and repair is
delegated to the Requirements Agent.

Control flow:
1. Load document
2. Invoke agent with full context
3. Apply returned changes
4. Enforce required top-level section presence
5. Exit

Responsibilities of this script (ONLY):
- Load requirements document
- Invoke the Requirements Agent
- Apply agent output to the document
- Enforce required top-level section presence
- Fail fast on catastrophic errors (file missing, invalid format)

All semantic validation, schema repair, ghost question detection,
cross-reference checking, and human edit normalization belong to the agent.
"""

import os
import sys
import argparse
import subprocess
import re
from datetime import date
from pathlib import Path
from typing import List

# ---------- Configuration ----------
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = REPO_ROOT / "docs" / "requirements.md"
AGENT_PROFILE = REPO_ROOT / "agent-profiles" / "requirements-agent.md"
SECTION_BOUNDARY_PATTERN = r'(?=\n###\s|\Z)'
# ---------- Canonical Template ----------
CANONICAL_TEMPLATE = """# Requirements Document

<!-- ============================================================================ -->
<!-- TEMPLATE BASELINE - Reusable Requirements Template                          -->
<!-- ============================================================================ -->
<!-- This is a clean, canonical template for requirements documentation          -->
<!-- To use: Copy this file to your project and replace placeholder content      -->
<!-- For agents: This is a "Template Baseline" - see special rules below         -->
<!-- ============================================================================ -->

<!-- This document is authored by humans and reviewed by the Requirements Agent -->
<!-- It serves as the single source of truth for what the project must deliver -->
<!-- Status values: Draft | Under Review | Approved -->

**Project:** [Project Name]
**Version:** 0.0
**Status:** Draft
**Last Updated:** [Date]
**Approved By:** Pending
**Approval Date:** Pending

---

## 1. Document Control

<!-- This section tracks the lifecycle of this requirements document -->

| Field | Value |
|-------|-------|
| Document Status | Draft |
| Current Version | 0.0 |
| Last Modified | [Date] |
| Modified By | Template |
| Approval Status | Pending - Revisions Required |
| Approved By | Pending |
| Approval Date | Pending |

### Version History

<!-- Requirements Agent updates this section when integrating answers in integrate_answers mode -->
<!-- Each integration must document: which Question IDs were integrated, which sections were updated, and nature of changes -->

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.0 | [Date] | Template | Template baseline - clean reusable starting point |

---

## 2. Problem Statement

<!-- Describe the problem being solved, not the solution -->
<!-- Must be specific, observable, and defensible -->
<!-- Focus on: What is broken? What pain exists? What is the measurable impact? -->

[Content needed for Problem Statement]

---

## 3. Goals and Objectives

### Primary Goals

<!-- The must-have outcomes that define project success -->

1. [Primary goal 1]
2. [Primary goal 2]

### Secondary Goals

<!-- Nice-to-have outcomes that add value but are not success-critical -->

1. [Secondary goal 1]
2. [Secondary goal 2]

---

## 4. Non-Goals

<!-- Explicitly state what this project will NOT do -->
<!-- Prevents scope creep and sets clear boundaries -->

This project explicitly does NOT include:

1. [Non-goal 1]
2. [Non-goal 2]

---

## 5. Stakeholders and Users

### Primary Stakeholders

<!-- Who are the decision makers and primary interested parties? -->

- [Stakeholder 1]
- [Stakeholder 2]

### End Users

<!-- Who will directly use or be affected by this system? -->

- [User group 1]
- [User group 2]

---

## 6. Assumptions

<!-- List assumptions made during requirements definition -->
<!-- These are things taken as true but not verified -->

1. [Assumption 1]
2. [Assumption 2]

---

## 7. Constraints

### Technical Constraints

<!-- Technology or platform limitations -->

- [Technical constraint 1]
- [Technical constraint 2]

### Business Constraints

<!-- Budget, timeline, or organizational limitations -->

- [Business constraint 1]
- [Business constraint 2]

### Resource Constraints

<!-- Team, skill, or tooling limitations -->

- [Resource constraint 1]
- [Resource constraint 2]

---

## 8. Functional Requirements

<!-- What the system must DO -->
<!-- Format: FR-XXX: [Name] -->
<!-- Each requirement must have: Description, Priority, Acceptance Criteria -->

### FR-001: [Requirement Name]

**Description:** [What this requirement delivers]

**Priority:** [High | Medium | Low]

**Acceptance Criteria:**
- [Criterion 1]
- [Criterion 2]

---

## 9. Non-Functional Requirements

<!-- How the system must BEHAVE -->
<!-- Quality attributes: performance, security, usability, etc. -->
<!-- Must be measurable -->

### NFR-001: [Requirement Name]

**Description:** [What quality attribute this addresses]

**Target:** [Measurable target or threshold]

**Measurement Method:** [How this will be verified]

---

## 10. Interfaces and Integrations

### External Systems

<!-- Systems this project must integrate with -->

- [System 1]: [Integration purpose]
- [System 2]: [Integration purpose]

### Data Exchange

<!-- What data flows in/out and in what format -->

- [Data flow 1]: [Format and frequency]
- [Data flow 2]: [Format and frequency]

---

## 11. Data Considerations

### Data Requirements

<!-- What data is needed, created, or managed -->

- [Data requirement 1]
- [Data requirement 2]

### Privacy & Security

<!-- Data protection, compliance, and security requirements -->

- [Privacy requirement 1]
- [Security requirement 2]

### Data Retention

<!-- Define how long data is kept and where -->

- [Retention policy 1]
- [Retention policy 2]

---

## 12. Risks and Open Issues

### Identified Risks

<!-- Requirements Agent updates this section during review -->
<!-- Risks should identify quality gaps, ambiguities, or potential project obstacles -->
<!-- Do NOT delete resolved risks - update their mitigation status -->

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| R-001 | Template baseline state | Low | Low | This is a template document - populate with project-specific content before approval | Requirements Agent |

---

### Intake

<!-- Human notes and unstructured thoughts go here -->
<!-- Requirements Agent processes this section and converts ambiguities into Open Questions -->
<!-- This section is cleared after processing -->

[Empty - add human notes here as needed]

---

### Open Questions

<!-- Requirements Agent manages this section -->
<!-- Format: Question ID, Status (Open/Resolved/Deferred), Asked By, Date, Question, Answer, Integration Targets -->

[No open questions at this time]

---

## 13. Success Criteria and Acceptance

### Project Success Criteria

<!-- Define the overall measures of project success -->

1. [Success criterion 1]
2. [Success criterion 2]

### Acceptance Criteria

<!-- These are the criteria that must be met for the project to be considered complete -->

- [Acceptance criterion 1]
- [Acceptance criterion 2]

---

## 14. Out of Scope

<!-- Explicitly state what will NOT be delivered in this project -->
<!-- These are binding exclusions documented to prevent scope creep -->

The following items are explicitly OUT OF SCOPE for this project:

1. [Out of scope item 1]
2. [Out of scope item 2]

---

## 15. Approval Record

<!-- This section tracks approval workflow and status -->
<!-- Only the Product Owner can set status to "Approved" -->
<!-- Requirements Agent can only recommend "Ready for Approval" or "Pending - Revisions Required" -->

| Field | Value |
|-------|-------|
| Current Status | Draft |
| Recommended By | Pending |
| Recommendation Date | Pending |
| Approved By | Pending |
| Approval Date | Pending |
| Review Notes | Template baseline - not ready for approval until populated with project-specific content |

---

### Approval Status Definitions

- **Draft:** Initial authoring in progress, not ready for review
- **Ready for Approval:** Requirements Agent has validated all quality criteria are met, all open questions resolved, no High/Medium risks remain, Success Criteria populated - awaiting Product Owner approval
- **Approved:** Product Owner has approved requirements as complete and accurate - triggers handoff to Planning Agent
- **Pending - Revisions Required:** Quality issues, open questions, or unmitigated risks prevent approval recommendation

### Approval Criteria

For the Requirements Agent to recommend "Ready for Approval", ALL of the following must be true:

1. [ ] All 15 sections are present and populated with project-specific content
2. [ ] All Open Questions are marked "Resolved" (or Open Questions table is empty)
3. [ ] No High or Medium severity risks remain unmitigated
4. [ ] Success Criteria section (Section 13) is populated with measurable criteria
5. [ ] All functional requirements have testable acceptance criteria
6. [ ] All non-functional requirements have measurable targets
7. [ ] No contradictory requirements exist
8. [ ] Document is internally consistent

---
"""

# ---------- Required Sections ----------
REQUIRED_SECTIONS = [
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
INTAKE_PLACEHOLDER = (
    "[Empty - Add your unstructured notes, questions, or thoughts here. They will be converted "
    "to formal Open Questions by the Requirements Agent.]"
)
STATUS_TABLE_FIELDS = ("| Approval Status |", "| Current Status |")
SECTION_HEADER_PATTERN = re.compile(r'^##\s+(\d+)\.\s+(.+?)\s*$')



def _normalize_section_header(line: str) -> str:
    match = SECTION_HEADER_PATTERN.match(line.strip())
    if not match:
        return ""
    number, title = match.groups()
    title = re.sub(r'\s+', ' ', title.strip())
    return f"## {number}. {title}"


def missing_required_sections(content: str) -> List[str]:
    """Return a list of missing required top-level sections."""
    headers = {_normalize_section_header(line) for line in content.splitlines()}
    headers.discard("")
    return [section for section in REQUIRED_SECTIONS if section not in headers]


def has_answered_questions(content: str) -> bool:
    """Detect answered questions by checking Answer blocks for non-placeholder content."""
    placeholder_answers = {
        "[awaiting response]",
        "[awaiting answer]",
        "[pending]",
        "[tbd]",
    }
    # Expected format: Answer block followed by Integration Targets.
    answer_pattern = re.compile(
        r'\*\*Answer:\*\*\s*(.*?)(?=\n\*\*Integration Targets:\*\*|\Z)',
        re.DOTALL
    )
    for match in answer_pattern.finditer(content):
        answer = match.group(1).strip()
        normalized = " ".join(answer.split()).lower()
        if not normalized:
            continue
        if normalized in placeholder_answers:
            continue
        if normalized.startswith('[') and normalized.endswith(']') and any(
            token in normalized for token in ("awaiting", "pending", "tbd")
        ):
            continue
        return True
    return False


def determine_mode(requirements: str) -> str:
    """Determine execution mode based on answered questions."""
    return "integrate" if has_answered_questions(requirements) else "review"


# ---------- Agent Instructions ----------
def get_agent_instructions(mode: str) -> str:
    """Return mode-specific instructions for the Requirements Agent."""
    shared_notice = """
REQUIRED INVARIANTS:
1. Every referenced Open Question ID MUST exist as a canonical Open Question subsection.
2. If a Risk requires a question, create the Open Question entry first, then reference it.
3. You own the Open Questions lifecycle: create, update, resolve, and clear as needed.
4. If required top-level sections are missing or malformed, repair them in your output.
5. Output patch-only content (do NOT output the full document).
"""

    if mode == "review":
        return f"""{shared_notice}
MODE: review

OUTPUT FORMAT:
## REVIEW_OUTPUT

### STATUS_UPDATE
[Status recommendation + reasons]

### RISKS
[Full updated content for the "Identified Risks" subsection, or "No risk changes"]

### OPEN_QUESTIONS
[Full updated content for the "Open Questions" subsection, or "No question changes"]

### INTAKE_CLEAR
[{INTAKE_PLACEHOLDER}]
"""

    return f"""{shared_notice}
MODE: integrate

OUTPUT FORMAT:
## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Question ID: <Q-XXX>
- Section: <exact section heading, e.g., "## 8. Functional Requirements">
<content to append, with source traceability>

### RISKS
[Full updated content for the "Identified Risks" subsection, or "No risk changes"]

### OPEN_QUESTIONS
[Full updated content for the "Open Questions" subsection, or "No question changes"]

### STATUS_UPDATE
[Status recommendation + reasons]
"""


# ---------- Patch Application Helpers ----------
def _extract_patch_section(agent_output: str, section: str) -> str:
    match = re.search(
        rf'### {re.escape(section)}\s*\n(.*?){SECTION_BOUNDARY_PATTERN}',
        agent_output,
        re.DOTALL
    )
    return match.group(1).strip() if match else ""


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _update_status(lines: List[str], status_update: str) -> None:
    status_value = _first_nonempty_line(status_update)
    if not status_value:
        return
    in_header = True
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_header = False
        if in_header and line.startswith("**Status:**"):
            lines[i] = f"**Status:** {status_value}"
        else:
            for field in STATUS_TABLE_FIELDS:
                if field in line:
                    lines[i] = f"{field} {status_value} |"
                    break


def _should_apply_patch(content: str, skip_phrases: tuple[str, ...]) -> bool:
    if not content:
        return False
    normalized = content.strip().lower()
    return all(phrase not in normalized for phrase in skip_phrases)


def _replace_subsection(lines: List[str], header: str, content: str) -> bool:
    content = content or ""
    content_lines = [line.rstrip() for line in content.strip().splitlines()]
    header_text = re.sub(r'\s+', ' ', header.strip())
    for i, line in enumerate(lines):
        if re.sub(r'\s+', ' ', line.strip()) == header_text:
            start = i + 1
            end = None
            for j in range(start, len(lines)):
                if lines[j].strip() == "---":
                    end = j
                    break
                if lines[j].startswith("### ") or lines[j].startswith("## "):
                    end = j
                    break
            if end is None:
                end = len(lines)
            replace_start = start
            while replace_start < end and "<!--" in lines[replace_start]:
                comment_end = replace_start
                while comment_end < end and "-->" not in lines[comment_end]:
                    comment_end += 1
                if comment_end >= end:
                    break
                replace_start = comment_end + 1
            replacement = [""] + content_lines + [""]
            lines[replace_start:end] = replacement
            return True
    return False


def _append_to_section(lines: List[str], section_heading: str, content: str) -> bool:
    if not content:
        return False
    content_lines = [line.rstrip() for line in content.strip().splitlines()]
    for i, line in enumerate(lines):
        if line.strip() == section_heading.strip():
            insert_pos = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## ") and lines[j].strip() != section_heading.strip():
                    insert_pos = j
                    break
            lines[insert_pos:insert_pos] = [""] + content_lines + [""]
            return True
    return False


def _apply_integrated_sections(lines: List[str], integrated_content: str) -> None:
    normalized = integrated_content.strip().lower() if integrated_content else ""
    if not normalized or "no updates" in normalized or "no integrated sections" in normalized:
        return
    # Expected format per block:
    # - Question ID: Q-XXX
    # - Section: ## N. Section Title
    # <content to append>
    # The pattern captures the section heading and all following content until the
    # next Question ID/Section marker or end of the block.
    section_pattern = re.compile(
        r'- Question ID:[^\n]*\n- Section:\s*(.+?)\n(.*?)(?=\n\s*(?:- Question ID:|- Section:)|\Z)',
        re.DOTALL
    )
    matches = list(section_pattern.finditer(integrated_content))
    if not matches:
        print("WARNING: No integrated sections matched expected format.")
        return
    for match in matches:
        section_heading = match.group(1).strip()
        content = match.group(2).strip()
        _append_to_section(lines, section_heading, content)


# ---------- Patch Application ----------
def apply_patches(requirements: str, agent_output: str, mode: str) -> str:
    """Apply agent patches to the requirements document."""
    lines = requirements.splitlines()

    status_update = _extract_patch_section(agent_output, "STATUS_UPDATE")
    _update_status(lines, status_update)

    risks_content = _extract_patch_section(agent_output, "RISKS")
    if _should_apply_patch(risks_content, ("no risk changes", "no new risks", "no risk updates")):
        _replace_subsection(lines, "### Identified Risks", risks_content)

    questions_content = _extract_patch_section(agent_output, "OPEN_QUESTIONS")
    if _should_apply_patch(questions_content, ("no question changes", "no new questions")):
        _replace_subsection(lines, "### Open Questions", questions_content)

    if mode == "review":
        intake_clear = _extract_patch_section(agent_output, "INTAKE_CLEAR")
        if intake_clear:
            _replace_subsection(lines, "### Intake", INTAKE_PLACEHOLDER)
    else:
        integrated_content = _extract_patch_section(agent_output, "INTEGRATED_SECTIONS")
        _apply_integrated_sections(lines, integrated_content)

    return "\n".join(lines)

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(
        description="Invoke Requirements Agent to review or integrate answers"
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Disable automatic git commit"
    )
    args = parser.parse_args()
    
    # --- Pre-flight checks (fail fast on catastrophic errors) ---
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    if not REQ_FILE.exists():
        print(f"ERROR: Requirements file not found: {REQ_FILE}")
        sys.exit(1)
    
    if not AGENT_PROFILE.exists():
        print(f"ERROR: Agent profile not found: {AGENT_PROFILE}")
        sys.exit(1)

    try:
        subprocess.check_call(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        print("ERROR: git repository not available for commit operations")
        sys.exit(1)
    
    # --- Load document ---
    requirements = REQ_FILE.read_text(encoding="utf-8")
    agent_profile = AGENT_PROFILE.read_text(encoding="utf-8")

    # Determine mode
    mode = determine_mode(requirements)
    print(f"[Mode] Running in {mode} mode")
    
    # --- Get user context ---
    print("\nOptional context (Ctrl+D to finish):")
    user_context = sys.stdin.read().strip()
    
    # --- Invoke agent ---
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

CRITICAL: Output ONLY the structured patch format specified above.
DO NOT output the full requirements document.
Your output will be parsed and applied as patches.
"""
    
    print(f"\n[Agent] Calling {MODEL}...")
    
    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package not installed")
        print("Install with: pip install anthropic")
        sys.exit(1)
    
    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}]
    )
    
    agent_output = response.content[0].text
    
    # Validate output format (simple structural check)
    expected_marker = "## REVIEW_OUTPUT" if mode == "review" else "## INTEGRATION_OUTPUT"
    if expected_marker not in agent_output:
        print(f"\nERROR: Agent output missing {expected_marker}")
        print("Agent must output structured patches, not a full document.")
        sys.exit(1)
    
    print("✓ Agent output validated")
    
    # --- Apply patches ---
    print(f"\n[Patching] Applying {mode} patches...")
    updated_doc = apply_patches(requirements, agent_output, mode)

    missing_sections = missing_required_sections(updated_doc)
    if missing_sections:
        print("\nERROR: Missing required top-level sections:")
        for section in missing_sections:
            print(f"  - {section}")
        sys.exit(1)

    document_changed = updated_doc != requirements
    if document_changed:
        lines = updated_doc.splitlines()
        current_version = None
        for line in lines:
            if line.startswith("**Version:**"):
                current_version = line.split("**Version:**", 1)[1].strip()
                break
        if current_version:
            version_parts = current_version.split(".")
            try:
                version_parts[-1] = str(int(version_parts[-1]) + 1)
            except ValueError:
                version_parts[-1] = "1"
            new_version = ".".join(version_parts)
            for i, line in enumerate(lines):
                if line.startswith("**Version:**"):
                    lines[i] = f"**Version:** {new_version}"
                elif line.startswith("| Current Version |"):
                    lines[i] = f"| Current Version | {new_version} |"
            version_row = f"| {new_version} | {date.today().isoformat()} | Requirements Agent | Automated update |"
            for i, line in enumerate(lines):
                if line.strip() == "### Version History":
                    insert_at = None
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith("| Version |"):
                            insert_at = j + 2
                            break
                    if insert_at is not None:
                        while insert_at < len(lines) and lines[insert_at].startswith("|"):
                            insert_at += 1
                        lines.insert(insert_at, version_row)
                    break
            updated_doc = "\n".join(lines)

    # Write updated document
    REQ_FILE.write_text(updated_doc, encoding="utf-8")
    print("✓ Document updated")

    if not args.no_commit:
        diff_result = subprocess.run(
            ["git", "diff", "--quiet", "--", "docs/requirements.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        if diff_result.returncode == 0:
            print("\n[Commit] No changes detected; skipping commit")
        elif diff_result.returncode != 1:
            detail = diff_result.stderr.strip() or "git diff returned unexpected status"
            print(f"\n[Commit] Unable to determine git diff status: {detail}")
            sys.exit(1)
        else:
            print("\n[Commit] Staging requirements changes...")
            subprocess.check_call(
                ["git", "add", "docs/requirements.md"],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            commit_message = f"requirements: {mode} pass"
            subprocess.check_call(
                ["git", "commit", "-m", commit_message],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✓ Changes committed")
    else:
        print("\n--no-commit specified, skipping auto-commit")

    print(f"\n{mode.capitalize()} pass completed.")

if __name__ == "__main__":
    main()
