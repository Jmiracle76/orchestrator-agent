# -----------------------------------------------------------------------------
# Minimal schema helpers (inline on purpose: avoid "tools folder explosion")
# -----------------------------------------------------------------------------

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class OpenQuestion:
    qid: str
    title: str
    status: str
    asked_by: str
    date: str
    question: str
    answer: str
    integration_targets: List[str]


OPEN_QUESTION_STATUS = {"Open", "Resolved", "Deferred"}


def _norm(s: str) -> str:
    return (s or "").strip()


def parse_open_questions(md: str) -> List[OpenQuestion]:
    """
    Parse canonical Open Question subsections.

    Required format:

    #### Q-001: Title
    **Status:** Open|Resolved|Deferred
    **Asked by:** ...
    **Date:** YYYY-MM-DD
    **Question:** ...
    **Answer:** ...
    **Integration Targets:**
    - Section X: ...
    - Section Y: ...

    Returns list in document order.
    """
    # Grab the Open Questions section if present; otherwise parse whole doc safely.
    # We avoid clever parsing; we want robust.
    section_match = re.search(r"(?ims)^##\s+12\.\s+Risks and Open Issues.*?$", md)
    start = section_match.start() if section_match else 0

    # Identify question blocks by headings
    q_heading_re = re.compile(r"(?m)^####\s+(Q-\d{3})\s*:\s*(.+?)\s*$")
    headings = list(q_heading_re.finditer(md, pos=start))

    questions: List[OpenQuestion] = []
    for i, h in enumerate(headings):
        qid = h.group(1)
        title = _norm(h.group(2))
        block_start = h.end()
        block_end = headings[i + 1].start() if i + 1 < len(headings) else len(md)
        block = md[block_start:block_end]

        def field(name: str) -> str:
            m = re.search(rf"(?ims)^\*\*{re.escape(name)}:\*\*\s*(.*?)\s*$", block)
            return _norm(m.group(1)) if m else ""

        status = field("Status")
        asked_by = field("Asked by")
        date = field("Date")

        # Question text can span multiple lines; capture until next **Field:** or heading
        def long_field(name: str) -> str:
            m = re.search(
                rf"(?ims)^\*\*{re.escape(name)}:\*\*\s*(.*?)(?=^\*\*[\w ].+?\:\*\*|\Z)",
                block,
            )
            return _norm(m.group(1)) if m else ""

        q_text = long_field("Question")
        ans_text = long_field("Answer")

        # Integration Targets: bullet list after the field
        targets: List[str] = []
        m = re.search(r"(?ims)^\*\*Integration Targets:\*\*\s*(.*?)(?=^\*\*[\w ].+?\:\*\*|\Z)", block)
        if m:
            tail = m.group(1)
            for line in tail.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    targets.append(_norm(line[2:]))

        questions.append(
            OpenQuestion(
                qid=qid,
                title=title,
                status=status,
                asked_by=asked_by,
                date=date,
                question=q_text,
                answer=ans_text,
                integration_targets=targets,
            )
        )

    return questions


def validate_open_questions(questions: List[OpenQuestion]) -> List[str]:
    """
    Return list of validation errors. No exceptions, no drama.
    """
    errors: List[str] = []
    seen: set[str] = set()

    for q in questions:
        if q.qid in seen:
            errors.append(f"Duplicate Question ID: {q.qid}")
        seen.add(q.qid)

        if q.status and q.status not in OPEN_QUESTION_STATUS:
            errors.append(f"{q.qid}: invalid Status '{q.status}' (must be Open/Resolved/Deferred)")

        if not q.title:
            errors.append(f"{q.qid}: missing title after 'Q-XXX:'")

        # Minimal required fields
        if not q.asked_by:
            errors.append(f"{q.qid}: missing '**Asked by:**'")
        if not q.date:
            errors.append(f"{q.qid}: missing '**Date:**'")
        if not q.question:
            errors.append(f"{q.qid}: missing '**Question:**' body")

        # If Answer exists, Integration Targets should exist
        if q.answer and not q.integration_targets:
            errors.append(f"{q.qid}: has Answer but no Integration Targets")

    return errors


def detect_answered_unintegrated_questions(questions: List[OpenQuestion]) -> List[OpenQuestion]:
    """
    "Answered but not resolved" drives integrate mode.
    """
    return [
        q for q in questions
        if _norm(q.answer) and _norm(q.status) != "Resolved"
    ]


def ensure_no_ghost_question_refs(md: str, questions: List[OpenQuestion]) -> List[str]:
    """
    Guardrail: doc must not reference non-existent Q-IDs (e.g., Q-012) unless that
    question actually exists as a canonical subsection.
    We only enforce this for 'Q-###' patterns.
    """
    known = {q.qid for q in questions}
    referenced = set(re.findall(r"\bQ-\d{3}\b", md))
    ghosts = sorted(referenced - known)
    return ghosts
