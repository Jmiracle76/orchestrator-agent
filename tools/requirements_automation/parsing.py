from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .config import (
    META_MARKER_RE,
    PLACEHOLDER_TOKEN,
    REVIEW_GATE_RESULT_RE,
    SECTION_LOCK_RE,
    SECTION_MARKER_RE,
    SUBSECTION_MARKER_RE,
    SUPPORTED_METADATA_KEYS,
    TABLE_MARKER_RE,
)
from .models import SectionSpan, SubsectionSpan

META_VALUE_LINE_RE = re.compile(r"-\s*\*\*(?P<label>[^*]+)\*\*:\s*(?P<value>.+)")
WORKFLOW_ORDER_START_RE = re.compile(r"<!--\s*workflow:order\b")


def _normalize_meta_label(label: str) -> str:
    return re.sub(r"[\s\-]+", "_", label.strip().lower())


def extract_metadata(lines: List[str]) -> Dict[str, str]:
    """Extract metadata from template/doc header markers."""
    metadata: Dict[str, str] = {}
    for i, ln in enumerate(lines):
        m = META_MARKER_RE.search(ln)
        if not m:
            continue
        key = m.group("key")
        if key not in SUPPORTED_METADATA_KEYS:
            continue
        value = (m.group("value") or "").strip()
        if value:
            metadata[key] = value
        elif i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            vmatch = META_VALUE_LINE_RE.match(next_line)
            if vmatch and _normalize_meta_label(vmatch.group("label")) == key:
                metadata[key] = vmatch.group("value").strip()
        if key == "doc_format":
            version = (m.group("version") or "").strip()
            if version:
                metadata["version"] = version
    return metadata


def extract_workflow_order(lines: List[str]) -> List[str]:
    """Extract the workflow order block from a template/doc header."""
    in_block = False
    workflow: List[str] = []
    seen = set()
    start_line = None

    def _add_entry(raw: str, doc_line_number: int) -> None:
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            return
        if entry in seen:
            raise ValueError(f"Duplicate workflow target '{entry}' on line {doc_line_number}.")
        workflow.append(entry)
        seen.add(entry)

    def _consume_line(raw: str, doc_line_number: int) -> bool:
        if "-->" in raw:
            content, _ = raw.split("-->", 1)
            _add_entry(content, doc_line_number)
            return True
        _add_entry(raw, doc_line_number)
        return False

    for idx, ln in enumerate(lines):
        if not in_block:
            match = WORKFLOW_ORDER_START_RE.search(ln)
            if match:
                in_block = True
                start_line = idx + 1
                remainder = ln[match.end() :]
                if _consume_line(remainder, idx + 1):
                    in_block = False
                    break
            continue

        if _consume_line(ln, idx + 1):
            in_block = False
            break

    if start_line is None:
        raise ValueError(
            "Workflow order block not found. Add a workflow order block after the metadata comments in the document header, e.g.:\n"
            "<!-- workflow:order\nsection_id\n-->"
        )
    if in_block:
        raise ValueError(f"Workflow order block not terminated (started on line {start_line}).")
    if not workflow:
        raise ValueError("Workflow order block is empty.")
    return workflow


def find_sections(lines: List[str]) -> List[SectionSpan]:
    """Locate section markers and return their line spans."""
    starts: List[Tuple[str, int]] = []
    for i, ln in enumerate(lines):
        m = SECTION_MARKER_RE.search(ln)
        if m:
            starts.append((m.group("id"), i))
    spans: List[SectionSpan] = []
    for idx, (sid, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines)
        spans.append(SectionSpan(sid, start, end))
    return spans


def get_section_span(spans: List[SectionSpan], section_id: str) -> Optional[SectionSpan]:
    """Return the span for a specific section ID, if present."""
    for sp in spans:
        if sp.section_id == section_id:
            return sp
    return None


def validate_required_section_spans(lines: List[str], required_ids: List[str]) -> List[str]:
    """Validate required sections exist, are unique, and non-nested."""
    spans = find_sections(lines)
    by_id: Dict[str, List[SectionSpan]] = {}
    for sp in spans:
        by_id.setdefault(sp.section_id, []).append(sp)

    issues: List[str] = []
    for sid in required_ids:
        hits = by_id.get(sid, [])
        if not hits:
            issues.append(f"Missing required section marker: {sid}")
            continue
        if len(hits) > 1:
            issues.append(f"Duplicate section markers for {sid} (count={len(hits)})")
            continue
        sp = hits[0]
        if sp.end_line <= sp.start_line:
            issues.append(f"Invalid span for {sid}: start={sp.start_line}, end={sp.end_line}")
            continue
        # Ensure section spans do not contain another marker (nested/corrupt).
        inner = "\n".join(lines[sp.start_line + 1 : sp.end_line])
        if SECTION_MARKER_RE.search(inner):
            issues.append(
                f"Section {sid} span contains another <!-- section:... --> marker (nested/corrupt)."
            )
    return issues


def section_text(lines: List[str], span: SectionSpan) -> str:
    """Return full raw text for the section span (including markers)."""
    return "\n".join(lines[span.start_line : span.end_line])


def section_body(lines: List[str], span: SectionSpan) -> str:
    """Extract the data-plane body text, excluding markers and headers."""
    block = lines[span.start_line : span.end_line]
    body: List[str] = []
    for ln in block:
        if SECTION_MARKER_RE.search(ln):
            continue
        if SECTION_LOCK_RE.search(ln):
            continue
        if ln.lstrip().startswith("##"):
            continue
        if ln.strip() == "---":
            continue
        body.append(ln)
    return "\n".join(body).strip("\n")


def section_is_locked(lines: List[str], span: SectionSpan) -> bool:
    """Return True if the last lock marker in the section is lock=true."""
    block = section_text(lines, span)
    locks = list(SECTION_LOCK_RE.finditer(block))
    return bool(locks) and locks[-1].group("lock") == "true"


def section_is_blank(lines: List[str], span: SectionSpan) -> bool:
    """
    Return True if the section preamble is blank (contains the placeholder token).
    
    A section is considered 'blank' when its main body (preamble) contains the 
    placeholder token, indicating it needs human input. Only checks the preamble
    before any subsections; subsection placeholders are ignored for section-level 
    blank detection.
    """
    return PLACEHOLDER_TOKEN in section_preamble_text(lines, span)


def find_table_block(lines: List[str], table_id: str) -> Optional[Tuple[int, int]]:
    """Find a markdown table block that follows a <!-- table:... --> marker."""
    marker_line = None
    for i, ln in enumerate(lines):
        m = TABLE_MARKER_RE.search(ln)
        if m and m.group("id") == table_id:
            marker_line = i
            break
    if marker_line is None:
        return None
    start = None
    # Table starts at the first row that begins with a pipe.
    for j in range(marker_line + 1, len(lines)):
        if lines[j].lstrip().startswith("|"):
            start = j
            break
        if SECTION_MARKER_RE.search(lines[j]):
            return None
    if start is None:
        return None
    end = start
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1
    return (start, end)


def find_subsections_within(lines: List[str], section_span: SectionSpan) -> List[SubsectionSpan]:
    """Return all subsection spans within a parent section span."""
    starts: List[Tuple[str, int]] = []
    for i in range(section_span.start_line, section_span.end_line):
        m = SUBSECTION_MARKER_RE.search(lines[i])
        if m:
            starts.append((m.group("id"), i))
    subs: List[SubsectionSpan] = []
    for idx, (sid, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else section_span.end_line
        subs.append(SubsectionSpan(sid, start, end))
    return subs


def get_subsection_span(subs: List[SubsectionSpan], subsection_id: str) -> Optional[SubsectionSpan]:
    """Return the span for a specific subsection ID, if present."""
    for s in subs:
        if s.subsection_id == subsection_id:
            return s
    return None


def get_section_preamble_end_line(lines: List[str], span: SectionSpan) -> int:
    """
    Get the line number where the section preamble ends.
    
    The preamble is the main body content before any subsections.
    Returns the line number of the first subsection, or span.end_line if no subsections exist.
    
    Args:
        lines: Document lines
        span: Section span
        
    Returns:
        Line number where preamble ends (exclusive)
    """
    subs = find_subsections_within(lines, span)
    if subs:
        return subs[0].start_line
    return span.end_line


def section_preamble_text(lines: List[str], span: SectionSpan) -> str:
    """
    Extract the section preamble text (content before any subsections).
    
    This excludes subsection content while keeping the main section body.
    Includes markers and headers in the preamble.
    
    Args:
        lines: Document lines
        span: Section span
        
    Returns:
        Preamble text as a single string
    """
    preamble_end = get_section_preamble_end_line(lines, span)
    return "\n".join(lines[span.start_line : preamble_end])


def extract_all_section_ids(lines: List[str]) -> List[str]:
    """Extract all section IDs from document (excluding review gates)."""
    spans = find_sections(lines)
    return [sp.section_id for sp in spans]


def section_exists(section_id: str, lines: List[str]) -> bool:
    """Check if a section exists in the document."""
    spans = find_sections(lines)
    return get_section_span(spans, section_id) is not None


def contains_markers(text: str) -> bool:
    """Check if text contains structure markers or HTML comments."""
    markers = [
        SECTION_MARKER_RE,
        SECTION_LOCK_RE,
        TABLE_MARKER_RE,
        SUBSECTION_MARKER_RE,
        META_MARKER_RE,
    ]
    for marker_re in markers:
        if marker_re.search(text):
            return True
    # Also check for any HTML comments (which would be structural markers)
    if "<!--" in text and "-->" in text:
        return True
    return False


def apply_patch(section_id: str, suggestion: str, lines: List[str]) -> List[str]:
    """
    Apply a patch to a section, replacing its body content.

    Validates document structure before applying patch and ensures the suggestion
    doesn't contain forbidden structure markers.

    Args:
        section_id: ID of section to patch
        suggestion: New body content
        lines: Document content as list of strings

    Returns:
        Updated document lines

    Raises:
        ValueError: If section not found or suggestion contains markers
        StructuralError: If patch would corrupt structure
    """
    from .structural_validator import StructuralValidator
    from .validation_errors import InvalidSpanError, StructuralError

    # Validate current structure
    validator_before = StructuralValidator(lines)
    validator_before.validate_or_raise()

    spans = find_sections(lines)
    span = get_section_span(spans, section_id)

    if not span:
        raise InvalidSpanError(section_id, "Cannot apply patch - section not found")

    # Validate suggestion doesn't contain structure markers
    if contains_markers(suggestion):
        raise ValueError(f"Patch suggestion contains forbidden structure markers")

    # Build new content preserving markers and headers
    new_lines = []
    in_section = False
    body_started = False

    for i, line in enumerate(lines):
        if i == span.start_line:
            # Add section marker
            new_lines.append(line)
            in_section = True
            continue

        if in_section and i < span.end_line:
            # Skip old body content, but preserve lock markers and headers
            if SECTION_LOCK_RE.search(line):
                new_lines.append(line)
            elif line.lstrip().startswith("##"):
                new_lines.append(line)
            elif not body_started:
                # Insert new content after headers/markers
                for suggestion_line in suggestion.split("\n"):
                    new_lines.append(suggestion_line)
                body_started = True
        elif i == span.end_line:
            # Reached end of section
            if not body_started:
                # No headers found, insert content now
                for suggestion_line in suggestion.split("\n"):
                    new_lines.append(suggestion_line)
            in_section = False
            body_started = False
            new_lines.append(line)
        else:
            new_lines.append(line)

    # Validate structure after patch
    validator_after = StructuralValidator(new_lines)
    errors_after = validator_after.validate_all()
    if errors_after:
        raise StructuralError(f"Patch to '{section_id}' would corrupt structure: {errors_after[0]}")

    return new_lines


def extract_review_gate_results(lines: List[str]) -> Dict[str, Tuple[str, int, int]]:
    """
    Extract review gate results from document markers.

    Returns:
        Dict mapping gate_id to (status, issues_count, warnings_count)
        where status is "passed" or "failed"
    """
    results: Dict[str, Tuple[str, int, int]] = {}

    for line in lines:
        m = REVIEW_GATE_RESULT_RE.search(line)
        if m:
            gate_id = m.group("gate_id")
            status = m.group("status")
            issues = int(m.group("issues") or "0")
            warnings = int(m.group("warnings") or "0")
            results[gate_id] = (status, issues, warnings)

    return results


def find_duplicate_section_markers(lines: List[str]) -> List[str]:
    """
    Find duplicate section markers in the document.

    Returns:
        List of section IDs that have duplicate markers
    """
    section_counts: Dict[str, int] = {}

    for line in lines:
        m = SECTION_MARKER_RE.search(line)
        if m:
            section_id = m.group("id")
            section_counts[section_id] = section_counts.get(section_id, 0) + 1

    duplicates = [sid for sid, count in section_counts.items() if count > 1]
    return duplicates


def has_placeholder(span: SectionSpan, lines: List[str]) -> bool:
    """
    Check if a section preamble contains PLACEHOLDER token.
    
    Only checks the main section body (preamble) before any subsections.
    Subsection placeholders are ignored for section-level completion.
    
    Args:
        span: Section span
        lines: Document lines
        
    Returns:
        True if preamble contains PLACEHOLDER token
    """
    preamble_text = section_preamble_text(lines, span)
    return PLACEHOLDER_TOKEN in preamble_text


def validate_open_questions_table_schema(lines: List[str]) -> bool:
    """
    Validate that the Open Questions table has the correct schema.

    Returns:
        True if the table schema is valid, False otherwise
    """
    from .config import OPEN_Q_COLUMNS

    span = find_table_block(lines, "open_questions")
    if not span:
        return False

    start, end = span
    table_lines = lines[start:end]

    if len(table_lines) < 2:
        return False

    # Parse header row
    header_line = table_lines[0]
    if not header_line.lstrip().startswith("|"):
        return False

    header_cells = [c.strip() for c in header_line.strip().strip("|").split("|")]
    return header_cells == OPEN_Q_COLUMNS


def check_section_table_for_open_questions(lines: List[str], section_id: str) -> Tuple[bool, int]:
    """
    Check if a section's question table has any "Open" status rows.
    
    Args:
        lines: Document content as list of strings
        section_id: Section ID to check (e.g., "problem_statement")
    
    Returns:
        Tuple of (has_open_questions, open_count)
    """
    table_id = f"{section_id}_questions"
    span = find_table_block(lines, table_id)
    
    if not span:
        # No table found - no open questions
        return False, 0
    
    start, end = span
    table_lines = lines[start:end]
    
    if len(table_lines) < 2:
        # Header only, no data rows
        return False, 0
    
    # Skip header and separator rows
    data_rows = table_lines[2:]
    
    open_count = 0
    for row in data_rows:
        if not row.strip().startswith("|"):
            continue
        
        # Parse row cells
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        
        # Typically: | Question ID | Question | Date | Answer | Status |
        # Status is the last column (index -1)
        if len(cells) >= 5:
            status = cells[-1].strip()
            if status.lower() == "open":
                open_count += 1
    
    return open_count > 0, open_count


def check_section_table_for_open_blockers(lines: List[str], section_id: str) -> Tuple[bool, int]:
    """
    Check if a section's question table has any "Open" status rows that are blockers.
    
    This function only counts questions prefixed with [BLOCKER] or unprefixed questions
    (for backward compatibility) that have "Open" status. Questions prefixed with 
    [WARNING] are not counted as blockers.
    
    Args:
        lines: Document content as list of strings
        section_id: Section ID to check (e.g., "problem_statement")
    
    Returns:
        Tuple of (has_open_blockers, open_blocker_count)
    """
    table_id = f"{section_id}_questions"
    span = find_table_block(lines, table_id)
    
    if not span:
        # No table found - no open blockers
        return False, 0
    
    start, end = span
    table_lines = lines[start:end]
    
    if len(table_lines) < 2:
        # Header only, no data rows
        return False, 0
    
    # Skip header and separator rows
    data_rows = table_lines[2:]
    
    blocker_count = 0
    for row in data_rows:
        if not row.strip().startswith("|"):
            continue
        
        # Parse row cells
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        
        # Typically: | Question ID | Question | Date | Answer | Status |
        # Question is at index 1, Status is at index -1
        if len(cells) >= 5:
            question_text = cells[1].strip()
            status = cells[-1].strip()
            
            # Only count as blocker if:
            # 1. Status is "Open" (case-insensitive)
            # 2. Question is NOT a warning (backward compatibility: unprefixed questions = blockers)
            if status.lower() == "open":
                # Check if it's a warning (which should NOT block)
                if question_text.upper().startswith("[WARNING]"):
                    continue
                # Count as blocker if:
                # - Explicitly marked as [BLOCKER], OR
                # - No severity prefix (backward compatibility)
                blocker_count += 1
    
    return blocker_count > 0, blocker_count


def check_risks_table_for_non_low_risks(lines: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if the risks table has any risks that are not Low/Low.
    
    Args:
        lines: Document content as list of strings
    
    Returns:
        Tuple of (has_non_low_risks, list_of_risk_descriptions)
    """
    span = find_table_block(lines, "risks")
    
    if not span:
        # No risks table found - consider this as pass (no risks to check)
        return False, []
    
    start, end = span
    table_lines = lines[start:end]
    
    if len(table_lines) < 2:
        # Header only, no data rows
        return False, []
    
    # Skip header and separator rows
    data_rows = table_lines[2:]
    
    non_low_risks = []
    for row in data_rows:
        if not row.strip().startswith("|"):
            continue
        
        # Parse row cells
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        
        # Expected: | Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
        if len(cells) >= 4:
            description = cells[1].strip() if len(cells) > 1 else "Unknown"
            probability = cells[2].strip() if len(cells) > 2 else ""
            impact = cells[3].strip() if len(cells) > 3 else ""
            
            # Skip placeholder rows - check for empty, dash, or any placeholder-like content
            if not description or description == "-" or "placeholder" in description.lower():
                continue
            
            # Check if both probability and impact are "Low" (case-insensitive)
            if probability.lower() != "low" or impact.lower() != "low":
                non_low_risks.append(f"{description} (Probability: {probability}, Impact: {impact})")
    
    return len(non_low_risks) > 0, non_low_risks


def set_section_lock(lines: List[str], section_id: str, lock: bool) -> List[str]:
    """
    Set the section lock marker for a section.
    
    Args:
        lines: Document content as list of strings
        section_id: Section ID to lock/unlock
        lock: True to lock, False to unlock
    
    Returns:
        Updated document lines
    """
    spans = find_sections(lines)
    span = get_section_span(spans, section_id)
    
    if not span:
        # Section not found, return lines unchanged
        return lines
    
    lock_value = "true" if lock else "false"
    new_marker = f"<!-- section_lock:{section_id} lock={lock_value} -->"
    
    # Look for existing lock marker in the section
    lock_line_idx = None
    for i in range(span.start_line, span.end_line):
        m = SECTION_LOCK_RE.search(lines[i])
        if m and m.group("id") == section_id:
            lock_line_idx = i
            break
    
    new_lines = lines.copy()
    
    if lock_line_idx is not None:
        # Replace existing lock marker
        new_lines[lock_line_idx] = new_marker
    else:
        # Insert new lock marker at the end of the section (before the separator)
        # Find the last line before the next section or end
        insert_idx = span.end_line - 1
        
        # Move back to skip trailing empty lines and "---" separators
        while insert_idx > span.start_line and (
            new_lines[insert_idx].strip() == "" or new_lines[insert_idx].strip() == "---"
        ):
            insert_idx -= 1
        
        # Insert after the last content line
        new_lines.insert(insert_idx + 1, new_marker)
    
    return new_lines


def update_approval_record_table(
    lines: List[str], reviewer: str, status: str = "Approved"
) -> List[str]:
    """
    Update the approval record table with reviewer information and current date.
    
    Args:
        lines: Document content as list of strings
        reviewer: Name of the reviewer/approver
        status: Approval status (default: "Approved")
    
    Returns:
        Updated document lines
    """
    from datetime import datetime
    
    span = find_table_block(lines, "approval_record")
    
    if not span:
        # No approval record table found
        return lines
    
    start, end = span
    new_lines = lines.copy()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Update the table rows
    for i in range(start, end):
        line = new_lines[i]
        
        # Parse table row: | Field | Value |
        if not line.strip().startswith("|"):
            continue
            
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        
        field = cells[0].strip()
        
        # Update specific fields
        if field in ("Current Status", "Status"):
            cells[1] = status
            new_lines[i] = "| " + " | ".join(cells) + " |"
        elif field in ("Recommended By", "Reviewer"):
            cells[1] = reviewer
            new_lines[i] = "| " + " | ".join(cells) + " |"
        elif field in ("Recommendation Date", "Review Date"):
            cells[1] = today
            new_lines[i] = "| " + " | ".join(cells) + " |"
    
    return new_lines
