"""Per-section question management module.

This module provides functions for managing section-scoped question tables,
replacing the global Open Questions table with per-section Questions & Issues tables.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .config import PLACEHOLDER_TOKEN
from .models import OpenQuestion
from .parsing import find_table_block


def get_section_questions_table_name(section_id: str) -> str:
    """Return table marker name for section questions.

    Args:
        section_id: Section identifier (e.g., "problem_statement")

    Returns:
        Table name (e.g., "problem_statement_questions")
    """
    return f"{section_id}_questions"


def parse_section_questions(
    lines: List[str], section_id: str
) -> Tuple[List[OpenQuestion], Tuple[int, int]]:
    """Parse questions table for specific section.

    Args:
        lines: Document content as list of strings
        section_id: Section identifier

    Returns:
        Tuple of (questions_list, (start_line, end_line))

    Raises:
        ValueError: If table not found or malformed
    """
    table_name = get_section_questions_table_name(section_id)
    span = find_table_block(lines, table_name)

    if not span:
        raise ValueError(
            f"Section questions table not found for '{section_id}' "
            f"(missing <!-- table:{table_name} --> or table)."
        )

    start, end = span
    rows = _parse_markdown_table(lines[start:end])

    if len(rows) < 2:
        raise ValueError(
            f"Section questions table for '{section_id}' malformed (missing header/separator)."
        )

    # Expected header: Question ID | Question | Date | Answer | Status
    header = rows[0]
    expected_header = ["Question ID", "Question", "Date", "Answer", "Status"]

    if header != expected_header:
        raise ValueError(
            f"Section questions header mismatch for '{section_id}'. "
            f"Expected {expected_header}, got {header}"
        )

    qs: List[OpenQuestion] = []

    # Skip separator row and any malformed or placeholder rows
    for r in rows[2:]:
        if len(r) != 5:
            continue
        if any(PLACEHOLDER_TOKEN in c for c in r):
            continue

        # Create OpenQuestion with section_target set to section_id
        # for compatibility with existing code
        qs.append(
            OpenQuestion(
                question_id=r[0],
                question=r[1],
                date=r[2],
                answer=r[3],
                section_target=section_id,  # Implicit from table location
                status=r[4],
            )
        )

    return qs, (start, end)


def _parse_markdown_table(table_lines: List[str]) -> List[List[str]]:
    """Convert markdown table lines into a list of cell arrays."""
    rows: List[List[str]] = []
    for line in table_lines:
        if not line.lstrip().startswith("|"):
            continue
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _norm(s: str) -> str:
    """Normalize strings for duplicate detection (case/space-insensitive)."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _is_placeholder_row(cells: List[str]) -> bool:
    """Return True if any cell contains the placeholder token."""
    return any(PLACEHOLDER_TOKEN in c for c in cells)


def _build_section_question_row(
    qid: str, question: str, date: str, answer: str, status: str
) -> str:
    """Render a markdown table row for a section question entry."""
    return f"| {qid} | {question} | {date} | {answer} | {status} |"


def section_questions_next_id(section_id: str, existing: List[OpenQuestion]) -> str:
    """Generate the next sequential section-scoped question ID.

    Args:
        section_id: Section identifier
        existing: List of existing questions for this section

    Returns:
        Next question ID (e.g., "problem_statement-Q1")
    """
    prefix = f"{section_id}-Q"
    max_n = 0

    for q in existing:
        # Match section_id-QN pattern
        pattern = rf"^{re.escape(section_id)}-Q(\d+)$"
        m = re.match(pattern, q.question_id.strip())
        if m:
            max_n = max(max_n, int(m.group(1)))

    return f"{prefix}{max_n + 1}"


def insert_section_question(
    lines: List[str], section_id: str, question: str, date: str
) -> Tuple[List[str], str]:
    """Insert new question into section table.

    Args:
        lines: Document content as list of strings
        section_id: Section identifier
        question: Question text
        date: Date string

    Returns:
        Tuple of (updated_lines, question_id)

    Raises:
        ValueError: If table not found
    """
    existing, (start, end) = parse_section_questions(lines, section_id)

    # Check for duplicates
    existing_keys = {_norm(q.question) for q in existing}
    if _norm(question) in existing_keys:
        # Find existing question ID
        for q in existing:
            if _norm(q.question) == _norm(question):
                return lines, q.question_id

    # Generate new ID and create row
    qid = section_questions_next_id(section_id, existing)
    new_row = _build_section_question_row(qid, question, date, "", "Open")

    # Insert after header and separator
    table_lines = lines[start:end]
    table_lines = table_lines[:2] + [new_row] + table_lines[2:]

    return lines[:start] + table_lines + lines[end:], qid


def insert_section_questions_batch(
    lines: List[str], section_id: str, questions: List[Tuple[str, str]]
) -> Tuple[List[str], int]:
    """Insert multiple questions into section table, skipping duplicates.

    Args:
        lines: Document content as list of strings
        section_id: Section identifier
        questions: List of (question_text, date) tuples

    Returns:
        Tuple of (updated_lines, insertion_count)
    """
    existing, (start, end) = parse_section_questions(lines, section_id)

    # Track existing questions
    existing_keys = {_norm(q.question) for q in existing}
    to_insert: List[str] = []
    inserted = 0

    for q_text, date in questions:
        key = _norm(q_text)
        if key in existing_keys:
            continue

        qid = section_questions_next_id(section_id, existing)
        existing.append(OpenQuestion(qid, q_text, date, "", section_id, "Open"))
        to_insert.append(_build_section_question_row(qid, q_text, date, "", "Open"))
        existing_keys.add(key)
        inserted += 1

    if inserted == 0:
        return lines, 0

    # Insert all new questions after header and separator
    table_lines = lines[start:end]
    table_lines = table_lines[:2] + to_insert + table_lines[2:]

    return lines[:start] + table_lines + lines[end:], inserted


def resolve_section_question(
    lines: List[str], section_id: str, question_id: str
) -> Tuple[List[str], bool]:
    """Mark question as Resolved in section table.

    Args:
        lines: Document content as list of strings
        section_id: Section identifier
        question_id: Question ID to resolve

    Returns:
        Tuple of (updated_lines, was_resolved)
    """
    _, (start, end) = parse_section_questions(lines, section_id)

    table_lines = lines[start:end]
    resolved = False

    for i in range(2, len(table_lines)):
        line = table_lines[i]
        if not line.lstrip().startswith("|"):
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or _is_placeholder_row(cells):
            continue

        if cells[0].strip() == question_id.strip() and cells[4].strip() != "Resolved":
            cells[4] = "Resolved"
            table_lines[i] = _build_section_question_row(
                cells[0], cells[1], cells[2], cells[3], cells[4]
            )
            resolved = True
            break

    if not resolved:
        return lines, False

    return lines[:start] + table_lines + lines[end:], True


def resolve_section_questions_batch(
    lines: List[str], section_id: str, question_ids: List[str]
) -> Tuple[List[str], int]:
    """Mark multiple questions as Resolved in section table.

    Args:
        lines: Document content as list of strings
        section_id: Section identifier
        question_ids: List of question IDs to resolve

    Returns:
        Tuple of (updated_lines, resolve_count)
    """
    _, (start, end) = parse_section_questions(lines, section_id)

    qset = {q.strip() for q in question_ids}
    table_lines = lines[start:end]
    resolved = 0

    for i in range(2, len(table_lines)):
        line = table_lines[i]
        if not line.lstrip().startswith("|"):
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or _is_placeholder_row(cells):
            continue

        if cells[0].strip() in qset and cells[4].strip() != "Resolved":
            cells[4] = "Resolved"
            table_lines[i] = _build_section_question_row(
                cells[0], cells[1], cells[2], cells[3], cells[4]
            )
            resolved += 1

    if resolved == 0:
        return lines, 0

    return lines[:start] + table_lines + lines[end:], resolved


def has_open_section_questions(lines: List[str], section_id: str) -> bool:
    """Check if section has any open questions.

    Args:
        lines: Document content as list of strings
        section_id: Section identifier

    Returns:
        True if section has open questions, False otherwise
    """
    try:
        questions, _ = parse_section_questions(lines, section_id)
        return any(q.status.strip() == "Open" for q in questions)
    except ValueError:
        # Table not found or malformed
        return False


def section_has_answered_questions(lines: List[str], section_id: str) -> bool:
    """Check if section has any answered questions (Open/Deferred with answers).

    Args:
        lines: Document content as list of strings
        section_id: Section identifier

    Returns:
        True if section has answered questions, False otherwise
    """
    try:
        questions, _ = parse_section_questions(lines, section_id)
        return any(
            q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
            for q in questions
        )
    except ValueError:
        # Table not found or malformed
        return False
