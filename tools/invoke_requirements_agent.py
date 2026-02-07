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

# ---------- Configuration ----------
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = REPO_ROOT / "docs" / "requirements.md"
AGENT_PROFILE = REPO_ROOT / "agent-profiles" / "requirements-agent.md"
PLANNING_STATE_MARKER = REPO_ROOT / ".agent_state" / "requirements_approved"

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

# Canonical Open Questions table schema
CANONICAL_OPEN_QUESTIONS_COLUMNS = [
    "Question ID",
    "Question",
    "Asked By",
    "Date",
    "Answer",
    "Resolution Status"
]

# ---------- Schema Validation ----------
def validate_open_questions_schema(requirements: str) -> tuple[bool, list[str], int]:
    """
    Validate the Open Questions table schema.

    Returns:
        (is_valid, missing_columns, header_line_idx)
    """
    lines = requirements.split('\n')
    in_open_questions = False

    for i, line in enumerate(lines):
        if '### Open Questions' in line:
            in_open_questions = True
            continue
        if in_open_questions and line.strip().startswith('##') and 'Open Questions' not in line:
            break
        if in_open_questions and line.strip().startswith('|') and 'Question ID' in line:
            header_parts = [col.strip() for col in line.split('|') if col.strip()]
            missing_columns = [col for col in CANONICAL_OPEN_QUESTIONS_COLUMNS if col not in header_parts]
            if missing_columns:
                return False, missing_columns, i
            if header_parts != CANONICAL_OPEN_QUESTIONS_COLUMNS:
                return False, ["Column order incorrect"], i
            return True, [], i

    return True, [], -1


def repair_open_questions_schema(requirements: str) -> tuple[str, bool]:
    """
    Repair the Open Questions table schema by restoring missing columns.

    Returns:
        (repaired_requirements, was_repaired)
    """
    is_valid, missing_columns, header_idx = validate_open_questions_schema(requirements)

    if is_valid or header_idx == -1:
        return requirements, False

    lines = requirements.split('\n')
    existing_header = lines[header_idx]
    header_parts = [col.strip() for col in existing_header.split('|') if col.strip()]

    # Build canonical header and separator
    canonical_header = '| ' + ' | '.join(CANONICAL_OPEN_QUESTIONS_COLUMNS) + ' |'
    canonical_separator = '|' + '|'.join(['-' * (len(col) + 2) for col in CANONICAL_OPEN_QUESTIONS_COLUMNS]) + '|'

    lines[header_idx] = canonical_header
    if header_idx + 1 < len(lines) and lines[header_idx + 1].strip().startswith('|---'):
        lines[header_idx + 1] = canonical_separator

    # Repair data rows
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        if line.strip().startswith('##') or line.strip().startswith('---'):
            break
        if line.strip().startswith('|') and '|---' not in line:
            row_parts = [col.strip() for col in line.split('|')]
            columns = row_parts[1:-1] if len(row_parts) > 2 else []
            column_values = {}
            for j, col_name in enumerate(header_parts):
                if j < len(columns):
                    column_values[col_name] = columns[j]
            new_columns = []
            for col_name in CANONICAL_OPEN_QUESTIONS_COLUMNS:
                if col_name in column_values:
                    new_columns.append(column_values[col_name])
                elif col_name == "Answer":
                    new_columns.append("")
                elif col_name == "Resolution Status":
                    new_columns.append("Open")
                else:
                    new_columns.append("")
            lines[i] = '| ' + ' | '.join(new_columns) + ' |'

    return '\n'.join(lines), True

# ---------- Mode Determination ----------
def has_pending_answers(requirements: str) -> bool:
    """
    Check if there are answered questions pending integration.
    
    Returns True if any question has a non-empty Answer field
    and Resolution Status is not "Resolved".
    """
    lines = requirements.split('\n')
    in_questions = False
    in_table = False
    
    for line in lines:
        if '### Open Questions' in line:
            in_questions = True
            continue
        if in_questions and line.strip().startswith('##'):
            break
        if in_questions and '| Question ID |' in line:
            in_table = True
            continue
        if in_table and '|---' in line:
            continue
        if in_table and line.strip().startswith('|') and line.count('|') >= 6:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 7:
                answer = parts[5].strip()
                status = parts[6].strip()
                # Has answer and not resolved
                if answer and answer != EMPTY_ANSWER_PLACEHOLDER and not status.lower().startswith('resolved'):
                    return True
    
    return False

def determine_mode(requirements: str) -> str:
    """
    Determine execution mode: integrate if there are pending answers, else review.
    """
    return "integrate" if has_pending_answers(requirements) else "review"

# ---------- Approval Detection & State Recording ----------
def is_requirements_approved(requirements: str) -> bool:
    """
    Detect if requirements are approved by checking the Approval Record section.
    
    Returns True if Current Status field contains "Approved".
    This is a deterministic, regex-based check.
    
    Expected table format (## 15. Approval Record):
    | Field | Value |
    |-------|-------|
    | Current Status | Approved |
    
    The pattern matches variations in whitespace but requires exact text match for "Approved".
    """
    # Look for the Approval Record section and Current Status field
    # Pattern: | Current Status | Approved |
    # Allows flexible whitespace but requires exact "Approved" text (case insensitive)
    pattern = r'\|\s*Current Status\s*\|\s*Approved\s*\|'
    return bool(re.search(pattern, requirements, re.IGNORECASE))

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
[New risk rows in markdown table format, or "No new risks identified"]

### OPEN_QUESTIONS
[New question rows in markdown table format, or "No new questions"]
| Question ID | Question | Asked By | Date | Answer | Resolution Status |

DO NOT output the full document.
"""
    else:  # integrate
        return """
MODE: integrate

In integrate mode, you MUST output ONLY structured patches (NOT a full document).

You must:
1. Find Open Questions with non-empty Answer fields
2. Integrate each answer into the appropriate section
3. Mark questions as "Resolved"
4. Update risks based on integrated answers
5. Recommend approval status

OUTPUT FORMAT (required):

## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Section: <exact section heading, e.g., "## 8. Functional Requirements">
<content to append, with source traceability>

### RESOLVED_QUESTIONS
<Question IDs that were integrated, e.g., "Q-003, Q-004", or "No questions resolved">

### RISKS
<Updated risk rows in markdown table format, or "No risk changes">

### STATUS_UPDATE
<Your status recommendation with reasons>

DO NOT output the full document.
"""

# ---------- Patch Application ----------
def apply_patches(requirements: str, agent_output: str, mode: str) -> str:
    """
    Apply agent patches to requirements document.
    
    This is a simplified version that:
    1. Extracts patch sections from agent output
    2. Updates corresponding document sections
    3. Updates revision history
    
    Returns updated document.
    """
    lines = requirements.split('\n')
    
    if mode == "review":
        # Extract review patches
        status_match = re.search(r'### STATUS_UPDATE\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        risks_match = re.search(r'### RISKS\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        questions_match = re.search(r'### OPEN_QUESTIONS\s*\n(.*?)(?=###|\Z)', agent_output, re.DOTALL)
        
        status_update = status_match.group(1).strip() if status_match else ""
        risks_content = risks_match.group(1).strip() if risks_match else ""
        questions_content = questions_match.group(1).strip() if questions_match else ""
        
        # Update approval status if provided
        if status_update and "No changes" not in status_update:
            for i, line in enumerate(lines):
                if '| Approval Status |' in line:
                    if 'Ready for Approval' in status_update:
                        lines[i] = '| Approval Status | Ready for Approval |'
                    elif 'Pending' in status_update:
                        lines[i] = '| Approval Status | Pending - Revisions Required |'
                    break
        
        # Append new risks
        if risks_content and "No new risks" not in risks_content:
            for i, line in enumerate(lines):
                if '### Risks' in line:
                    # Find end of risks section
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() and not lines[j].strip().startswith('|'):
                            lines.insert(j, "\n" + risks_content)
                            break
                    break
        
        # Append new questions
        if questions_content and "No new questions" not in questions_content:
            for i, line in enumerate(lines):
                if '### Open Questions' in line:
                    # Find end of questions section
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() and not lines[j].strip().startswith('|'):
                            lines.insert(j, "\n" + questions_content)
                            break
                    break
    
    else:  # integrate mode
        # Extract integration patches
        integrated_match = re.search(
            r'### INTEGRATED_SECTIONS\s*\n(.*?)(?=### RESOLVED_QUESTIONS|\Z)',
            agent_output, re.DOTALL
        )
        resolved_match = re.search(
            r'### RESOLVED_QUESTIONS\s*\n(.*?)(?=### RISKS|\Z)',
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
        resolved_questions = resolved_match.group(1).strip() if resolved_match else ""
        risks_content = risks_match.group(1).strip() if risks_match else ""
        status_update = status_match.group(1).strip() if status_match else ""
        
        # Apply integrated sections
        if integrated_content:
            # Parse section updates
            section_pattern = re.compile(r'- Section: (.+?)\n(.*?)(?=\n- Section:|\Z)', re.DOTALL)
            for match in section_pattern.finditer(integrated_content):
                section_heading = match.group(1).strip()
                content = match.group(2).strip()
                
                # Find section in document and append content
                for i, line in enumerate(lines):
                    if section_heading in line:
                        # Find next section
                        for j in range(i + 1, len(lines)):
                            if lines[j].strip().startswith('##') and lines[j].strip() != section_heading:
                                lines.insert(j, "\n" + content + "\n")
                                break
                        break
        
        # Mark questions as resolved
        if resolved_questions and "No questions" not in resolved_questions:
            q_ids = [q.strip() for q in resolved_questions.replace(',', ' ').split() if q.strip()]
            for q_id in q_ids:
                for i, line in enumerate(lines):
                    if line.startswith('|') and q_id in line:
                        parts = line.split('|')
                        if len(parts) >= 7:
                            parts[6] = ' Resolved '
                            lines[i] = '|'.join(parts)
        
        # Update risks
        if risks_content and "No risk changes" not in risks_content:
            for i, line in enumerate(lines):
                if '### Risks' in line:
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() and not lines[j].strip().startswith('|'):
                            lines.insert(j, "\n" + risks_content)
                            break
                    break
        
        # Update approval status
        if status_update:
            for i, line in enumerate(lines):
                if '| Approval Status |' in line:
                    if 'Ready for Approval' in status_update:
                        lines[i] = '| Approval Status | Ready for Approval |'
                    elif 'Pending' in status_update:
                        lines[i] = '| Approval Status | Pending - Revisions Required |'
                    break
    
    # Add revision history entry
    today = datetime.now().strftime("%Y-%m-%d")
    change_desc = f"{mode.capitalize()} pass by Requirements Agent"
    
    for i, line in enumerate(lines):
        if '### Version History' in line:
            # Find first data row and extract version
            for j in range(i + 1, len(lines)):
                if lines[j].startswith('|') and '|---' not in lines[j] and lines[j].count('|') >= 4:
                    parts = [p.strip() for p in lines[j].split('|')]
                    if len(parts) >= 2:
                        try:
                            # Use string manipulation to avoid floating-point precision issues
                            current_ver_str = parts[1]
                            major, minor = current_ver_str.split('.')
                            new_minor = int(minor) + 1
                            new_ver = f"{major}.{new_minor}"
                            new_entry = f"| {new_ver} | {today} | Requirements Agent | {change_desc} |"
                            lines.insert(j, new_entry)
                            break
                        except (ValueError, IndexError):
                            pass
                    break
            break
    
    return '\n'.join(lines)

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
    
    # Validate and repair Open Questions schema
    print("\n[Schema] Validating Open Questions table...")
    is_valid, missing_columns, header_idx = validate_open_questions_schema(requirements)
    
    if not is_valid:
        print(f"⚠️  Missing columns: {', '.join(missing_columns)}")
        print("🔧 Auto-repairing schema...")
        requirements, was_repaired = repair_open_questions_schema(requirements)
        
        if was_repaired:
            REQ_FILE.write_text(requirements, encoding="utf-8")
            print(f"✓ Schema repaired")
        else:
            print("⚠️  Auto-repair failed")
    else:
        print("✓ Schema valid")
    
    # Reload after potential repair
    requirements = REQ_FILE.read_text(encoding="utf-8")
    
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
    updated_doc = apply_patches(requirements, agent_output, mode)
    
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
