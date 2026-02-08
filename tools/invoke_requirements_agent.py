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

# ---------- Mode Determination ----------
def determine_mode(requirements: str) -> str:
    """
    Determine execution mode: integrate if there are pending answers, else review.
    """
    return "integrate" if _has_pending_answers(requirements) else "review"

# ---------- Approval Detection & State Recording ----------
def is_requirements_approved(requirements: str) -> bool:
    """
    Detect if requirements are approved by checking for explicit approval marker.
    
    Returns True if document contains "Current Status" followed by "Approved".
    """
    # Simple text search for approval indicator in section
    return 'Current Status' in requirements and 'Approved' in requirements

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
def get_agent_instructions(mode: str) -> str:
    """Get mode-specific instructions for the agent."""
    if mode == "review":
        return """
MODE: review

In review mode, you MUST output ONLY structured patches (NOT a full document).

You may:
- Review document quality and completeness
- Identify new risks to add
- Identify new open questions
- Recommend approval status

OUTPUT FORMAT (required):

## REVIEW_OUTPUT

### STATUS_UPDATE
[Your status recommendation: "Ready for Approval" or "Pending - Revisions Required"]
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
        
        status_update = status_match.group(1).strip() if status_match else ""
        risks_content = risks_match.group(1).strip() if risks_match else ""
        questions_content = questions_match.group(1).strip() if questions_match else ""
        
        # Update approval status if provided
        _update_approval_status(lines, status_update)
        
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
    
    # Add revision history entry (simplified - just append a line after Version History)
    today = datetime.now().strftime("%Y-%m-%d")
    change_desc = f"{mode.capitalize()} pass by Requirements Agent"
    
    for i, line in enumerate(lines):
        if '### Version History' in line:
            # Find the header row separator and insert after it
            for j in range(i + 1, min(i + 10, len(lines))):
                if '|---' in lines[j]:
                    # Insert new entry right after the separator
                    lines.insert(j + 1, f"| - | {today} | Requirements Agent | {change_desc} |")
                    break
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
    
    # Determine mode
    mode = determine_mode(requirements)
    print(f"\n[Mode] Running in {mode} mode")
    
    # Build prompt
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
