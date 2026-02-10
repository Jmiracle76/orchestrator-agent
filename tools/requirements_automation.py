#!/usr/bin/env python3
"""
requirements_automation.py

Functional Phase 1 (Intent & Scope) automation for docs/requirements.md.

What it does (Phase 1):
- Ensure docs/requirements.md exists (copy from docs/templates/requirements-template.md if missing)
- Validate minimal structure (markers exist)
- For each Phase 1 section in order:
  - Skip if locked
  - If section is blank -> ask LLM for Open Questions and insert them deterministically
  - If answers exist targeting this section -> ask LLM to integrate answers into section and mark those questions Resolved
  - (Human-modified review is stubbed until provenance is implemented)

Open Questions table contract (immutable schema):
| Question ID | Question | Date | Answer | Section Target | Resolution Status |

Important:
- Automation owns the Open Questions table mechanics (IDs, schema, resolve status)
- LLM never edits tables directly; it returns JSON instructions only
- Git is safety net: optional auto-commit/push
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def extract_json_object(text: str) -> str:
    """Extract a JSON object from LLM output.

    Handles common cases:
    - Raw JSON: { ... }
    - Fenced JSON: ```json\n{...}\n```
    - Fenced generic: ```\n{...}\n```

    Returns a JSON string safe for json.loads().
    Raises ValueError if no JSON object can be found.
    """
    t = (text or "").strip()

    # Strip markdown fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # Already looks like JSON
    if t.startswith("{") and t.endswith("}"):
        return t

    # Fallback: slice from first { to last }
    first = t.find("{")
    last = t.rfind("}")
    if first != -1 and last != -1 and last > first:
        return t[first:last + 1].strip()

    raise ValueError("No JSON object found in LLM output")


# -----------------------------
# Configuration
# -----------------------------

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "docs" / "templates" / "requirements-template.md"
DEFAULT_DOC = REPO_ROOT / "docs" / "requirements.md"

PHASES: Dict[str, List[str]] = {
    # Phase 1: Intent & scope
    "phase_1_intent_scope": [
        "problem_statement",
        "goals_objectives",
        "stakeholders_users",
        "success_criteria",
    ],
    # Phase 2: Assumptions & constraints
    "phase_2_assumptions_constraints": [
        "assumptions",
        "constraints",
    ],
}

# Execute phases in this order; we run ONLY the first incomplete phase each run.
PHASE_ORDER = [
    "phase_1_intent_scope",
    "phase_2_assumptions_constraints",
]


# Open Questions may sometimes (incorrectly) target subsection IDs.
# Phase 1 only edits whole sections, so we coerce known subsection targets
# back to their owning section.
TARGET_CANONICAL_MAP: Dict[str, str] = {
    # Goals & objectives subsections
    "primary_goals": "goals_objectives",
    "secondary_goals": "goals_objectives",
    "non_goals": "goals_objectives",
}

# Markers
SECTION_MARKER_RE = re.compile(r"<!--\s*section:(?P<id>[a-z0-9_]+)\s*-->")
SECTION_LOCK_RE   = re.compile(r"<!--\s*section_lock:(?P<id>[a-z0-9_]+)\s+lock=(?P<lock>true|false)\s*-->")
TABLE_MARKER_RE   = re.compile(r"<!--\s*table:(?P<id>[a-z0-9_]+)\s*-->")
SUBSECTION_MARKER_RE = re.compile(r"<!--\s*subsection:(?P<id>[a-z0-9_]+)\s*-->")
PLACEHOLDER_TOKEN = "<!-- PLACEHOLDER -->"

OPEN_Q_COLUMNS = [
    "Question ID",
    "Question",
    "Date",
    "Answer",
    "Section Target",
    "Resolution Status",
]


# -----------------------------
# Data models
# -----------------------------

@dataclasses.dataclass(frozen=True)
class SectionSpan:
    section_id: str
    start_line: int
    end_line: int


@dataclasses.dataclass
class OpenQuestion:
    question_id: str
    question: str
    date: str
    answer: str
    section_target: str
    status: str  # Open | Resolved | Deferred


@dataclasses.dataclass
class RunResult:
    outcome: str  # no-op | updated | blocked | error
    changed: bool
    blocked_reasons: List[str]


# -----------------------------
# Utilities
# -----------------------------

def iso_today() -> str:
    return dt.date.today().isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def backup_file(path: Path) -> Path:
    """
    Create a timestamped backup copy of the requirements doc *outside* the git repo.

    Why: backups inside the repo show up as modified/untracked files and break the
    'only docs/requirements.md may change' commit allowlist.
    """
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_root = Path(os.getenv("TMPDIR", "/tmp")) / "requirements_automation_backups"
    tmp_root.mkdir(parents=True, exist_ok=True)
    backup_path = tmp_root / f"{path.name}.{ts}.bak"
    shutil.copy2(path, backup_path)
    return backup_path



# -----------------------------
# Automation-owned updates: meta, document control, version history
# -----------------------------

AUTOMATION_ACTOR = "requirements-automation"

def _find_meta_value_line(lines: List[str], meta_id: str) -> Optional[int]:
    """Return index of the line immediately following <!-- meta:<id> --> marker."""
    marker = re.compile(rf"<!--\s*meta:{re.escape(meta_id)}\s*-->")
    for i, ln in enumerate(lines):
        if marker.search(ln):
            # next non-empty line is the value line
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            return j if j < len(lines) else None
    return None

def _set_meta_field(lines: List[str], meta_id: str, new_value_line: str) -> Tuple[List[str], bool]:
    idx = _find_meta_value_line(lines, meta_id)
    if idx is None:
        return lines, False
    if lines[idx].rstrip() == new_value_line.rstrip():
        return lines, False
    lines = list(lines)
    lines[idx] = new_value_line
    return lines, True

def _find_table_span_by_marker(lines: List[str], table_id: str) -> Optional[Tuple[int, int]]:
    span = find_table_block(lines, table_id)
    return span

def _update_document_control_table(lines: List[str], version: str, today: str) -> Tuple[List[str], bool]:
    """Update table:document_control fields we own."""
    span = _find_table_span_by_marker(lines, "document_control")
    if not span:
        return lines, False
    start, end = span
    table_lines = lines[start:end]
    rows = parse_markdown_table(table_lines)
    if len(rows) < 2:
        return lines, False

    changed = False
    # Rebuild table_lines in-place by editing only known fields
    for i in range(2, len(rows)):  # data rows only
        r = rows[i]
        if len(r) < 2:
            continue
        field = r[0].strip()
        if field == "Current Version":
            if r[1].strip() != version:
                r[1] = version; changed = True
        elif field == "Last Modified":
            if r[1].strip() != today:
                r[1] = today; changed = True
        elif field == "Modified By":
            if r[1].strip() != AUTOMATION_ACTOR:
                r[1] = AUTOMATION_ACTOR; changed = True
        # Leave statuses/approval fields for you/humans for now.

    if not changed:
        return lines, False

    # Re-emit table lines (preserving original header/separator lines)
    new_table_lines: List[str] = []
    new_table_lines.append(table_lines[0])  # header row (as-is)
    new_table_lines.append(table_lines[1])  # separator (as-is)
    for i in range(2, len(rows)):
        # Try to preserve original formatting width? Not worth it. Deterministic output is better.
        new_table_lines.append("| " + " | ".join(rows[i]) + " |")
    return lines[:start] + new_table_lines + lines[end:], True

def _parse_version(v: str) -> Tuple[int, int]:
    m = re.match(r"^(\d+)\.(\d+)$", v.strip())
    if not m:
        return (0, 0)
    return int(m.group(1)), int(m.group(2))

def _format_version(major: int, minor: int) -> str:
    return f"{major}.{minor}"

def _increment_minor(v: str) -> str:
    major, minor = _parse_version(v)
    return _format_version(major, minor + 1)

def _get_current_version(lines: List[str]) -> str:
    idx = _find_meta_value_line(lines, "version")
    if idx is None:
        return "0.0"
    m = re.search(r"\*\*Version:\*\*\s*([0-9]+\.[0-9]+)", lines[idx])
    return m.group(1) if m else "0.0"

def _upsert_version_history_row(lines: List[str], version: str, today: str, summary: str) -> Tuple[List[str], bool]:
    """Insert a new Version History row at top of the table, replacing template placeholder row if present."""
    # Find the '### Version History' heading
    vh_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == "### Version History":
            vh_idx = i
            break
    if vh_idx is None:
        return lines, False

    # Find first table row after heading
    start = None
    for j in range(vh_idx + 1, len(lines)):
        if lines[j].lstrip().startswith("|"):
            start = j
            break
        if SECTION_MARKER_RE.search(lines[j]):  # next section before table
            return lines, False
    if start is None:
        return lines, False

    end = start
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1

    table_lines = lines[start:end]
    rows = parse_markdown_table(table_lines)
    if len(rows) < 2:
        return lines, False

    # Build new row
    new_row = [version, today, AUTOMATION_ACTOR, summary]

    # Remove placeholder data rows (rows[2:] that are empty or placeholder)
    data = rows[2:] if len(rows) > 2 else []
    cleaned = []
    for r in data:
        if len(r) != 4:
            continue
        if any(PLACEHOLDER_TOKEN in c for c in r):
            continue
        if all(c.strip() in ("", "-", "Pending") for c in r):
            continue
        cleaned.append(r)

    # Avoid inserting duplicate consecutive entry (same version+date+summary)
    if cleaned:
        top = cleaned[0]
        if top[0].strip() == version and top[1].strip() == today and top[3].strip() == summary.strip():
            return lines, False

    new_rows = [rows[0], rows[1], new_row] + cleaned
    # Emit
    new_table_lines = [
        "| " + " | ".join(new_rows[0]) + " |",
        "|" + "|".join(["---------"] * len(new_rows[0])) + "|",
    ]
    for r in new_rows[2:]:
        new_table_lines.append("| " + " | ".join(r) + " |")

    return lines[:start] + new_table_lines + lines[end:], True

def update_automation_owned_fields(
    lines_before: List[str],
    lines_after: List[str],
    *,
    doc_created: bool,
    phase_completed_this_run: bool,
    change_summaries: List[str],
) -> Tuple[List[str], bool]:
    """Update meta/version/date + document control + version history, deterministically."""
    today = iso_today()
    changed = False
    lines = list(lines_after)

    # Decide version bump
    current_version = _get_current_version(lines_before if lines_before else lines)
    new_version = current_version

    if doc_created and current_version == "0.0":
        new_version = "0.1"
    elif phase_completed_this_run:
        new_version = _increment_minor(current_version)

    # Update meta fields
    if new_version != current_version:
        lines, did = _set_meta_field(lines, "version", f"- **Version:** {new_version} ")
        changed = changed or did

    # Always update last_updated if anything changed in doc content OR version bumped
    if change_summaries or (new_version != current_version) or doc_created:
        lines, did = _set_meta_field(lines, "last_updated", f"- **Last Updated:** {today} ")
        changed = changed or did

    # Update document control table (version/last modified/modified by)
    lines, did = _update_document_control_table(lines, new_version, today)
    changed = changed or did

    # Version history row
    if change_summaries or (new_version != current_version) or doc_created:
        summary = "; ".join(change_summaries) if change_summaries else "Automation run"
        lines, did = _upsert_version_history_row(lines, new_version, today, summary)
        changed = changed or did

    return lines, changed

def split_lines(doc: str) -> List[str]:
    return doc.splitlines()


def join_lines(lines: List[str]) -> str:
    return "\n".join(lines) + "\n"


# -----------------------------
# Git helpers (optional safety net)
# -----------------------------

def git_status_porcelain(repo_root: Path) -> str:
    return subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root).decode()


def is_working_tree_clean(repo_root: Path) -> bool:
    return not git_status_porcelain(repo_root).strip()


def get_modified_files(repo_root: Path) -> List[str]:
    status = git_status_porcelain(repo_root)
    files: List[str] = []
    for line in status.strip().splitlines():
        if not line.strip():
            continue
        rest = line[2:].strip()
        if " -> " in rest:
            rest = rest.split(" -> ")[-1]
        files.append(str(Path(rest).as_posix()))
    return files


def commit_and_push(repo_root: Path, commit_message: str, allow_files: List[str]) -> None:
    modified = get_modified_files(repo_root)
    if not modified:
        return
    unexpected = [f for f in modified if f not in allow_files]
    if unexpected:
        raise RuntimeError(f"Unexpected files modified: {unexpected}. Allowed: {allow_files}")

    for f in allow_files:
        subprocess.check_call(["git", "add", f], cwd=repo_root)

    subprocess.check_call(["git", "commit", "-m", commit_message], cwd=repo_root)
    subprocess.check_call(["git", "push"], cwd=repo_root)


# -----------------------------
# Document parsing (sections)
# -----------------------------

def find_sections(lines: List[str]) -> List[SectionSpan]:
    section_starts: List[Tuple[str, int]] = []
    for i, line in enumerate(lines):
        m = SECTION_MARKER_RE.search(line)
        if m:
            section_starts.append((m.group("id"), i))

    spans: List[SectionSpan] = []
    for idx, (sid, start) in enumerate(section_starts):
        end = section_starts[idx + 1][1] if idx + 1 < len(section_starts) else len(lines)
        spans.append(SectionSpan(section_id=sid, start_line=start, end_line=end))
    return spans


def get_section_span(spans: List[SectionSpan], section_id: str) -> Optional[SectionSpan]:
    for s in spans:
        if s.section_id == section_id:
            return s
    return None



def validate_required_section_spans(lines: List[str], required_ids: List[str]) -> List[str]:
    """
    Validate basic section span integrity for the given section ids.
    We don't try to auto-repair here; we just report issues so the run can be blocked
    instead of corrupting the document.
    """
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

        # Ensure no nested section marker inside span (other than the first line).
        inner = "\n".join(lines[sp.start_line + 1:sp.end_line])
        if SECTION_MARKER_RE.search(inner):
            issues.append(f"Section {sid} span contains another <!-- section:... --> marker (nested/corrupt).")

        # If there's a lock tag, it should be within the span (this is a warning, not fatal).
        # (We don't require it, but corruption often moves it outside.)
        if SECTION_LOCK_RE.search(inner) is None and any(SECTION_LOCK_RE.search(ln) for ln in lines):
            # leave as info-level issue
            pass

    return issues

def section_text(lines: List[str], span: SectionSpan) -> str:
    return "\n".join(lines[span.start_line:span.end_line])


def section_body(lines: List[str], span: SectionSpan) -> str:
    """Return the section *data-plane* text only.

    Strips control-plane markers and headings:
    - <!-- section:... -->
    - markdown headers (##, ### ...)
    - <!-- section_lock:... -->
    - '---' divider lines

    This keeps the LLM focused on editable content, and prevents it from
    "learning" and regurgitating markers.
    """
    block = lines[span.start_line:span.end_line]
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
    # Trim leading/trailing blank lines
    text = "\n".join(body).strip("\n")
    return text


def section_is_locked(lines: List[str], span: SectionSpan) -> bool:
    block = section_text(lines, span)
    locks = list(SECTION_LOCK_RE.finditer(block))
    if not locks:
        return False
    return locks[-1].group("lock") == "true"


def section_is_blank(lines: List[str], span: SectionSpan) -> bool:
    return PLACEHOLDER_TOKEN in section_text(lines, span)


# -----------------------------
# Table parsing: Open Questions
# -----------------------------

def find_table_block(lines: List[str], table_id: str) -> Optional[Tuple[int, int]]:
    marker_line = None
    for i, line in enumerate(lines):
        m = TABLE_MARKER_RE.search(line)
        if m and m.group("id") == table_id:
            marker_line = i
            break
    if marker_line is None:
        return None

    start = None
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


def parse_markdown_table(table_lines: List[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in table_lines:
        if not line.lstrip().startswith("|"):
            continue
        parts = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(parts)
    return rows


def open_questions_parse(lines: List[str]) -> Tuple[List[OpenQuestion], Tuple[int, int], List[str]]:
    span = find_table_block(lines, "open_questions")
    if not span:
        raise ValueError("Open Questions table not found (missing <!-- table:open_questions --> or table).")

    start, end = span
    table_lines = lines[start:end]
    rows = parse_markdown_table(table_lines)

    if len(rows) < 2:
        raise ValueError("Open Questions table malformed (missing header/separator).")

    header = rows[0]
    if header != OPEN_Q_COLUMNS:
        raise ValueError(f"Open Questions header mismatch. Expected {OPEN_Q_COLUMNS}, got {header}")

    data_rows = rows[2:] if len(rows) > 2 else []
    questions: List[OpenQuestion] = []
    for r in data_rows:
        if len(r) != 6:
            continue
        if any(PLACEHOLDER_TOKEN in cell for cell in r):
            continue
        questions.append(OpenQuestion(
            question_id=r[0],
            question=r[1],
            date=r[2],
            answer=r[3],
            section_target=r[4],
            status=r[5],
        ))

    return questions, (start, end), header


def open_questions_next_id(existing: List[OpenQuestion]) -> str:
    max_n = 0
    for q in existing:
        m = re.match(r"Q-(\d+)$", q.question_id.strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"Q-{max_n + 1:03d}"


# -----------------------------
# Open Questions: INSERT + SET ANSWER + RESOLVE
# -----------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _is_placeholder_row(cells: List[str]) -> bool:
    return any(PLACEHOLDER_TOKEN in c for c in cells)


def _build_open_q_row(qid: str, question: str, date: str, answer: str, target: str, status: str) -> str:
    # Keep exactly 6 columns.
    return f"| {qid} | {question} | {date} | {answer} | {target} | {status} |"


def open_questions_insert(lines: List[str], new_questions: List[Tuple[str, str, str]]) -> Tuple[List[str], int]:
    """
    new_questions: [(question_text, section_target, date_iso), ...]
    - assigns IDs (Q-###)
    - dedupes by (question_text, section_target) normalized
    - inserts after header+separator
    """
    existing, (start, end), header = open_questions_parse(lines)
    if header != OPEN_Q_COLUMNS:
        raise ValueError(f"Open Questions header mismatch. Expected {OPEN_Q_COLUMNS}, got {header}")

    existing_keys = {(_norm(q.question), _norm(q.section_target)) for q in existing}

    to_insert: List[str] = []
    inserted = 0
    for q_text, target, date in new_questions:
        key = (_norm(q_text), _norm(target))
        if key in existing_keys:
            continue
        qid = open_questions_next_id(existing)
        existing.append(OpenQuestion(qid, q_text, date, "", target, "Open"))
        to_insert.append(_build_open_q_row(qid, q_text, date, "", target, "Open"))
        existing_keys.add(key)
        inserted += 1

    if inserted == 0:
        return lines, 0

    table_lines = lines[start:end]
    table_lines = table_lines[:2] + to_insert + table_lines[2:]  # after header+separator
    return lines[:start] + table_lines + lines[end:], inserted




# Backwards-compatible alias used by some phase processors
def insert_open_questions(lines: List[str], new_questions: List[Tuple[str, str, str]]) -> Tuple[List[str], int]:
    """Alias for open_questions_insert."""
    return open_questions_insert(lines, new_questions)
def open_questions_set_answer(
    lines: List[str],
    question_id: str,
    answer: str,
    date: Optional[str] = None,
    keep_status: bool = True,
) -> Tuple[List[str], bool]:
    """
    Set Answer for a specific Question ID. Optionally updates Date.
    """
    _, (start, end), header = open_questions_parse(lines)
    if header != OPEN_Q_COLUMNS:
        raise ValueError(f"Open Questions header mismatch. Expected {OPEN_Q_COLUMNS}, got {header}")

    table_lines = lines[start:end]
    changed = False

    for i in range(2, len(table_lines)):
        line = table_lines[i]
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        if _is_placeholder_row(cells):
            continue
        if cells[0].strip() == question_id:
            new_answer = answer.strip()
            if cells[3].strip() != new_answer:
                cells[3] = new_answer
                changed = True
            if date is not None and cells[2].strip() != date.strip():
                cells[2] = date.strip()
                changed = True
            # keep_status means leave cells[5] alone
            table_lines[i] = _build_open_q_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5])
            break

    if not changed:
        return lines, False

    return lines[:start] + table_lines + lines[end:], True


def open_questions_resolve(lines: List[str], question_ids: List[str]) -> Tuple[List[str], int]:
    """
    Mark Resolution Status = Resolved for each question_id.
    """
    _, (start, end), header = open_questions_parse(lines)
    if header != OPEN_Q_COLUMNS:
        raise ValueError(f"Open Questions header mismatch. Expected {OPEN_Q_COLUMNS}, got {header}")

    qset = {q.strip() for q in question_ids}
    table_lines = lines[start:end]
    resolved = 0

    for i in range(2, len(table_lines)):
        line = table_lines[i]
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        if _is_placeholder_row(cells):
            continue
        if cells[0].strip() in qset and cells[5].strip() != "Resolved":
            cells[5] = "Resolved"
            table_lines[i] = _build_open_q_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5])
            resolved += 1

    if resolved == 0:
        return lines, 0

    return lines[:start] + table_lines + lines[end:], resolved


# -----------------------------
# LLM Client (Anthropic-backed, JSON-only outputs)
# -----------------------------

class LLMClient:
    """
    Anthropic-backed client with strict JSON outputs.

    Two operations used in Phase 1:
    - generate_open_questions(section_id, context) -> list of {question, section_target, rationale}
    - integrate_answers(section_id, context, answered_questions) -> new body text (data-plane only)
    """

    def __init__(self, model: str = MODEL, max_tokens: int = MAX_TOKENS) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = self._make_client()

    @staticmethod
    def _make_client():
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("anthropic package not installed (pip install anthropic)") from e
        return Anthropic()

    def _call(self, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    def generate_open_questions(self, section_id: str, section_context: str) -> List[dict]:
        prompt = f"""
You are a requirements assistant. Produce ONLY valid JSON.

TASK:
Generate clarifying questions needed to fill the section "{section_id}".

RULES:
- Do NOT edit the document.
- Do NOT include markdown tables.
- Output JSON with this exact shape:

{{
  "questions": [
    {{
      "question": "string",
      "section_target": "string (must be a valid section id, default to {section_id})",
      "rationale": "string (short)"
    }}
  ]
}}

CONTEXT (current section text):
\"\"\"{section_context}\"\"\"

Return JSON only. No prose.
"""
        raw = self._call(prompt).strip()
        try:
            payload = extract_json_object(raw)
            data = json.loads(payload)
        except Exception as e:
            raise RuntimeError(f"LLM returned non-JSON for generate_open_questions: {raw[:400]}") from e

        questions = data.get("questions", [])
        if not isinstance(questions, list):
            return []
        cleaned: List[dict] = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            qt = (q.get("question") or "").strip()
            st = (q.get("section_target") or section_id).strip()
            rat = (q.get("rationale") or "").strip()
            if qt:
                cleaned.append({"question": qt, "section_target": st, "rationale": rat})
        return cleaned

    def integrate_answers(self, section_id: str, section_context: str, answered_questions: List[OpenQuestion]) -> str:
        qa = "\n".join(
            f"- {q.question_id}: {q.question}\n  Answer: {q.answer}"
            for q in answered_questions
        )
        prompt = f"""
You are a requirements assistant.

TASK:
Integrate the provided Q&A into section "{section_id}".
Return ONLY the updated section body text (data-plane). No markers, no section headers, no lock tags.

RULES:
- Keep it crisp and requirements-style.
- Remove placeholder wording.
- If answers conflict, do NOT guess: add a short "Open issues" note at end describing the conflict (do not create table rows).

CURRENT SECTION TEXT:
\"\"\"{section_context}\"\"\"

ANSWERED QUESTIONS:
{qa}

Return updated body text only.
"""
        return self._call(prompt).strip()

    def review_and_revise(self, section_id: str, section_context: str) -> str:
        prompt = f"""
You are a requirements assistant.

TASK:
Review and improve section "{section_id}" for clarity and completeness.
Return ONLY revised section body text (data-plane). No headers, no markers.

CURRENT SECTION TEXT:
\"\"\"{section_context}\"\"\"
"""
        return self._call(prompt).strip()


# -----------------------------
# Structural integrity (minimal)
# -----------------------------

def validate_and_repair_structure(lines: List[str]) -> Tuple[List[str], bool, List[str]]:
    """
    Validate + (lightly) repair control-plane structure.

    Repair policy (Phase 1):
    - If a required section marker is missing but the corresponding numbered heading exists,
      re-insert the marker immediately above that heading.
    - If section_lock references a missing section marker, warn (and the insertion above should fix most cases).
    """
    changed = False
    notes: List[str] = []

    # --- Auto-repair missing section markers (based on numbered headings) ---
    expected_heading_to_id = {
        "## 2. Problem Statement": "problem_statement",
        "## 3. Goals and Objectives": "goals_objectives",
        "## 4. Stakeholders and Users": "stakeholders_users",
        "## 11. Success Criteria and Acceptance": "success_criteria",
        "## 12. Out of Scope": "out_of_scope",
        "## 1. Document Control": "document_control",
        "## 10. Risks and Open Issues": "risks_open_issues",
        "## 5. Assumptions": "assumptions",
        "## 6. Constraints": "constraints",
    }

    # Compute known section markers
    spans = find_sections(lines)
    present = {s.section_id for s in spans}

    for heading, sid in expected_heading_to_id.items():
        if sid in present:
            continue
        # Find heading line
        for i, ln in enumerate(lines):
            if ln.strip() == heading:
                # Insert marker above heading, unless marker already exists very near
                insert_at = i
                # If previous line is already some marker, insert above it to keep marker->heading adjacency
                if i > 0 and lines[i-1].strip().startswith("<!--") and "section:" in lines[i-1]:
                    break
                marker = f"<!-- section:{sid} -->"
                lines.insert(insert_at, marker)
                notes.append(f"Repaired missing section marker for {sid} above heading '{heading}' (line {i+1}).")
                changed = True
                # Refresh present set so we don't double-insert
                present.add(sid)
                break

    # Recompute spans after potential insertions
    spans = find_sections(lines)
    known_sections = {s.section_id for s in spans}

    # --- Orphan lock warnings ---
    for i, line in enumerate(lines):
        m = SECTION_LOCK_RE.search(line)
        if m and m.group("id") not in known_sections:
            notes.append(f"Orphan section_lock at line {i+1}: {m.group('id')}")

    return lines, changed, notes


# -----------------------------
# Section editing helpers
# -----------------------------

def sanitize_llm_body(section_id: str, body: str) -> str:
    """
    Defensive sanitization of model output before it touches the doc.
    - Strip section/table/lock markers, horizontal rules, and stray headers.
    - Apply section-specific guardrails to reduce cross-section contamination.
    - Light de-duplication for list-style sections (notably assumptions).
    """
    if not body:
        return ""

    lines = body.splitlines()

    # 1) Drop any automation markers or obvious document structure tokens.
    cleaned: List[str] = []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            cleaned.append("")
            continue
        if SECTION_MARKER_RE.search(s) or SECTION_LOCK_RE.search(s) or TABLE_MARKER_RE.search(s):
            continue
        if s.strip() == "---":
            continue
        if s.strip().startswith("<!--") and s.strip().endswith("-->"):
            continue
        # prevent the model from injecting new top-level headers
        if s.lstrip().startswith("#"):
            continue
        cleaned.append(s)

    # 2) Section-specific filtering.
    if section_id == "assumptions":
        # Assumptions should be a flat list, not a mini novel with subsections.
        keep: List[str] = []
        for s in cleaned:
            st = s.strip()
            if not st:
                keep.append("")
                continue
            if st.startswith("###") or st.startswith("##"):
                continue
            # If the model tries to paste constraints subheads here, drop them.
            if re.match(r"(?i)^technical constraints|^operational constraints|^resource constraints", st):
                continue
            keep.append(s)

        # De-dupe list items (case/whitespace-insensitive).
        seen = set()
        deduped: List[str] = []
        for s in keep:
            st = s.strip()
            if not st:
                # compress blank lines later
                deduped.append("")
                continue
            norm = re.sub(r"\s+", " ", re.sub(r"^[\-\*\d]+\.\s*", "", st)).strip().lower()
            if norm in seen:
                continue
            seen.add(norm)
            deduped.append(s)

        cleaned = deduped

    elif section_id == "constraints":
        # Constraints section supports specific subsections. Keep only those headings.
        allowed_heads = {
            "### Technical Constraints",
            "### Operational Constraints",
            "### Resource Constraints",
        }
        keep: List[str] = []
        for s in cleaned:
            st = s.strip()
            if not st:
                keep.append("")
                continue
            if st.startswith("###"):
                if st in allowed_heads:
                    keep.append(st)
                # drop any other ### headings
                continue
            if st.startswith("##"):
                continue
            keep.append(s)
        cleaned = keep

    # 3) Trim leading/trailing blank lines and collapse runs of blanks.
    out: List[str] = []
    blank_run = 0
    for s in cleaned:
        if not s.strip():
            blank_run += 1
            if blank_run > 1:
                continue
            out.append("")
        else:
            blank_run = 0
            out.append(s)

    # Trim edges
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()

    return "\n".join(out).strip()

def find_subsections_within(lines: List[str], section_span: SectionSpan) -> List[SubsectionSpan]:
    """Find <!-- subsection:<id> --> markers inside a section span."""
    starts: List[Tuple[str, int]] = []
    for i in range(section_span.start_line, section_span.end_line):
        m = SUBSECTION_MARKER_RE.search(lines[i])
        if m:
            starts.append((m.group("id"), i))
    subs: List[SubsectionSpan] = []
    for idx, (sid, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else section_span.end_line
        subs.append(SubsectionSpan(subsection_id=sid, start_line=start, end_line=end))
    return subs

def get_subsection_span(subs: List[SubsectionSpan], subsection_id: str) -> Optional[SubsectionSpan]:
    for s in subs:
        if s.subsection_id == subsection_id:
            return s
    return None

def replace_block_body_preserving_markers(lines: List[str], start: int, end: int, new_body: str) -> List[str]:
    """
    Replace the *content* of a block while preserving:
    - the first line (marker)
    - the first heading line (## or ###) if present
    - any trailing section_lock line(s) inside the block
    - an ending '---' divider if present at the end of the original block
    """
    block_lines = lines[start:end]
    if not block_lines:
        return lines

    marker_line = block_lines[0]
    heading_line = None
    for ln in block_lines[1:8]:
        if ln.lstrip().startswith("## ") or ln.lstrip().startswith("### "):
            heading_line = ln
            break

    lock_lines = [ln for ln in block_lines if SECTION_LOCK_RE.search(ln)]
    keep_divider = ("---" in block_lines[-3:])

    new_block: List[str] = [marker_line]
    if heading_line:
        new_block.append(heading_line)

    body_clean = sanitize_llm_body("block", new_body)
    if body_clean:
        new_block.extend(split_lines(body_clean))
    else:
        new_block.append(PLACEHOLDER_TOKEN)

    if lock_lines:
        new_block.append(lock_lines[-1])
    if keep_divider:
        new_block.append("---")

    return lines[:start] + new_block + lines[end:]

def replace_section_data_plane(lines: List[str], span: SectionSpan, new_body: str) -> List[str]:
    block_lines = lines[span.start_line:span.end_line]

    heading = None
    for ln in block_lines:
        if ln.lstrip().startswith("## "):
            heading = ln
            break

    new_block: List[str] = [block_lines[0]]
    if heading:
        new_block.append(heading)

    body_lines = split_lines(new_body.strip())
    if body_lines:
        new_block.extend(body_lines)
    else:
        new_block.append(PLACEHOLDER_TOKEN)

    lock_lines = [ln for ln in block_lines if SECTION_LOCK_RE.search(ln)]
    if lock_lines:
        new_block.append(lock_lines[-1])

    if "---" in block_lines[-3:]:
        new_block.append("---")

    return lines[:span.start_line] + new_block + lines[span.end_line:]


# -----------------------------
# Phase 1 processing
# -----------------------------

def process_phase_1(
    lines: List[str],
    llm: LLMClient,
    dry_run: bool,
) -> Tuple[List[str], bool, List[str], bool, List[str]]:
    changed = False
    blocked: List[str] = []
    needs_human_input = False
    change_summaries: List[str] = []

    spans = find_sections(lines)

    # Parse Open Questions
    open_qs, _, _ = open_questions_parse(lines)

    revised_sections: Dict[str, int] = {sid: 0 for sid in PHASES["phase_1_intent_scope"]}

    for section_id in PHASES["phase_1_intent_scope"]:
        span = get_section_span(spans, section_id)
        if not span:
            blocked.append(f"Missing required section marker: {section_id}")
            continue

        if section_is_locked(lines, span):
            logging.info("Section locked, skipping edits: %s", section_id)
            continue

        blank = section_is_blank(lines, span)

        # Canonicalize question targets (some earlier runs may have created subsection targets)
        def canon_target(t: str) -> str:
            t0 = (t or "").strip()
            return TARGET_CANONICAL_MAP.get(t0, t0)

        # Any questions (open or answered) targeting this section
        subs = find_subsections_within(lines, span)
        target_ids = {section_id} | {s.subsection_id for s in subs}

        targeted = [q for q in open_qs if canon_target(q.section_target) in target_ids]

        answered = [
            q for q in targeted
            if q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
        ]

        open_unanswered_exists = any(
            q.status.strip() in ("Open", "Deferred") and q.answer.strip() in ("", "-", "Pending")
            for q in targeted
        )

        # provenance stub
        human_modified = False

        # 1) If we have answers for this section, integrate them FIRST (even if the section is blank).
        # This prevents the "blank" branch from endlessly generating questions while answers exist.
        if answered and revised_sections[section_id] < 1:
            # Integrate answers into the most specific target we can:
            # - If question targets a subsection (e.g., primary_goals), update that subsection block.
            # - Else, update the parent section block.
            by_target: Dict[str, List[OpenQuestion]] = {}
            for q in answered:
                tgt = canon_target(q.section_target)
                by_target.setdefault(tgt, []).append(q)

            any_integrated = False

            for tgt, qs_for_tgt in by_target.items():
                if tgt == section_id:
                    tgt_start, tgt_end = span.start_line, span.end_line
                else:
                    subspan = get_subsection_span(subs, tgt)
                    if not subspan:
                        logging.warning("Answered questions target '%s' but no matching subsection marker exists; skipping.", tgt)
                        continue
                    tgt_start, tgt_end = subspan.start_line, subspan.end_line

                context = "\n".join(lines[tgt_start:tgt_end])

                try:
                    new_body = llm.integrate_answers(tgt, context, qs_for_tgt)
                except NotImplementedError:
                    new_body = context

                # Apply strict sanitizer before writing
                new_body = sanitize_llm_body(tgt, new_body)

                if new_body.strip() and new_body.strip() != context.strip():
                    if not dry_run:
                        lines = replace_block_body_preserving_markers(lines, tgt_start, tgt_end, new_body)
                    any_integrated = True

            if any_integrated:
                changed = True
                revised_sections[section_id] += 1

                qids = [q.question_id for q in answered]
                lines, resolved = open_questions_resolve(lines, qids)
                if resolved:
                    change_summaries.append(f"Questions resolved: {', '.join(qids)}")
                    changed = True
                    open_qs, _, _ = open_questions_parse(lines)

            # Re-evaluate blankness after integration
            blank = section_is_blank(lines, span)

        # 2) If still blank, generate questions ONLY if none already exist for this section.
        if blank:
            needs_human_input = True
            if open_unanswered_exists:
                logging.info("Section blank but already has open questions; not generating more: %s", section_id)
                continue

            context_body = section_body(lines, span)
            proposed = llm.generate_open_questions(section_id, context_body)

            if proposed:
                allowed_targets = set(PHASES["phase_1_intent_scope"])
                new_questions = []
                for item in proposed:
                    q_text = (item.get("question") or "").strip()
                    target = canon_target((item.get("section_target") or section_id).strip())
                    # Coerce invalid targets to the current section (keeps Phase 1 deterministic)
                    if target not in allowed_targets:
                        target = section_id
                    if q_text:
                        new_questions.append((q_text, target, iso_today()))
                if new_questions and not dry_run:
                    lines, inserted = open_questions_insert(lines, new_questions)
                    if inserted:
                        changed = True
                        change_summaries.append(f"Open questions added for {section_id}: {inserted}")
                        open_qs, _, _ = open_questions_parse(lines)
            else:
                blocked.append(f"{section_id} is blank and LLM returned no questions.")
            continue

        # 3) human modified -> review (stub)
        if human_modified and revised_sections[section_id] < 1:
            context_body = section_body(lines, span)
            revised = llm.review_and_revise(section_id, context_body)
            if revised.strip() and revised.strip() != context_body.strip():
                if not dry_run:
                    lines = replace_section_data_plane(lines, span, revised)
                changed = True
                revised_sections[section_id] += 1

    return lines, changed, blocked, needs_human_input, change_summaries


# -----------------------------
# Readiness gate (Phase 1)
# -----------------------------

def validate_phase_1_complete(lines: List[str]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    spans = find_sections(lines)

    try:
        open_qs, _, _ = open_questions_parse(lines)
    except Exception as e:
        return False, [f"Open Questions parse failed: {e}"]

    def canon_target(t: str) -> str:
        t0 = (t or "").strip()
        return TARGET_CANONICAL_MAP.get(t0, t0)

    for sid in PHASES["phase_1_intent_scope"]:
        sp = get_section_span(spans, sid)
        if not sp:
            issues.append(f"Missing section: {sid}")
            continue
        if section_is_blank(lines, sp):
            issues.append(f"Section still blank: {sid}")
        if any(canon_target(q.section_target) == sid and q.status.strip() == "Open" for q in open_qs):
            issues.append(f"Open questions remain for section: {sid}")

    return (len(issues) == 0), issues


# -----------------------------
# Bootstrap helper (optional but useful)
# -----------------------------


def process_phase_2(
    lines: List[str],
    llm: LLMClient,
    dry_run: bool,
) -> Tuple[List[str], bool, List[str], bool, List[str]]:
    """
    Phase 2: Assumptions + Constraints.

    Behavior:
    - If a Phase 2 section is blank (PLACEHOLDER present) AND there are no open questions for it yet -> generate questions.
    - If there are answered questions for a Phase 2 section -> integrate answers into that section and resolve those QIDs.
    - PLACEHOLDER stays until we actually write real content into the section (option B).
    """
    changed = False
    blocked: List[str] = []
    needs_human_input = False
    summaries: List[str] = []

    phase2_sections = PHASES["phase_2_assumptions_constraints"]

    # Span sanity check up-front (block instead of corrupting).
    span_issues = validate_required_section_spans(lines, phase2_sections)
    if span_issues:
        blocked.extend(span_issues)
        return lines, False, blocked, True, summaries

    spans = find_sections(lines)

    # Parse Open Questions
    open_qs, _, _ = open_questions_parse(lines)

    for section_id in phase2_sections:
        span = get_section_span(spans, section_id)
        if not span:
            blocked.append(f"Missing required section marker: {section_id}")
            continue

        if section_is_locked(lines, span):
            logging.info("Section locked, skipping edits: %s", section_id)
            continue

        blank = section_is_blank(lines, span)

        # Questions targeting this section
        targeted = [q for q in open_qs if q.section_target.strip() == section_id]

        answered = [
            q for q in targeted
            if q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
        ]

        open_unanswered_exists = any(
            q.status.strip() == "Open" and q.answer.strip() in ("", "-", "Pending", "")
            for q in targeted
        )

        # 1) If we have answered questions, integrate them (even if PLACEHOLDER remains).
        if answered:
            context = section_text(lines, span)
            context_body = section_body(lines, span)
            new_body = llm.integrate_answers(section_id, context, answered)
            new_body = sanitize_llm_body(section_id, new_body)

            if new_body.strip() and new_body.strip() != context_body.strip():
                if not dry_run:
                    lines = replace_block_body_preserving_markers(lines, span, new_body)
                    # Refresh spans because the doc just changed.
                    spans = find_sections(lines)
                    span = get_section_span(spans, section_id) or span
                changed = True

                qids = [q.question_id for q in answered]
                if qids and not dry_run:
                    lines, resolved = open_questions_resolve(lines, qids)
                    if resolved:
                        changed = True
                        # Refresh parsed questions
                        open_qs, _, _ = open_questions_parse(lines)

                summaries.append(f"{section_id}: integrated {len(answered)} answers; resolved {len(answered)} questions.")
            continue

        # 2) If section is blank and no open questions exist for it yet -> generate new questions.
        #    If open questions already exist, don't spam duplicates.
        if blank and not open_unanswered_exists:
            needs_human_input = True
            context = section_text(lines, span)
            proposed = llm.generate_open_questions(section_id, context)

            if proposed:
                new_questions: List[Tuple[str, str, str]] = []
                for item in proposed:
                    q_text = (item.get("question") or "").strip()
                    target = (item.get("section_target") or section_id).strip()
                    if q_text:
                        new_questions.append((q_text, target, iso_today()))

                if new_questions and not dry_run:
                    lines, inserted = open_questions_insert(lines, new_questions)
                    if inserted:
                        changed = True
                        open_qs, _, _ = open_questions_parse(lines)
                        summaries.append(f"{section_id}: generated {inserted} open questions.")
            else:
                blocked.append(f"{section_id} is blank and LLM returned no questions.")
            continue

        # 3) Otherwise: no answered questions and either not blank or already has open questions.
        if blank:
            needs_human_input = True

    return lines, changed, blocked, needs_human_input, summaries

def maybe_fill_bootstrap_problem(lines: List[str], problem_text: str) -> Tuple[List[str], bool]:
    """
    If you have a bootstrap question like Q-001 in the Open Questions table,
    this fills its Answer with --problem input.

    It will NOT create Q-001. Put Q-001 in the template if you want it guaranteed.
    """
    if not problem_text.strip():
        return lines, False
    # Try to set Q-001 if it exists.
    try:
        return open_questions_set_answer(lines, "Q-001", problem_text.strip(), date=iso_today(), keep_status=True)
    except Exception:
        return lines, False


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Requirements automation (functional Phase 1).")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Template path (default: repo docs/templates/requirements-template.md)")
    parser.add_argument("--doc", default=str(DEFAULT_DOC), help="Requirements doc path (default: repo docs/requirements.md)")
    parser.add_argument("--dry-run", action="store_true", help="Compute changes but do not write file.")
    parser.add_argument("--no-commit", action="store_true", help="Do not git commit/push changes.")
    parser.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    parser.add_argument("--problem", default="", help="Optional bootstrap problem statement text (fills Q-001 Answer if present).")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(levelname)s %(message)s")

    template_path = Path(args.template).resolve()
    doc_path = Path(args.doc).resolve()

    doc_created = False
    change_summaries: List[str] = []
    # Pre-flight git safety (optional but smart)
    if not args.no_commit:
        if not is_working_tree_clean(REPO_ROOT):
            print("ERROR: Working tree has uncommitted changes.\n")
            print(git_status_porcelain(REPO_ROOT))
            return 2

    # Ensure doc exists
    if not doc_path.exists():
        if not template_path.exists():
            print(f"ERROR: Template missing: {template_path}")
            return 2
        logging.info("Doc missing; creating from template: %s -> %s", template_path, doc_path)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_path, doc_path)
        doc_created = True
        change_summaries.append("Created requirements doc from template")

    doc_text = read_text(doc_path)
    lines = split_lines(doc_text)

    # Structure validation
    lines, struct_changed, struct_notes = validate_and_repair_structure(lines)
    for n in struct_notes:
        logging.warning("STRUCT NOTE: %s", n)

    changed = struct_changed

    # Optional bootstrap fill
    if args.problem.strip():
        lines, did = maybe_fill_bootstrap_problem(lines, args.problem)
        changed = changed or did
        if did:
            logging.info("Bootstrap: filled Q-001 Answer from --problem input.")
            change_summaries.append("Bootstrap: answered Q-001 from --problem")

    lines_before_run = list(lines)

    # Determine which phase to run: we run ONLY the first incomplete phase each run.
    phase_to_run = None
    complete_before = False

    for ph in PHASE_ORDER:
        if ph == "phase_1_intent_scope":
            complete, _issues = validate_phase_1_complete(lines)
        elif ph == "phase_2_assumptions_constraints":
            # Phase 2 only matters after Phase 1 is complete.
            p1_complete, _ = validate_phase_1_complete(lines)
            if not p1_complete:
                complete = False
            else:
                complete, _issues = validate_phase_2_complete(lines)
        else:
            complete = True

        if not complete:
            phase_to_run = ph
            complete_before = False
            break

    if phase_to_run is None:
        # Everything we currently know about is complete.
        phase_to_run = "phase_2_assumptions_constraints"
        complete_before = True

    # Initialize real LLM client
    try:
        llm = LLMClient()
    except Exception as e:
        print(f"ERROR: LLM client init failed: {e}")
        return 2

    # Run selected phase
    try:
        if phase_to_run == "phase_1_intent_scope":
            lines, phase_changed, blocked, needs_human, phase_summaries = process_phase_1(lines, llm, args.dry_run)
            complete_after, _ = validate_phase_1_complete(lines)
        elif phase_to_run == "phase_2_assumptions_constraints":
            lines, phase_changed, blocked, needs_human, phase_summaries = process_phase_2(lines, llm, args.dry_run)
            complete_after, _ = validate_phase_2_complete(lines)
        else:
            phase_changed, blocked, needs_human, phase_summaries, complete_after = False, [], False, [], True

        change_summaries.extend(phase_summaries)
        changed = changed or phase_changed
    except Exception as e:
        logging.error("Run failed: %s", e, exc_info=True)
        return 2

    # A phase completion transition is what triggers a minor version bump (0.x -> 0.(x+1)).
    phase_completed_this_run = (not complete_before) and complete_after

    lines, meta_changed = update_automation_owned_fields(lines_before_run, lines, doc_created=doc_created, phase_completed_this_run=phase_completed_this_run, change_summaries=change_summaries)
    changed = changed or meta_changed
    # Validate completeness for phases we know about (informational only).
    p1_complete, p1_issues = validate_phase_1_complete(lines)
    if not p1_complete:
        for i in p1_issues:
            logging.info("PHASE 1 INCOMPLETE: %s", i)

    if p1_complete:
        p2_complete, p2_issues = validate_phase_2_complete(lines)
        if not p2_complete:
            for i in p2_issues:
                logging.info("PHASE 2 INCOMPLETE: %s", i)
    # Outcome
    if blocked:
        outcome = "blocked"
    elif not changed:
        outcome = "no-op"
    else:
        outcome = "updated"

    # Write output
    if changed and not args.dry_run:
        backup = backup_file(doc_path)
        logging.info("Backup created: %s", backup)
        write_text(doc_path, join_lines(lines))

    # Commit/push (only if changed and enabled)
    if changed and not args.dry_run and not args.no_commit:
        commit_msg = f"requirements: automation pass ({phase_to_run})"
        allow = [str(doc_path.relative_to(REPO_ROOT)).replace("\\", "/")]
        commit_and_push(REPO_ROOT, commit_msg, allow_files=allow)

    result = RunResult(outcome=outcome, changed=changed, blocked_reasons=blocked)
    print(json.dumps(dataclasses.asdict(result), indent=2))
    return 0 if outcome in ("no-op", "updated") else 1


if __name__ == "__main__":
    raise SystemExit(main())
