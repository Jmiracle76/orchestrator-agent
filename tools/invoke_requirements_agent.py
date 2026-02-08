#!/usr/bin/env python3
"""
Simplified Requirements Agent Invoker

This script invokes an AI agent to review or integrate changes into requirements.md.
It relies on Git as the primary safety mechanism rather than complex internal validation.

Key principles:
- Linear, readable control flow
- Minimal validation (only what prevents corruption)
- Git is the safety net
- Auto-commit on any document change
- State-based handoff: Records approval state for future orchestration
"""

import os
import sys
import argparse
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# ---------- Configuration ----------
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = REPO_ROOT / "docs" / "requirements.md"
AGENT_PROFILE = REPO_ROOT / "agent-profiles" / "requirements-agent.md"
PLANNING_STATE_MARKER = REPO_ROOT / ".agent_state" / "requirements_approved"

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
        mode: "review" or "integrate"
    
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
        else:
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

# ---------- Constants ----------
EMPTY_ANSWER_PLACEHOLDER = '-'

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

# ---------- Human Edit Detection ----------
def get_last_commit_message(file_path: Path) -> Optional[str]:
    """
    Get the last commit message for a specific file.
    
    Returns:
        Commit message or None if no commits exist
    """
    try:
        # Convert to relative path safely
        try:
            rel_path = file_path.relative_to(REPO_ROOT)
        except ValueError:
            # If relative_to fails, try using absolute path
            rel_path = file_path
        
        msg = subprocess.check_output(
            ["git", "log", "-1", "--format=%B", "--", str(rel_path)],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return msg if msg else None
    except subprocess.CalledProcessError:
        return None

def is_last_commit_by_agent(file_path: Path) -> bool:
    """
    Check if the last commit to a file was made by the agent.
    
    Agent commits contain "Agent mode: review" or "Agent mode: integrate" in the message.
    
    Returns:
        True if last commit was by agent or no commits exist yet (safe initial state)
    """
    msg = get_last_commit_message(file_path)
    if not msg:
        # No commits yet - this is the initial state before any changes
        # Treat as safe since there's nothing to protect yet
        return True
    
    # Check for agent signature in commit message
    return "Agent mode:" in msg

def has_unauthorized_human_edits_to_protected_sections() -> tuple[bool, str]:
    """
    Detect if humans have directly edited protected sections (2-14) of requirements.md.
    
    Protected sections are "agent-owned" and humans must not edit them directly
    once requirements development begins (i.e., after the first agent commit).
    
    Detection logic:
    1. Check if requirements.md exists and has commit history
    2. If the last commit to requirements.md was NOT by the agent, it's a human edit
    3. If human edit detected, check if protected sections (2-14) were modified
    
    Returns:
        (has_violations, message)
    """
    if not REQ_FILE.exists():
        return False, "Requirements file does not exist yet"
    
    # Check if this is the first commit (no previous commits)
    try:
        subprocess.check_output(
            ["git", "log", "-1", "--", "docs/requirements.md"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        # No commits yet, safe to proceed
        return False, "No previous commits, initial state is safe"
    
    # Check if last commit was by agent
    if is_last_commit_by_agent(REQ_FILE):
        return False, "Last commit was by agent"
    
    # Last commit was by human - check if protected sections were modified
    # Get the diff of the last commit to see what changed
    try:
        # Check if HEAD~1 exists (not an initial commit)
        try:
            subprocess.check_output(
                ["git", "rev-parse", "HEAD~1"],
                cwd=REPO_ROOT,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            # This is the initial commit, no parent to compare
            # Since we already checked last commit was not by agent, this is a human's initial commit
            # Check if it contains content in sections 2-14
            content = REQ_FILE.read_text(encoding="utf-8")
            if has_content_in_protected_sections(content):
                return True, "Human edits detected in protected sections (2-14)"
            return False, "Human edits only in non-protected sections"
        
        diff_output = subprocess.check_output(
            ["git", "diff", "HEAD~1", "HEAD", "--", "docs/requirements.md"],
            cwd=REPO_ROOT
        ).decode()
        
        # Parse diff to see if any lines in sections 2-14 were modified
        # Track section context based on diff lines
        current_section = None
        has_protected_changes = False
        
        for line in diff_output.splitlines():
            # Skip diff metadata lines
            if line.startswith('@@') or line.startswith('+++') or line.startswith('---'):
                continue
            
            # Extract the actual content by removing diff prefix
            # Diff lines start with ' ' (context), '+' (added), or '-' (removed)
            if len(line) > 0 and line[0] in [' ', '+', '-']:
                content_line = line[1:] if len(line) > 1 else ''
                
                # Check if this is a section header
                section_match = re.match(r'##\s+(\d+)\.\s+', content_line)
                if section_match:
                    section_num = int(section_match.group(1))
                    current_section = section_num
                
                # If we're in a protected section and this line is added or removed
                # (not just context), we have a protected change
                if current_section is not None and 2 <= current_section <= 14:
                    if line.startswith('+') or line.startswith('-'):
                        # Ignore the section header line itself
                        if not re.match(r'##\s+\d+\.\s+', content_line):
                            has_protected_changes = True
                            break
        
        if has_protected_changes:
            return True, "Human edits detected in protected sections (2-14)"
        else:
            return False, "Human edits only in non-protected sections"
            
    except subprocess.CalledProcessError as e:
        # If we can't get the diff, be conservative and allow it
        return False, f"Could not verify edit source: {e}"

def has_content_in_protected_sections(content: str) -> bool:
    """
    Check if there is actual content in protected sections 2-14.
    Used for initial commits to detect if human added content to protected sections.
    
    Returns:
        True if protected sections have content beyond headers and comments
    """
    lines = content.splitlines()
    in_protected_section = False
    has_content = False
    
    for line in lines:
        # Detect section headers
        section_match = re.match(r'##\s+(\d+)\.\s+', line)
        if section_match:
            section_num = int(section_match.group(1))
            in_protected_section = (2 <= section_num <= 14)
        
        # If in protected section, check for non-trivial content
        if in_protected_section:
            stripped = line.strip()
            # Skip empty lines, comments, headers, and horizontal rules
            if stripped and not stripped.startswith('#') and not stripped.startswith('<!--') and stripped != '---':
                has_content = True
                break
    
    return has_content

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
    
    if mode == "review":
        intake_instructions = ""
        if intake_content:
            intake_instructions = """
- Process Intake section: Convert unstructured notes into formal Open Questions
- Clear the Intake section after processing
"""
        return f"""{intake_notice}{template_warning}MODE: review

In review mode, you MUST output ONLY structured patches (NOT a full document).

You may:
- Review document quality and completeness
- Identify new risks to add
- Identify new open questions{intake_instructions}
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
        return """
MODE: integrate

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
    
    Called once and only once during the 0.0 -> 0.1+ version transition.
    """
    # Identify line ranges for content sections 2-14 (not section 1 or 15)
    # We'll track section boundaries
    section_ranges = []
    current_section = None
    current_start = None
    
    for i, line in enumerate(lines):
        # Detect section headers like "## 2. Problem Statement"
        section_match = re.match(r'##\s+(\d+)\.\s+', line)
        if section_match:
            section_num = int(section_match.group(1))
            
            # Save previous section if it was in range 2-14
            if current_section is not None and 2 <= current_section <= 14 and current_start is not None:
                section_ranges.append((current_start, i))
            
            # Start tracking new section if in range 2-14
            if 2 <= section_num <= 14:
                current_section = section_num
                current_start = i
            else:
                current_section = None
                current_start = None
    
    # Handle last section if it was in range 2-14
    if current_section is not None and 2 <= current_section <= 14 and current_start is not None:
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
        status_match = re.search(r'### STATUS_UPDATE\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        risks_match = re.search(r'### RISKS\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        questions_match = re.search(r'### OPEN_QUESTIONS\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        intake_clear_match = re.search(r'### INTAKE_CLEAR\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        
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
                        if lines[j].strip().startswith('---') and j + 1 < len(lines) and '###' in lines[j + 2]:
                            end_pos = j
                            break
                    
                    if end_pos:
                        # Replace content between header and separator with placeholder
                        placeholder = "\n[Empty - Add your unstructured notes, questions, or thoughts here. They will be converted to formal Open Questions by the Requirements Agent.]\n"
                        # Find where comments end
                        comment_end = start_pos + 1
                        while comment_end < end_pos:
                            if not lines[comment_end].strip().startswith('<!--') and not lines[comment_end].strip().startswith('-->') and '-->' not in lines[comment_end]:
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
            for i, line in enumerate(lines):
                if '### Open Questions' in line:
                    # Find the comment block after questions
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith('<!--') and 'ANSWER INTEGRATION WORKFLOW' in lines[j]:
                            # Insert before the comment block
                            lines.insert(j, "\n" + questions_content + "\n")
                            break
                    break
    
    else:  # integrate mode
        # Extract integration patches
        integrated_match = re.search(
            r'### INTEGRATED_SECTIONS\s*\n(.*?)(?=### RISKS|\Z)',
            agent_output, re.DOTALL
        )
        risks_match = re.search(
            r'### RISKS\s*\n(.*?)(?=### STATUS_UPDATE|\Z)',
            agent_output, re.DOTALL
        )
        status_match = re.search(
            r'### STATUS_UPDATE\s*\n(.*?)(?=###|\Z)',
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
    
    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    # Verify clean working tree
    print("\n[Pre-flight] Checking git status...")
    if not is_working_tree_clean():
        print("ERROR: Working tree has uncommitted changes")
        print("Please commit or stash changes before running.")
        print("\nCurrent status:")
        print(git_status_porcelain())
        sys.exit(1)
    print("✓ Working tree is clean")
    
    # Check for unauthorized human edits to protected sections
    print("\n[Protection] Checking for direct human edits to agent-owned sections...")
    has_violations, violation_msg = has_unauthorized_human_edits_to_protected_sections()
    if has_violations:
        print("ERROR: Direct human edits to protected sections detected")
        print(f"\n{violation_msg}")
        print("\nSections 2-14 are agent-owned and must not be edited directly by humans.")
        print("To make changes to these sections:")
        print("  1. Add questions to Section 1 (Document Control) Open Questions")
        print("  2. Provide answers to those questions")
        print("  3. Run this script to let the agent integrate the changes")
        print("\nHuman edits are only allowed in:")
        print("  - Section 1 (Document Control)")
        print("  - Section 15 (Approval Record)")
        sys.exit(1)
    print(f"✓ {violation_msg}")
    
    # Get user context
    print("\nOptional context (Ctrl+D to finish):")
    user_context = sys.stdin.read().strip()
    
    # Read files
    requirements = REQ_FILE.read_text(encoding="utf-8")
    agent_profile = AGENT_PROFILE.read_text(encoding="utf-8")
    
    # Parse Open Questions to validate format
    print("\n[Format] Parsing Open Questions section...")
    questions = _parse_open_questions_section(requirements)
    print(f"✓ Found {len(questions)} questions")
    resolved_count = sum(1 for q in questions if q['status'].lower().startswith('resolved'))
    pending_count = sum(1 for q in questions if q['answer'] and not q['status'].lower().startswith('resolved'))
    print(f"  - {resolved_count} resolved")
    print(f"  - {pending_count} pending integration")
    
    # Parse Intake section
    print("\n[Intake] Parsing Intake section...")
    intake_content = _parse_intake_section(requirements)
    if intake_content:
        print(f"✓ Found intake content ({len(intake_content)} chars)")
        print("  → Will be converted to Open Questions")
    else:
        print("✓ Intake section is empty")
    
    # Check document version for template baseline detection
    version_str, major, minor = get_document_version(requirements)
    is_template = is_template_baseline(requirements)
    print(f"\n[Version] Document version: {version_str}")
    if is_template:
        print("  ⚠️  Template baseline detected - special safeguards active")
    
    # Determine mode
    mode = determine_mode(requirements)
    print(f"\n[Mode] Running in {mode} mode")
    
    # Build prompt
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
    
    # Call agent
    print(f"\n[Agent] Calling {MODEL}...")
    
    # Import anthropic only when needed
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
    
    # Validate output format (simple check)
    expected_marker = "## REVIEW_OUTPUT" if mode == "review" else "## INTEGRATION_OUTPUT"
    if expected_marker not in agent_output:
        print(f"\nERROR: Agent output missing {expected_marker}")
        print("Agent must output structured patches, not a full document.")
        sys.exit(1)
    
    print("✓ Agent output validated")
    
    # Apply patches
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
    
    # Auto-commit if changes exist
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
    
    # Check for approval and record state transition (one-time)
    # Reload requirements after commit to ensure we have the latest state from disk
    # (patches may have been applied and committed by commit_changes)
    requirements = REQ_FILE.read_text(encoding="utf-8")
    
    if is_requirements_approved(requirements):
        print("\n[Approval] Requirements document is APPROVED")
        
        if has_planning_been_triggered():
            print("✓ Planning handoff already recorded (marker exists)")
            print(f"  Marker: {PLANNING_STATE_MARKER.relative_to(REPO_ROOT)}")
        else:
            print("→ First-time approval detected. Recording planning handoff readiness...")
            
            # Create and commit the state marker
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
