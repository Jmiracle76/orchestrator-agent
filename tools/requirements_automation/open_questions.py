from __future__ import annotations

import re
from typing import List, Tuple

from .config import OPEN_Q_COLUMNS, PLACEHOLDER_TOKEN
from .models import OpenQuestion
from .parsing import find_table_block


def parse_markdown_table(table_lines: List[str]) -> List[List[str]]:
    """Convert markdown table lines into a list of cell arrays."""
    rows: List[List[str]] = []
    for line in table_lines:
        if not line.lstrip().startswith("|"):
            continue
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def open_questions_parse(lines: List[str], table_id: str = "open_questions") -> Tuple[List[OpenQuestion], Tuple[int, int], List[str]]:
    """Parse an Open Questions table and return rows with its span.
    
    Args:
        lines: Document lines
        table_id: Table identifier to parse (default: "open_questions" for backward compatibility)
        
    Returns:
        Tuple of (questions, (start_line, end_line), header_columns)
    """
    span = find_table_block(lines, table_id)
    if not span:
        raise ValueError(
            f"Open Questions table not found (missing <!-- table:{table_id} --> or table)."
        )
    start, end = span
    rows = parse_markdown_table(lines[start:end])
    if len(rows) < 2:
        raise ValueError(f"Open Questions table malformed (missing header/separator) for table: {table_id}")
    # Validate the header row to ensure a stable schema.
    header = rows[0]
    if header != OPEN_Q_COLUMNS:
        raise ValueError(f"Open Questions header mismatch for table {table_id}. Expected {OPEN_Q_COLUMNS}, got {header}")
    qs: List[OpenQuestion] = []
    # Skip separator row and any malformed or placeholder rows.
    for r in rows[2:]:
        if len(r) != 6:
            continue
        if any(PLACEHOLDER_TOKEN in c for c in r):
            continue
        qs.append(OpenQuestion(r[0], r[1], r[2], r[3], r[4], r[5]))
    return qs, (start, end), header


def _norm(s: str) -> str:
    """Normalize strings for duplicate detection (case/space-insensitive)."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _is_placeholder_row(cells: List[str]) -> bool:
    """Return True if any cell contains the placeholder token."""
    return any(PLACEHOLDER_TOKEN in c for c in cells)


def _build_row(qid: str, question: str, date: str, answer: str, target: str, status: str) -> str:
    """Render a markdown table row for an Open Questions entry."""
    return f"| {qid} | {question} | {date} | {answer} | {target} | {status} |"


def open_questions_next_id(existing: List[OpenQuestion]) -> str:
    """Generate the next sequential Q-XXX identifier."""
    max_n = 0
    for q in existing:
        m = re.match(r"Q-(\d+)$", q.question_id.strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"Q-{max_n + 1:03d}"


def open_questions_insert(
    lines: List[str], new_questions: List[Tuple[str, str, str]], table_id: str = "open_questions"
) -> Tuple[List[str], int]:
    """Insert new questions, skipping duplicates, and return insert count.
    
    Args:
        lines: Document lines
        new_questions: List of (question_text, section_target, date) tuples
        table_id: Table identifier to insert into (default: "open_questions" for backward compatibility)
        
    Returns:
        Tuple of (updated_lines, insert_count)
    """
    existing, (start, end), _ = open_questions_parse(lines, table_id)
    existing_keys = {(_norm(q.question), _norm(q.section_target)) for q in existing}
    to_insert: List[str] = []
    inserted = 0
    for q_text, target, date in new_questions:
        key = (_norm(q_text), _norm(target))
        if key in existing_keys:
            continue
        qid = open_questions_next_id(existing)
        existing.append(OpenQuestion(qid, q_text, date, "", target, "Open"))
        to_insert.append(_build_row(qid, q_text, date, "", target, "Open"))
        existing_keys.add(key)
        inserted += 1
    if inserted == 0:
        return lines, 0
    table_lines = lines[start:end]
    table_lines = table_lines[:2] + to_insert + table_lines[2:]
    return lines[:start] + table_lines + lines[end:], inserted


def open_questions_resolve(lines: List[str], question_ids: List[str], table_id: str = "open_questions") -> Tuple[List[str], int]:
    """Mark matching question IDs as Resolved and return resolve count.
    
    Args:
        lines: Document lines
        question_ids: List of question IDs to resolve
        table_id: Table identifier to resolve in (default: "open_questions" for backward compatibility)
        
    Returns:
        Tuple of (updated_lines, resolve_count)
    """
    _, (start, end), _ = open_questions_parse(lines, table_id)
    qset = {q.strip() for q in question_ids}
    table_lines = lines[start:end]
    resolved = 0
    for i in range(2, len(table_lines)):
        line = table_lines[i]
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or _is_placeholder_row(cells):
            continue
        if cells[0].strip() in qset and cells[5].strip() != "Resolved":
            cells[5] = "Resolved"
            table_lines[i] = _build_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5])
            resolved += 1
    if resolved == 0:
        return lines, 0
    return lines[:start] + table_lines + lines[end:], resolved
