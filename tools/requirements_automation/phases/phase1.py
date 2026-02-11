from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from ..config import PHASES, TARGET_CANONICAL_MAP
from ..editing import replace_block_body_preserving_markers
from ..models import OpenQuestion
from ..open_questions import open_questions_insert, open_questions_parse, open_questions_resolve
from ..parsing import (
    find_sections,
    find_subsections_within,
    get_section_span,
    get_subsection_span,
    section_body,
    section_is_blank,
    section_is_locked,
)
from ..utils_io import iso_today


def _canon_target(t: str) -> str:
    """Normalize alias section IDs to canonical targets."""
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)


def process_phase_1(
    lines: List[str], llm: Any, dry_run: bool, target_section: str | None = None
) -> Tuple[List[str], bool, List[str], bool, List[str]]:
    """Fill intent/scope sections or create open questions when missing."""
    changed = False
    blocked: List[str] = []
    needs_human = False
    summaries: List[str] = []

    # Parse document structure and current open questions table.
    spans = find_sections(lines)
    open_qs, _, _ = open_questions_parse(lines)

    # Track how many times we've integrated for each section in this run.
    phase_sections = PHASES["phase_1_intent_scope"]
    if target_section:
        phase_sections = [target_section]
    revised: Dict[str, int] = {sid: 0 for sid in phase_sections}

    for section_id in phase_sections:
        span = get_section_span(spans, section_id)
        if not span:
            blocked.append(f"Missing required section marker: {section_id}")
            continue
        if section_is_locked(lines, span):
            logging.info("Section locked, skipping edits: %s", section_id)
            continue

        blank = section_is_blank(lines, span)

        # Subsections allow targeting nested areas inside a section.
        subs = find_subsections_within(lines, span)
        target_ids = {section_id} | {s.subsection_id for s in subs}
        targeted = [q for q in open_qs if _canon_target(q.section_target) in target_ids]
        answered = [
            q
            for q in targeted
            if q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
        ]
        open_unanswered_exists = any(
            q.status.strip() in ("Open", "Deferred") and q.answer.strip() in ("", "-", "Pending")
            for q in targeted
        )

        # If answers exist, integrate them into the section/subsection body.
        if answered and revised[section_id] < 1:
            by_target: Dict[str, List[OpenQuestion]] = {}
            for q in answered:
                by_target.setdefault(_canon_target(q.section_target), []).append(q)

            any_integrated = False
            for tgt, qs in by_target.items():
                if tgt == section_id:
                    start, end = span.start_line, span.end_line
                else:
                    subspan = get_subsection_span(subs, tgt)
                    if not subspan:
                        logging.warning(
                            "Answered questions target '%s' but no matching subsection marker exists; skipping.",
                            tgt,
                        )
                        continue
                    start, end = subspan.start_line, subspan.end_line
                # Provide the LLM the current context for a targeted block.
                context = "\n".join(lines[start:end])
                new_body = llm.integrate_answers(tgt, context, qs)
                if new_body.strip() and new_body.strip() != context.strip():
                    if not dry_run:
                        lines = replace_block_body_preserving_markers(
                            lines, start, end, section_id=tgt, new_body=new_body
                        )
                    any_integrated = True

            if any_integrated:
                changed = True
                revised[section_id] += 1
                qids = [q.question_id for q in answered]
                if not dry_run:
                    lines, resolved = open_questions_resolve(lines, qids)
                    if resolved:
                        summaries.append(f"Questions resolved: {', '.join(qids)}")
                        open_qs, _, _ = open_questions_parse(lines)

            blank = section_is_blank(lines, span)

        # If still blank and no unanswered questions exist, generate new ones.
        if blank:
            needs_human = True
            if open_unanswered_exists:
                logging.info(
                    "Section blank but already has open questions; not generating more: %s",
                    section_id,
                )
                continue
            ctx = section_body(lines, span)
            proposed = llm.generate_open_questions(section_id, ctx)
            new_qs = []
            allowed_targets = set(phase_sections)
            for item in proposed:
                q_text = (item.get("question") or "").strip()
                target = _canon_target((item.get("section_target") or section_id).strip())
                if target not in allowed_targets:
                    target = section_id
                if q_text:
                    new_qs.append((q_text, target, iso_today()))
            if new_qs and not dry_run:
                lines, inserted = open_questions_insert(lines, new_qs)
                if inserted:
                    changed = True
                    summaries.append(f"Open questions added for {section_id}: {inserted}")
                    open_qs, _, _ = open_questions_parse(lines)
            continue

    return lines, changed, blocked, needs_human, summaries
