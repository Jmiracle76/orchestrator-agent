#!/usr/bin/env python3
"""
Minimal Deterministic Requirements Agent Invoker

This script is a thin, deterministic wrapper whose only job is lifecycle
gating and safety checks. All document understanding and repair is
delegated to the Requirements Agent.

Control flow:
1. Load document
2. Run minimal structural checks (file exists, valid format)
3. Invoke agent with full context
4. Apply returned changes
5. Exit

Responsibilities of this script (ONLY):
- Load requirements document
- Detect high-level document state (Template vs Active)
- Enforce lifecycle gates (e.g., Approved cannot be auto-set)
- Invoke the Requirements Agent
- Apply agent output to the document
- Fail fast on catastrophic errors (file missing, invalid format)

All semantic validation, schema repair, ghost question detection,
cross-reference checking, and human edit normalization belong to the agent.
"""

import os
import sys
import argparse
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# ---------- Configuration ----------
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = REPO_ROOT / "docs" / "requirements.md"
AGENT_PROFILE = REPO_ROOT / "agent-profiles" / "requirements-agent.md"
PLANNING_STATE_MARKER = REPO_ROOT / ".agent_state" / "requirements_approved"

# Regex pattern for detecting section boundaries (### with space or end of string)
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

# ---------- Intake Section Parsing ----------
def _parse_intake_section(content: str) -> str:
    """
    Parse and extract the Intake section content.
    
    Returns:
        The Intake section content (or empty string if none/empty)
    """
    # Find the Intake section
    intake_match = re.search(r'### Intake\n', content)
    if not intake_match:
        return ""
    
    start_pos = intake_match.end()
    
    # Find the end of the Intake section (next ### or ---)
    rest = content[start_pos:]
    
    # Skip comments at the beginning of the section
    while rest.startswith('<!--'):
        comment_end = rest.find('-->')
        if comment_end == -1:
            break
        rest = rest[comment_end + 3:].lstrip('\n')
        start_pos = start_pos + comment_end + 3
    
    # Find the end marker (next subsection or horizontal rule)
    end_pattern = r'\n---\n\n###'
    end_match = re.search(end_pattern, rest)
    if end_match:
        end_pos = end_match.start()
    else:
        # Fallback: next major section
        next_section = re.search(r'\n---\n\n## \d+\.', rest)
        end_pos = next_section.start() if next_section else len(rest)
    
    section_content = rest[:end_pos].strip()
    
    # Check if content is just the placeholder text
    if section_content.startswith('[Empty'):
        return ""
    
    return section_content


# ---------- Open Questions Parsing (Section-Based Format) ----------
def _parse_open_questions_section(content: str) -> List[Dict[str, str]]:
    """
    Parse section-based Open Questions format.
    
    Returns a list of question dictionaries with fields:
    - id: Question ID (e.g., "Q-001")
    - title: Question title
    - status: Status value (Open, Resolved, Deferred)
    - asked_by: Who asked the question
    - date: Date in YYYY-MM-DD format
    - question: The question text
    - answer: The answer text (may be empty)
    - targets: List of integration target strings
    """
    questions = []
    
    # Find the Open Questions section
    open_q_match = re.search(r'### Open Questions\n', content)
    if not open_q_match:
        return questions
    
    start_pos = open_q_match.end()
    
    # Find the end of the Open Questions section (comment block, not separator lines)
    rest = content[start_pos:]
    end_pattern = r'\n<!--\s*ANSWER INTEGRATION WORKFLOW'
    
    end_match = re.search(end_pattern, rest)
    if end_match:
        end_pos = end_match.start()
    else:
        # Fallback: next major section
        next_section = re.search(r'\n---\n\n## \d+\.', rest)
        end_pos = next_section.start() if next_section else len(rest)
    
    section_content = rest[:end_pos]
    
    # Find all question blocks using a simple approach
    # Each question starts with #### Q-XXX: and ends before the next #### or ---
    question_starts = [(m.start(), m.group()) for m in re.finditer(r'####\s+(Q-\d+):\s+(.+)', section_content)]
    
    for i, (start, heading_text) in enumerate(question_starts):
        # Find end of this question block
        if i + 1 < len(question_starts):
            end = question_starts[i + 1][0]
        else:
            end = len(section_content)
        
        # Extract the block
        block = section_content[start:end]
        
        # Parse heading
        heading_match = re.match(r'####\s+(Q-\d+):\s+(.+)', heading_text)
        if not heading_match:
            continue
        
        q_id = heading_match.group(1).strip()
        title = heading_match.group(2).strip()
        
        # Parse fields from block
        status_match = re.search(r'\*\*Status:\*\*\s+(.+?)\s*\n', block)
        asked_by_match = re.search(r'\*\*Asked by:\*\*\s+(.+?)\s*\n', block)
        date_match = re.search(r'\*\*Date:\*\*\s+(.+?)\s*\n', block)
        
        question_match = re.search(r'\*\*Question:\*\*\s*\n(.+?)\s*\n\*\*Answer:\*\*', block, re.DOTALL)
        answer_match = re.search(r'\*\*Answer:\*\*\s*\n(.+?)\s*\n\*\*Integration Targets:\*\*', block, re.DOTALL)
        targets_match = re.search(r'\*\*Integration Targets:\*\*\s*\n((?:- .+\n?)+)', block)
        
        if not all([status_match, asked_by_match, date_match, question_match, targets_match]):
            continue
        
        status = status_match.group(1).strip()
        asked_by = asked_by_match.group(1).strip()
        date = date_match.group(1).strip()
        question = question_match.group(1).strip()
        answer = answer_match.group(1).strip() if answer_match else ""
        targets_text = targets_match.group(1).strip()
        
        # Parse targets list
        targets = []
        for line in targets_text.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                target = line[2:].strip()
                if target:  # Only add non-empty targets
                    targets.append(target)
        
        questions.append({
            'id': q_id,
            'title': title,
            'status': status,
            'asked_by': asked_by,
            'date': date,
            'question': question,
            'answer': answer,
            'targets': targets
        })
    
    return questions


def _has_pending_answers(content: str) -> bool:
    """
    Check if there are answered questions pending integration.
    
    Returns True if any question has:
    - Non-empty Answer field
    - Status is not "Resolved"
    """
    questions = _parse_open_questions_section(content)
    
    for q in questions:
        answer = q['answer'].strip()
        status = q['status'].strip()
        
        # Has answer and not resolved
        if answer and not status.lower().startswith('resolved'):
            return True
    
    return False


# ---------- Git Helpers ----------
def git_status_porcelain() -> str:
    """Get git status in porcelain format."""
    return subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT
    ).decode()

def is_working_tree_clean() -> bool:
    """Check if git working tree is clean."""
    return not git_status_porcelain().strip()

def get_modified_files() -> list[str]:
    """Get list of modified files from git status."""
    status = git_status_porcelain()
    files = []
    for line in status.strip().splitlines():
        if line.strip():
            # Format: XY<space-or-tab>filename
            # Status is always 2 chars; skip them and strip whitespace
            rest = line[2:].strip()
            # Handle renames: "old -> new"
            if ' -> ' in rest:
                rest = rest.split(' -> ')[-1]
            # Normalize path separators
            filename = str(Path(rest).as_posix())
            files.append(filename)
    return files

def verify_only_requirements_modified() -> tuple[bool, str]:
    """
    Verify that only docs/requirements.md is modified.
    
    Returns:
        (is_valid, message)
    """
    modified = get_modified_files()
    
    print(f"\n[Commit Validation Debug]")
    print(f"  Modified files: {modified}")
    
    if not modified:
        return False, "No changes detected"
    
    # Normalize the expected path
    expected = "docs/requirements.md"
    print(f"  Allowed file: {expected}")
    
    # Check if all modified files are the requirements file
    unexpected = [f for f in modified if f != expected]
    
    if unexpected:
        return False, f"Unexpected files modified: {', '.join(unexpected)}"
    
    return True, f"Only expected file modified: {expected}"

def commit_changes(mode: str) -> bool:
    """
    Commit requirements.md changes.
    
    Args:
        mode: "review", "integrate", or "schema_repair"
    
    Returns:
        True if successful
    """
    try:
        # Stage the requirements file
        subprocess.check_call(
            ["git", "add", "docs/requirements.md"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Create commit message
        if mode == "integrate":
            msg = """requirements: integrate agent answers

- Integrated answers into existing sections
- Resolved answered open questions
- Updated revision history

Agent mode: integrate"""
        elif mode == "schema_repair":
            msg = """requirements: schema repair completed

- Restored missing required sections
- Added placeholder content for review
- Updated risks and open questions

Agent mode: schema_repair"""
        else:  # review
            msg = """requirements: review pass completed

- Reviewed document for quality and completeness
- Updated risks and open questions

Agent mode: review"""
        
        # Commit
        subprocess.check_call(
            ["git", "commit", "-m", msg],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Get commit hash
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT
        ).decode().strip()
        
        print(f"✓ Committed successfully: {commit_hash[:8]}")
        
        # Push to remote
        try:
            subprocess.check_call(
                ["git", "push"],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✓ Pushed to remote successfully")
        except subprocess.CalledProcessError as push_error:
            print(f"✗ Push failed: {push_error}")
            print("Changes are committed locally but not pushed to remote.")
            return False
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Commit failed: {e}")
        return False

# ---------- Version Detection ----------
def get_document_version(requirements: str) -> tuple[str, int, int]:
    """
    Extract document version from requirements.md.
    
    Returns:
        tuple: (version_string, major, minor)
        Returns ("0.0", 0, 0) if version cannot be parsed
    """
    version_match = re.search(r'\*\*Version:\*\*\s+([0-9.]+)', requirements)
    if not version_match:
        return ("0.0", 0, 0)
    
    version_str = version_match.group(1).strip()
    parts = version_str.split('.')
    
    try:
        major = int(parts[0]) if len(parts) >= 1 else 0
        minor = int(parts[1]) if len(parts) >= 2 else 0
        return (version_str, major, minor)
    except (ValueError, IndexError):
        return ("0.0", 0, 0)

def is_template_baseline(requirements: str) -> bool:
    """
    Check if document is a template baseline (version 0.0).
    
    Template baselines have special safeguards:
    - Content sections (2-14) are read-only
    - Placeholders must not be altered
    - No approval recommendations allowed
    
    Returns:
        True if version is 0.0
    """
    _, major, minor = get_document_version(requirements)
    return major == 0 and minor == 0

# ---------- Mode Determination ----------
def determine_mode(requirements: str) -> str:
    """
    Determine execution mode: integrate if there are pending answers, else review.
    
    Template baseline documents (version 0.0) always run in review mode with
    special safeguards that prevent modification of content sections.
    """
    # Template baselines (version 0.0) can only be reviewed, never integrated
    if is_template_baseline(requirements):
        return "review"
    
    return "integrate" if _has_pending_answers(requirements) else "review"

# ---------- Approval Detection & State Recording ----------
def is_requirements_approved(requirements: str) -> bool:
    """
    Detect if requirements are approved by checking for explicit approval marker.
    
    Returns True if "Approval Record" section contains "Current Status" field set to "Approved".
    """
    # Find Approval Record section and check for approval on same line
    approval_section_match = re.search(r'## 15\. Approval Record.*?(?=## \d+\.|$)', requirements, re.DOTALL)
    if approval_section_match:
        section_text = approval_section_match.group()
        # Check for both terms appearing on the same line or in table format
        return bool(re.search(r'Current Status.*Approved|Approved.*Current Status', section_text))
    return False

def has_planning_been_triggered() -> bool:
    """
    Check if planning agent has already been triggered.
    
    Returns True if the state marker file exists.
    """
    return PLANNING_STATE_MARKER.exists()

def create_planning_state_marker() -> None:
    """
    Create the planning state marker file to record handoff readiness.
    """
    # Ensure the .agent_state directory exists
    PLANNING_STATE_MARKER.parent.mkdir(parents=True, exist_ok=True)
    
    # Write marker with timestamp
    timestamp = datetime.now().isoformat()
    PLANNING_STATE_MARKER.write_text(
        f"Requirements approved and ready for planning handoff at {timestamp}\n",
        encoding="utf-8"
    )

def commit_planning_marker() -> bool:
    """
    Commit the planning state marker to git.
    
    Returns True if successful.
    """
    try:
        # Stage the marker file
        subprocess.check_call(
            ["git", "add", ".agent_state/requirements_approved"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Commit
        msg = "agent-state: requirements approved, ready for planning handoff"
        subprocess.check_call(
            ["git", "commit", "-m", msg],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Get commit hash
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT
        ).decode().strip()
        
        print(f"✓ State marker committed: {commit_hash[:8]}")
        
        # Push to remote
        try:
            subprocess.check_call(
                ["git", "push"],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✓ State marker pushed to remote")
        except subprocess.CalledProcessError as push_error:
            print(f"✗ Push failed: {push_error}")
            print("State marker is committed locally but not pushed to remote.")
            return False
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ State marker commit failed: {e}")
        return False

def revoke_approval_state() -> bool:
    """
    Revoke approval by deleting the planning state marker file.
    
    Returns True if the marker was deleted (existed and was removed).
    Returns False if the marker didn't exist.
    """
    if PLANNING_STATE_MARKER.exists():
        PLANNING_STATE_MARKER.unlink()
        return True
    return False

def update_approval_status_to_pending(requirements: str) -> str:
    """
    Update the Approval Status field in requirements.md to "Pending - Revisions Required".
    
    This is used when new human input (Intake content) invalidates previous approval.
    
    Returns the updated requirements document text.
    """
    lines = requirements.splitlines(keepends=True)
    
    # Find and update the Approval Status field in Document Control table
    for i, line in enumerate(lines):
        if '| Approval Status |' in line:
            # Preserve original line ending
            line_ending = '\n' if line.endswith('\n') else ''
            lines[i] = f'| Approval Status | Pending - Revisions Required |{line_ending}'
            break
    
    return ''.join(lines)

def revoke_approval_and_commit(requirements: str, reason: str, commit_message: str) -> str:
    """
    Revoke approval by updating the document and deleting the state marker.
    
    This function:
    1. Updates approval status to "Pending - Revisions Required"
    2. Writes updated document to disk
    3. Deletes planning state marker if it exists
    4. Commits changes to git
    5. Rolls back all changes if commit fails
    
    Args:
        requirements: The current requirements document text
        reason: Human-readable reason for revocation (for logging)
        commit_message: Git commit message
    
    Returns:
        The updated requirements document text (re-read from disk after commit)
    """
    print(f"  ⚠️  Requirements were previously approved")
    print(f"  → Revoking approval due to {reason}")
    
    # Update approval status in document to "Pending"
    updated_requirements = update_approval_status_to_pending(requirements)
    REQ_FILE.write_text(updated_requirements, encoding="utf-8")
    print("  ✓ Approval status updated to 'Pending - Revisions Required'")
    
    # Prepare git operations
    git_add_commands = [
        ["git", "add", str(REQ_FILE)]
    ]
    
    # Delete planning state marker if it exists (save original content for rollback)
    marker_original_content = None
    if PLANNING_STATE_MARKER.exists():
        marker_original_content = PLANNING_STATE_MARKER.read_text(encoding="utf-8")
    
    marker_deleted = revoke_approval_state()
    if marker_deleted:
        print("  ✓ Planning state marker deleted")
        git_add_commands.append(["git", "add", "-u", ".agent_state/"])
    
    # Commit the revocation
    try:
        for cmd in git_add_commands:
            subprocess.check_call(
                cmd,
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        # Check if there are actually changes to commit
        status = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=REPO_ROOT
        ).decode().strip()
        
        if status:
            subprocess.check_call(
                ["git", "commit", "-m", commit_message],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("  ✓ Approval revocation committed")
        else:
            print("  ℹ️  No changes to commit (approval already pending)")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to commit revocation: {e}")
        # Rollback: revert document changes
        REQ_FILE.write_text(requirements, encoding="utf-8")
        print("  → Reverted document changes due to commit failure")
        # Rollback: restore marker if it was deleted
        if marker_deleted and marker_original_content is not None:
            PLANNING_STATE_MARKER.parent.mkdir(parents=True, exist_ok=True)
            PLANNING_STATE_MARKER.write_text(marker_original_content, encoding="utf-8")
            print("  → Restored planning state marker")
        return requirements
    
    # Re-read requirements after successful commit
    return REQ_FILE.read_text(encoding="utf-8")

# ---------- Agent Instructions ----------
def get_agent_instructions(mode: str, is_template: bool, intake_content: str = "") -> str:
    """
    Get mode-specific instructions for the agent.
    
    Args:
        mode: "review" or "integrate"
        is_template: True if document is version 0.0 (template baseline)
        intake_content: Content from the Intake section (if any)
    """
    intake_notice = ""
    if intake_content:
        intake_notice = f"""
⚠️  INTAKE SECTION HAS CONTENT ⚠️

The following unstructured notes were found in the Intake section:
---
{intake_content}
---

You MUST:
1. Read and analyze these notes for ambiguities, questions, or concerns
2. Convert them into formal Open Questions in the Open Questions section
3. Clear the Intake section after processing (replace with placeholder text)
4. NEVER integrate raw Intake text directly into content sections

After processing, the Intake section should contain only:
[Empty - Add your unstructured notes, questions, or thoughts here. They will be converted to formal Open Questions by the Requirements Agent.]

"""
    
    template_warning = ""
    if is_template:
        template_warning = """
⚠️  TEMPLATE BASELINE DETECTED (Version 0.0) ⚠️

This is a template baseline document. Special safeguards apply:
- Content sections (Sections 2-14) are READ-ONLY
- DO NOT modify, delete, or alter placeholder text in these sections
- DO NOT recommend "Ready for Approval" (templates cannot be approved)
- You may ONLY modify: Intake, Risks, Open Questions, and Status fields
- Template baselines require human engagement before approval is possible

"""
    
    schema_repair_notice = """
SCHEMA AND CONSISTENCY RESPONSIBILITIES:

You own all document understanding and repair. You MUST:
1. Detect and repair missing or malformed sections
2. Detect ghost question references (Q-IDs referenced but not defined) and create entries for them
3. Validate cross-references between Risks and Open Questions
4. Ensure internal consistency across all sections
5. Maintain canonical formatting for all sections

If you find structural issues, repair them in your output.
Do NOT create Risks that reference non-existent Open Questions.
Every Q-ID referenced anywhere in the document MUST have a canonical Open Questions entry.
"""
    
    if mode == "review":
        intake_instructions = ""
        if intake_content:
            intake_instructions = """
- Process Intake section: Convert unstructured notes into formal Open Questions
- Clear the Intake section after processing
"""
        return f"""{intake_notice}{template_warning}{schema_repair_notice}MODE: review

In review mode, you MUST output ONLY structured patches (NOT a full document).

You may:
- Review document quality and completeness
- Identify new risks to add
- Identify new open questions{intake_instructions}
- Repair missing sections or malformed content
- Recommend approval status{' (BUT NOT for template baselines - version 0.0)' if is_template else ''}

OUTPUT FORMAT (required):

## REVIEW_OUTPUT

### STATUS_UPDATE
[Your status recommendation: {"'Pending - Revisions Required' ONLY (templates cannot be approved)" if is_template else '"Ready for Approval" or "Pending - Revisions Required"'}]
[Specific reasons]

### RISKS
[New risk entries, or "No new risks identified"]

### OPEN_QUESTIONS
[New question subsections in section-based format, or "No new questions"]

For each new question, use this format:
#### Q-XXX: [Question Title]

**Status:** Open  
**Asked by:** Requirements Agent  
**Date:** [YYYY-MM-DD]  

**Question:**  
[The question text]

**Answer:**  


**Integration Targets:**  
- [Target section]

{"### INTAKE_CLEAR" if intake_content else ""}
{"[Clear the Intake section and replace with: '[Empty - Add your unstructured notes, questions, or thoughts here. They will be converted to formal Open Questions by the Requirements Agent.]']" if intake_content else ""}

DO NOT output the full document.
"""
    else:  # integrate
        return f"""{schema_repair_notice}MODE: integrate

In integrate mode, you MUST output ONLY structured patches (NOT a full document).

You must:
1. Find Open Questions subsections with non-empty Answer fields and Status not "Resolved"
2. Integrate each answer into the appropriate section specified in Integration Targets
3. Update risks based on integrated answers
4. Recommend approval status

CRITICAL: Do NOT mark questions as "Resolved". Resolution status is derived mechanically by the 
invocation script based on whether all Integration Targets were successfully updated.

OUTPUT FORMAT (required):

## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
For each question being integrated, list:
- Question ID: <Q-XXX>
- Section: <exact section heading, e.g., "## 8. Functional Requirements">
<content to append, with source traceability>

### RISKS
<Updated risk entries, or "No risk changes">

### STATUS_UPDATE
<Your status recommendation with reasons>

DO NOT output the full document.
DO NOT include a RESOLVED_QUESTIONS section - resolution is derived automatically.
"""

# ---------- Patch Application Helpers ----------
def _update_approval_status(lines: list, status_update: str) -> None:
    """Helper to update approval status in document lines."""
    if not status_update or "No changes" in status_update:
        return
    
    for i, line in enumerate(lines):
        if '| Approval Status |' in line:
            if 'Ready for Approval' in status_update:
                lines[i] = '| Approval Status | Ready for Approval |'
            elif 'Pending' in status_update:
                lines[i] = '| Approval Status | Pending - Revisions Required |'
            break

# ---------- Placeholder Cleanup ----------
def _cleanup_template_placeholders(lines: list) -> None:
    """
    Clean up template baseline placeholders after transitioning to active document (0.0 -> 0.1+).
    
    This function:
    - Removes placeholder text like [Date], [Author], etc. from content sections
    - Removes duplicated scaffolding (redundant template examples)
    - Preserves document structure
    - EXCLUDES Open Questions section (brackets are intentional there)
    
    Called once and only once during the 0.0 -> 0.1+ version transition.
    """
    # Identify line ranges for content sections 2-14 (not section 1 or 15)
    # But EXCLUDE the Open Questions subsection within section 12
    section_ranges = []
    current_section = None
    current_start = None
    in_open_questions = False
    
    for i, line in enumerate(lines):
        # Check if we're entering Open Questions subsection
        if '### Open Questions' in line:
            # Save section up to this point if it was in range 2-14
            if current_section is not None and 2 <= current_section <= 14 and current_start is not None:
                section_ranges.append((current_start, i))
            in_open_questions = True
            current_start = None
            continue
        
        # Check if we're exiting Open Questions subsection (next ### or ##)
        if in_open_questions and (line.strip().startswith('###') or line.strip().startswith('##')):
            in_open_questions = False
            # If this is still in section 12 or another section 2-14, start tracking again
            section_match = re.match(r'##\s+(\d+)\.\s+', line)
            if section_match:
                section_num = int(section_match.group(1))
                if 2 <= section_num <= 14:
                    current_section = section_num
                    current_start = i
            elif line.strip().startswith('###') and current_section is not None and 2 <= current_section <= 14:
                # Subsection within same parent section
                current_start = i
            continue
        
        # Detect section headers like "## 2. Problem Statement"
        section_match = re.match(r'##\s+(\d+)\.\s+', line)
        if section_match:
            section_num = int(section_match.group(1))
            
            # Save previous section if it was in range 2-14
            if current_section is not None and 2 <= current_section <= 14 and current_start is not None and not in_open_questions:
                section_ranges.append((current_start, i))
            
            # Start tracking new section if in range 2-14
            if 2 <= section_num <= 14 and not in_open_questions:
                current_section = section_num
                current_start = i
            else:
                current_section = None
                current_start = None
    
    # Handle last section if it was in range 2-14 and not in Open Questions
    if current_section is not None and 2 <= current_section <= 14 and current_start is not None and not in_open_questions:
        section_ranges.append((current_start, len(lines)))
    
    # Clean up placeholders in identified sections
    # Use a more generic pattern that matches anything in square brackets
    placeholder_pattern = r'\[([^\]]+)\]'
    
    for start, end in section_ranges:
        for i in range(start, end):
            # Remove all square bracket placeholders from this line
            if re.search(placeholder_pattern, lines[i]):
                lines[i] = re.sub(placeholder_pattern, '', lines[i])
    
    # Remove lines that become empty or only whitespace after cleanup
    # But preserve structural elements (headers, separators, list markers)
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # Remove lines that are now empty or only contain punctuation/whitespace
        # But keep section headers, list markers, separators
        if stripped and not stripped.startswith('#') and not stripped.startswith('-') and not stripped.startswith('*'):
            # Check if line is effectively empty after placeholder removal
            # (e.g., "Version: " with nothing after colon)
            if re.match(r'^[:\s|]*$', stripped):
                lines.pop(i)
                continue
        i += 1
    
    # Remove duplicated scaffolding: look for commented example blocks and remove them
    # These are typically marked with <!-- Example --> or similar
    i = 0
    in_example_block = False
    example_start = -1
    
    while i < len(lines):
        if '<!-- Example' in lines[i] or '<!-- Template' in lines[i]:
            in_example_block = True
            example_start = i
        elif in_example_block and '-->' in lines[i]:
            # Remove the entire example block
            if example_start >= 0:
                # Delete from example_start to i (inclusive)
                del lines[example_start:i+1]
                i = example_start
                in_example_block = False
                example_start = -1
                continue
        i += 1

# ---------- Patch Application ----------
def apply_patches(requirements: str, agent_output: str, mode: str) -> tuple[str, dict]:
    """
    Apply agent patches to requirements document.
    
    This is a simplified version that:
    1. Extracts patch sections from agent output
    2. Updates corresponding document sections
    3. Updates revision history
    4. (For integrate mode) Derives resolution status based on successful target integration
    
    Returns:
        tuple: (updated_document, integration_info)
        integration_info is a dict with keys:
            - 'resolved': list of question IDs that were resolved
            - 'unresolved': dict mapping question IDs to list of failed targets
    """
    lines = requirements.split('\n')
    integration_info = {'resolved': [], 'unresolved': {}}
    
    if mode == "review":
        # Extract review patches
        # Note: Use word boundary or space after ### to avoid matching #### headers
        status_match = re.search(rf'### STATUS_UPDATE\s*\n(.*?){SECTION_BOUNDARY_PATTERN}', agent_output, re.DOTALL)
        risks_match = re.search(rf'### RISKS\s*\n(.*?){SECTION_BOUNDARY_PATTERN}', agent_output, re.DOTALL)
        questions_match = re.search(rf'### OPEN_QUESTIONS\s*\n(.*?){SECTION_BOUNDARY_PATTERN}', agent_output, re.DOTALL)
        intake_clear_match = re.search(rf'### INTAKE_CLEAR\s*\n(.*?){SECTION_BOUNDARY_PATTERN}', agent_output, re.DOTALL)
        
        status_update = status_match.group(1).strip() if status_match else ""
        risks_content = risks_match.group(1).strip() if risks_match else ""
        questions_content = questions_match.group(1).strip() if questions_match else ""
        intake_clear = intake_clear_match.group(1).strip() if intake_clear_match else ""
        
        # Update approval status if provided
        _update_approval_status(lines, status_update)
        
        # Clear Intake section if requested
        if intake_clear or "INTAKE_CLEAR" in agent_output:
            for i, line in enumerate(lines):
                if '### Intake' in line:
                    # Find the end of the Intake section
                    start_pos = i
                    end_pos = None
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith('---') and j + 2 < len(lines) and '###' in lines[j + 2]:
                            end_pos = j
                            break
                    
                    if end_pos:
                        # Replace content between header and separator with placeholder
                        placeholder = "\n[Empty - Add your unstructured notes, questions, or thoughts here. They will be converted to formal Open Questions by the Requirements Agent.]\n"
                        # Find where comments end
                        comment_end = start_pos + 1
                        while comment_end < end_pos:
                            stripped_line = lines[comment_end].strip()
                            if not stripped_line.startswith('<!--') and not stripped_line.startswith('-->') and '-->' not in stripped_line:
                                break
                            comment_end += 1
                        
                        # Delete content between comment_end and end_pos
                        del lines[comment_end:end_pos]
                        # Insert placeholder
                        lines.insert(comment_end, placeholder)
                    break
        
        # Append new risks
        if risks_content and "No new risks" not in risks_content:
            for i, line in enumerate(lines):
                if '### Risks' in line or '### Identified Risks' in line:
                    # Find next section heading and insert before it
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith('###'):
                            lines.insert(j, "\n" + risks_content + "\n")
                            break
                    break
        
        # Append new questions (section-based format)
        if questions_content and "No new questions" not in questions_content:
            # Validate that new questions don't have duplicate IDs
            existing_q_ids = {m.group(1) for m in re.finditer(r'####\s+(Q-\d+):', '\n'.join(lines))}
            
            # Extract Q-IDs from new questions
            new_q_ids = set(re.findall(r'####\s+(Q-\d+):', questions_content))
            
            # Check for conflicts
            duplicate_ids = new_q_ids & existing_q_ids
            if duplicate_ids:
                dup_list = ", ".join(sorted(duplicate_ids))
                print(f"WARNING: Agent attempted to create duplicate Question IDs: {dup_list}")
                print("Skipping duplicate questions to maintain canonical ownership.")
                # Filter out duplicate questions from questions_content
                filtered_questions = []
                for q_block in re.split(r'(?=####\s+Q-\d+:)', questions_content):
                    q_id_match = re.match(r'####\s+(Q-\d+):', q_block)
                    if q_id_match:
                        q_id = q_id_match.group(1)
                        if q_id not in duplicate_ids:
                            filtered_questions.append(q_block)
                    elif q_block.strip():  # Non-empty content without Q-ID header
                        filtered_questions.append(q_block)
                
                questions_content = '\n'.join(filtered_questions).strip()
            
            # Only append if there's content after filtering
            if questions_content:
                for i, line in enumerate(lines):
                    if '### Open Questions' in line:
                        # Find the comment block after questions
                        # Comment can be multiline, so search for "ANSWER INTEGRATION WORKFLOW"
                        # anywhere in the next few lines after finding <!--
                        for j in range(i + 1, len(lines)):
                            # Check if this line or nearby lines contain the comment
                            if 'ANSWER INTEGRATION WORKFLOW' in lines[j]:
                                # Insert before this line (or before the opening <!--)
                                # Search backwards to find the opening <!--
                                insert_pos = j
                                for k in range(j - 1, i, -1):
                                    if '<!--' in lines[k]:
                                        insert_pos = k
                                        break
                                lines.insert(insert_pos, "\n" + questions_content + "\n")
                                break
                        break
    
    else:  # integrate mode
        # Extract integration patches
        # Note: Use consistent section boundary patterns
        integrated_match = re.search(
            rf'### INTEGRATED_SECTIONS\s*\n(.*?){SECTION_BOUNDARY_PATTERN}',
            agent_output, re.DOTALL
        )
        risks_match = re.search(
            rf'### RISKS\s*\n(.*?){SECTION_BOUNDARY_PATTERN}',
            agent_output, re.DOTALL
        )
        status_match = re.search(
            rf'### STATUS_UPDATE\s*\n(.*?){SECTION_BOUNDARY_PATTERN}',
            agent_output, re.DOTALL
        )
        
        integrated_content = integrated_match.group(1).strip() if integrated_match else ""
        risks_content = risks_match.group(1).strip() if risks_match else ""
        status_update = status_match.group(1).strip() if status_match else ""
        
        # Track which questions had their targets successfully integrated
        # Map: {question_id: {target_section: was_integrated}}
        integration_tracking = {}
        
        # Parse all questions to get their integration targets
        questions = _parse_open_questions_section('\n'.join(lines))
        for q in questions:
            if q['answer'].strip() and not q['status'].lower().startswith('resolved'):
                # Initialize tracking for this question
                integration_tracking[q['id']] = {target: False for target in q['targets']}
        
        # Apply integrated sections and track successful integrations
        if integrated_content:
            # Parse section updates with question IDs
            # Updated pattern to match: "- Question ID: Q-XXX\n- Section: ..."
            section_pattern = re.compile(
                r'- Question ID:\s*(Q-\d+)\s*\n- Section:\s*(.+?)\n(.*?)(?=\n- Question ID:|\Z)',
                re.DOTALL
            )
            for match in section_pattern.finditer(integrated_content):
                q_id = match.group(1).strip()
                section_heading = match.group(2).strip()
                content = match.group(3).strip()
                
                # Find section in document and append content
                section_found = False
                for i, line in enumerate(lines):
                    if section_heading in line:
                        # Find next section
                        for j in range(i + 1, len(lines)):
                            if lines[j].strip().startswith('##') and lines[j].strip() != section_heading:
                                lines.insert(j, "\n" + content + "\n")
                                section_found = True
                                break
                        break
                
                # Mark this target as integrated if successful
                if section_found and q_id in integration_tracking:
                    # Match the target by checking if the section heading appears in any target
                    # The section heading from agent is "## 8. Functional Requirements"
                    # The target is "Section 8: Functional Requirements"
                    # Extract section number and name for precise matching
                    
                    # Parse section heading: "## 8. Functional Requirements" -> section_num=8, name="Functional Requirements"
                    heading_match = re.match(r'##\s*(\d+)\.\s*(.+)', section_heading)
                    if heading_match:
                        heading_num = heading_match.group(1)
                        heading_name = heading_match.group(2).strip()
                        
                        for target in integration_tracking[q_id]:
                            # Parse target: "Section 8: Functional Requirements" -> section_num=8, name="Functional Requirements"
                            target_match = re.match(r'Section\s+(\d+)[:.]\s*(.+)', target, re.IGNORECASE)
                            if target_match:
                                target_num = target_match.group(1)
                                target_name = target_match.group(2).strip()
                                
                                # Match if section numbers are the same and names match (case-insensitive)
                                if heading_num == target_num and heading_name.lower() == target_name.lower():
                                    integration_tracking[q_id][target] = True
                                    break
        
        # Derive resolution status: mark questions as resolved ONLY if all targets were integrated
        for q_id, targets in integration_tracking.items():
            if all(targets.values()) and len(targets) > 0:
                # All targets were successfully integrated - mark as Resolved
                integration_info['resolved'].append(q_id)
                for i, line in enumerate(lines):
                    if line.strip().startswith(f'#### {q_id}:'):
                        # Find the Status line in the next few lines
                        for j in range(i + 1, min(i + 10, len(lines))):
                            if '**Status:**' in lines[j]:
                                # Update status to Resolved
                                # Match "**Status:** <anything>" and replace with "**Status:** Resolved"
                                # Use .*? to match the entire status value, then $ to match end of line
                                lines[j] = re.sub(r'\*\*Status:\*\*\s+.*?$', '**Status:** Resolved', lines[j].rstrip())
                                break
                        break
            else:
                # Not all targets were integrated - track failed targets
                failed_targets = [t for t, integrated in targets.items() if not integrated]
                if failed_targets:
                    integration_info['unresolved'][q_id] = failed_targets
        
        # Update risks
        if risks_content and "No risk changes" not in risks_content:
            for i, line in enumerate(lines):
                if '### Risks' in line or '### Identified Risks' in line:
                    # Find next section heading and insert before it
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith('###'):
                            lines.insert(j, "\n" + risks_content + "\n")
                            break
                    break
        
        # Update approval status
        _update_approval_status(lines, status_update)
    
    # Add revision history entry (simplified version increment)
    # Detect version transition from 0.0 → 0.1+ for placeholder cleanup
    today = datetime.now().strftime("%Y-%m-%d")
    change_desc = f"{mode.capitalize()} pass by Requirements Agent"
    version_to_use = "0.1"  # Default fallback if no previous version found
    previous_version = "0.0"  # Track previous version for transition detection
    
    for i, line in enumerate(lines):
        if '### Version History' in line:
            # Find first data row to get current version and insert new entry
            for j in range(i + 1, len(lines)):
                if '|---' in lines[j]:
                    continue
                # Skip header row (contains "Version | Date | Author | Changes")
                if 'Version' in lines[j] and 'Date' in lines[j] and 'Author' in lines[j]:
                    continue
                if lines[j].strip().startswith('|') and lines[j].count('|') >= 4:
                    parts = lines[j].split('|')
                    if len(parts) >= 2:
                        prev_ver = parts[1].strip()
                        previous_version = prev_ver  # Track for transition detection
                        # Simple increment: if it's "X.Y", make it "X.Y+1"
                        try:
                            if '.' in prev_ver and prev_ver.count('.') == 1:
                                major, minor = prev_ver.split('.')
                                version_to_use = f"{major}.{int(minor) + 1}"
                        except (ValueError, IndexError):
                            pass
                    lines.insert(j, f"| {version_to_use} | {today} | Requirements Agent | {change_desc} |")
                    break
            break
    
    # Detect template baseline -> active document transition (0.0 -> 0.1+)
    # This is the ONE-TIME placeholder cleanup trigger
    is_version_transition = (previous_version == "0.0" and version_to_use != "0.0")
    
    if is_version_transition:
        print(f"\n[Version Transition] Detected 0.0 -> {version_to_use} transition")
        print("  -> Cleaning up template placeholders (one-time operation)")
        _cleanup_template_placeholders(lines)
        print("  ✓ Placeholder cleanup complete")
    
    # Update Document Control table fields atomically
    # Track which fields have been updated to avoid redundant iterations
    fields_updated = 0
    for i, line in enumerate(lines):
        if '| Current Version |' in line:
            lines[i] = f'| Current Version | {version_to_use} |'
            fields_updated += 1
        elif '| Last Modified |' in line:
            lines[i] = f'| Last Modified | {today} |'
            fields_updated += 1
        elif '| Modified By |' in line:
            lines[i] = f'| Modified By | Requirements Agent |'
            fields_updated += 1
        # Break early if all three fields have been found and updated
        if fields_updated >= 3:
            break
    
    # Update header version field
    for i, line in enumerate(lines):
        if line.startswith('**Version:**'):
            lines[i] = f'**Version:** {version_to_use}'
            break
    
    return '\n'.join(lines), integration_info

# ---------- Reset Function ----------
def reset_requirements_document():
    """
    Destructive reset of requirements document to canonical template.
    
    This function:
    - Replaces the entire requirements document with CANONICAL_TEMPLATE
    - Discards all existing content (requirements, questions, risks, etc.)
    - Resets version to 0.0 and status to Draft
    - Is idempotent (multiple runs produce same result)
    
    This is a deliberate, destructive operation and must be explicitly requested.
    """
    print("\n" + "=" * 70)
    print("WARNING: DESTRUCTIVE OPERATION")
    print("=" * 70)
    print("\nYou are about to RESET the requirements document to the canonical template.")
    print("\nThis operation will:")
    print("  - REPLACE the entire requirements document")
    print("  - DISCARD all existing content")
    print("  - ERASE all requirements, questions, risks, and version history")
    print("  - RESET version to 0.0 and status to Draft")
    print("\nThis action CANNOT be undone without git revert.")
    print("=" * 70)
    
    # Require explicit confirmation
    print("\nType 'RESET' (all caps) to confirm: ", end="")
    confirmation = input().strip()
    
    if confirmation != "RESET":
        print("\nReset cancelled. No changes made.")
        sys.exit(0)
    
    print("\n[Reset] Replacing requirements document with canonical template...")
    
    # Replace document with canonical template
    REQ_FILE.write_text(CANONICAL_TEMPLATE, encoding="utf-8")
    
    print("✓ Requirements document reset to canonical template")
    print(f"✓ Document location: {REQ_FILE}")
    print(f"✓ Version: 0.0")
    print(f"✓ Status: Draft")
    
    # Verify the reset was successful by checking version
    reset_content = REQ_FILE.read_text(encoding="utf-8")
    if "**Version:** 0.0" in reset_content and "| 0.0 |" in reset_content:
        print("\n✓ Reset verification passed - document is at template baseline")
    else:
        print("\n⚠️  Warning: Reset may be incomplete - verification failed")
        sys.exit(1)
    
    print("\n[Next Steps]")
    print("1. Review the reset document: cat docs/requirements.md")
    print("2. Commit the reset: git add docs/requirements.md && git commit -m 'Reset requirements to canonical template'")
    print("3. Begin requirements development with clean baseline")

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
    parser.add_argument(
        "--reset-template",
        action="store_true",
        help="DESTRUCTIVE: Reset requirements document to canonical template baseline. Discards all existing content."
    )
    args = parser.parse_args()
    
    # Handle reset mode - this happens BEFORE any other checks
    if args.reset_template:
        reset_requirements_document()
        sys.exit(0)
    
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
    
    print("\n[Pre-flight] Checking git status...")
    if not is_working_tree_clean():
        print("ERROR: Working tree has uncommitted changes")
        print("Please commit or stash changes before running.")
        print("\nCurrent status:")
        print(git_status_porcelain())
        sys.exit(1)
    print("✓ Working tree is clean")
    
    # --- Load document ---
    requirements = REQ_FILE.read_text(encoding="utf-8")
    agent_profile = AGENT_PROFILE.read_text(encoding="utf-8")
    
    # --- Detect high-level document state ---
    version_str, major, minor = get_document_version(requirements)
    is_template = is_template_baseline(requirements)
    print(f"\n[State] Document version: {version_str}")
    if is_template:
        print("  ⚠️  Template baseline detected - special safeguards active")
    
    # Parse Intake section (needed for agent context)
    intake_content = _parse_intake_section(requirements)
    if intake_content:
        print(f"✓ Found Intake content ({len(intake_content)} chars)")
    
    # Determine mode
    mode = determine_mode(requirements)
    print(f"[Mode] Running in {mode} mode")
    
    # --- Enforce lifecycle gate: revoke approval on new input ---
    if intake_content or _has_pending_answers(requirements):
        if is_requirements_approved(requirements):
            reason = "new human input" if intake_content else "answered questions pending integration"
            requirements = revoke_approval_and_commit(
                requirements, reason, f"revoke: {reason}"
            )
    
    # --- Get user context ---
    print("\nOptional context (Ctrl+D to finish):")
    user_context = sys.stdin.read().strip()
    
    # --- Invoke agent ---
    instructions = get_agent_instructions(mode, is_template, intake_content)
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
    updated_doc, integration_info = apply_patches(requirements, agent_output, mode)
    
    # Log integration resolution results (integrate mode only)
    if mode == "integrate":
        if integration_info['resolved']:
            print(f"\n[Resolution] Questions resolved (all targets integrated):")
            for q_id in integration_info['resolved']:
                print(f"  ✓ {q_id}")
        if integration_info['unresolved']:
            print(f"\n[Resolution] Questions NOT resolved (missing targets):")
            for q_id, failed_targets in integration_info['unresolved'].items():
                print(f"  ✗ {q_id}: Failed to integrate into {', '.join(failed_targets)}")
    
    # Write updated document
    REQ_FILE.write_text(updated_doc, encoding="utf-8")
    print("✓ Document updated")
    
    # --- Auto-commit ---
    if not args.no_commit:
        print("\n[Commit] Checking for changes to commit...")
        is_valid, msg = verify_only_requirements_modified()
        
        if is_valid:
            print(f"✓ {msg}")
            if commit_changes(mode):
                print("✓ Changes committed to main")
            else:
                print("✗ Commit failed")
        else:
            print(f"✗ {msg}")
            print("Skipping auto-commit")
    else:
        print("\n--no-commit specified, skipping auto-commit")
    
    print(f"\n{mode.capitalize()} pass completed.")
    
    # --- Check for approval and record state transition ---
    requirements = REQ_FILE.read_text(encoding="utf-8")
    
    if is_requirements_approved(requirements):
        print("\n[Approval] Requirements document is APPROVED")
        
        if has_planning_been_triggered():
            print("✓ Planning handoff already recorded (marker exists)")
            print(f"  Marker: {PLANNING_STATE_MARKER.relative_to(REPO_ROOT)}")
        else:
            print("→ First-time approval detected. Recording planning handoff readiness...")
            
            create_planning_state_marker()
            print(f"✓ Created state marker: {PLANNING_STATE_MARKER.relative_to(REPO_ROOT)}")
            
            if commit_planning_marker():
                print("\n" + "=" * 60)
                print("PLANNING HANDOFF READY")
                print("=" * 60)
                print("\nRequirements are approved and marker has been recorded.")
                print("A separate orchestrator or planning script can now proceed.")
            else:
                print("\n✗ Failed to commit state marker.")
                sys.exit(1)
    else:
        print("\n[Approval] Requirements not yet approved. No handoff recorded.")

if __name__ == "__main__":
    main()
