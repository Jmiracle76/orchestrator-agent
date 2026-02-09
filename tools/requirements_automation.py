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
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Configuration
# -----------------------------

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "docs" / "templates" / "requirements-template.md"
DEFAULT_DOC = REPO_ROOT / "docs" / "requirements.md"

PHASES: Dict[str, List[str]] = {
    "phase_1_intent_scope": [
        "problem_statement",
        "goals_objectives",
        "stakeholders_users",
        "success_criteria",
    ],
}

# Markers
SECTION_MARKER_RE = re.compile(r"<!--\s*section:(?P<id>[a-z0-9_]+)\s*-->")
SECTION_LOCK_RE   = re.compile(r"<!--\s*section_lock:(?P<id>[a-z0-9_]+)\s+lock=(?P<lock>true|false)\s*-->")
TABLE_MARKER_RE   = re.compile(r"<!--\s*table:(?P<id>[a-z0-9_]+)\s*-->")
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


def section_text(lines: List[str], span: SectionSpan) -> str:
    return "\n".join(lines[span.start_line:span.end_line])


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
            data = json.loads(raw)
        except json.JSONDecodeError as e:
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
    changed = False
    notes: List[str] = []

    spans = find_sections(lines)
    known_sections = {s.section_id for s in spans}

    # Warn on orphan locks
    for i, line in enumerate(lines):
        m = SECTION_LOCK_RE.search(line)
        if m and m.group("id") not in known_sections:
            notes.append(f"Orphan section_lock at line {i+1}: {m.group('id')}")

    # Ensure Open Questions table exists (don’t auto-create silently)
    if not find_table_block(lines, "open_questions"):
        notes.append("Missing Open Questions table marker/block: <!-- table:open_questions -->")

    return lines, changed, notes


# -----------------------------
# Section editing helpers
# -----------------------------

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
) -> Tuple[List[str], bool, List[str], bool]:
    changed = False
    blocked: List[str] = []
    needs_human_input = False

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

        answered = [
            q for q in open_qs
            if q.section_target.strip() == section_id
            and q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
        ]

        # provenance stub
        human_modified = False

        # 1) blank -> generate questions
        if blank:
            needs_human_input = True
            context = section_text(lines, span)
            proposed = llm.generate_open_questions(section_id, context)

            if proposed:
                new_questions = []
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
            else:
                blocked.append(f"{section_id} is blank and LLM returned no questions.")
            continue

        # 2) answered -> integrate -> resolve
        if answered and revised_sections[section_id] < 1:
            context = section_text(lines, span)
            new_body = llm.integrate_answers(section_id, context, answered)

            if new_body.strip() != context.strip():
                if not dry_run:
                    lines = replace_section_data_plane(lines, span, new_body)
                changed = True
                revised_sections[section_id] += 1

                qids = [q.question_id for q in answered]
                if qids and not dry_run:
                    lines, resolved = open_questions_resolve(lines, qids)
                    if resolved:
                        changed = True
                        open_qs, _, _ = open_questions_parse(lines)

        # 3) human modified -> review (stub)
        if human_modified and revised_sections[section_id] < 1:
            context = section_text(lines, span)
            revised = llm.review_and_revise(section_id, context)
            if revised.strip() != context.strip():
                if not dry_run:
                    lines = replace_section_data_plane(lines, span, revised)
                changed = True
                revised_sections[section_id] += 1

    return lines, changed, blocked, needs_human_input


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

    for sid in PHASES["phase_1_intent_scope"]:
        sp = get_section_span(spans, sid)
        if not sp:
            issues.append(f"Missing section: {sid}")
            continue
        if section_is_blank(lines, sp):
            issues.append(f"Section still blank: {sid}")
        if any(q.section_target.strip() == sid and q.status.strip() == "Open" for q in open_qs):
            issues.append(f"Open questions remain for section: {sid}")

    return (len(issues) == 0), issues


# -----------------------------
# Bootstrap helper (optional but useful)
# -----------------------------

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

    # Initialize real LLM client
    try:
        llm = LLMClient()
    except Exception as e:
        print(f"ERROR: LLM client init failed: {e}")
        return 2

    # Phase 1
    try:
        lines, phase_changed, blocked, needs_human = process_phase_1(lines, llm, args.dry_run)
        changed = changed or phase_changed
    except Exception as e:
        logging.error("Run failed: %s", e, exc_info=True)
        return 2

    # Validate Phase 1 completeness
    complete, issues = validate_phase_1_complete(lines)
    if not complete:
        for i in issues:
            logging.info("PHASE 1 INCOMPLETE: %s", i)

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
        commit_msg = "requirements: automation pass (phase 1)"
        allow = [str(doc_path.relative_to(REPO_ROOT)).replace("\\", "/")]
        commit_and_push(REPO_ROOT, commit_msg, allow_files=allow)

    result = RunResult(outcome=outcome, changed=changed, blocked_reasons=blocked)
    print(json.dumps(dataclasses.asdict(result), indent=2))
    return 0 if outcome in ("no-op", "updated") else 1


if __name__ == "__main__":
    raise SystemExit(main())
