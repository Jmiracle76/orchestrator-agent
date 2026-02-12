from __future__ import annotations

import logging
from typing import Any, List, Tuple

from ..config import PHASES
from ..editing import replace_block_body_preserving_markers
from ..open_questions import open_questions_insert, open_questions_parse, open_questions_resolve
from ..parsing import (
    find_sections,
    get_section_span,
    section_body,
    section_is_blank,
    section_is_locked,
    section_text,
    validate_required_section_spans,
)
from ..utils_io import iso_today


def process_phase_2(
    lines: List[str], llm: Any, dry_run: bool, target_section: str | None = None
) -> Tuple[List[str], bool, List[str], bool, List[str]]:
    """Fill assumptions/constraints or generate questions for missing content.
    
    DEPRECATED: This legacy phase processor uses the global open_questions table.
    New code should use the unified handler with per-section question tables configured
    in handler_registry.yaml. This function remains for backward compatibility with
    sections that don't have handler configurations.
    """
    logging.warning(
        "Using deprecated phase-based handler for phase_2. "
        "Consider migrating to unified handler with per-section question tables."
    )
    changed = False
    blocked: List[str] = []
    needs_human = False
    summaries: List[str] = []

    # Validate spans first to ensure the document is structurally sound.
    phase_sections = PHASES["phase_2_assumptions_constraints"]
    if target_section:
        phase_sections = [target_section]
    span_issues = validate_required_section_spans(lines, phase_sections)
    if span_issues:
        blocked.extend(span_issues)
        return lines, False, blocked, True, summaries

    spans = find_sections(lines)
    open_qs, _, _ = open_questions_parse(lines)

    for section_id in phase_sections:
        span = get_section_span(spans, section_id)
        if not span:
            blocked.append(f"Missing required section marker: {section_id}")
            continue
        if section_is_locked(lines, span):
            logging.info("Section locked, skipping edits: %s", section_id)
            continue

        blank = section_is_blank(lines, span)
        targeted = [q for q in open_qs if q.section_target.strip() == section_id]
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

        # Integrate answered questions into the section if present.
        if answered:
            ctx = section_text(lines, span)
            current_body = section_body(lines, span)
            new_body = llm.integrate_answers(section_id, ctx, answered)
            if new_body.strip() and new_body.strip() != current_body.strip():
                if not dry_run:
                    lines = replace_block_body_preserving_markers(
                        lines,
                        span.start_line,
                        span.end_line,
                        section_id=section_id,
                        new_body=new_body,
                    )
                    spans = find_sections(lines)
                changed = True
                qids = [q.question_id for q in answered]
                if not dry_run:
                    lines, resolved = open_questions_resolve(lines, qids)
                    if resolved:
                        open_qs, _, _ = open_questions_parse(lines)
                summaries.append(
                    f"{section_id}: integrated {len(answered)} answers; resolved {len(answered)} questions."
                )
            continue

        # If blank and no unanswered questions exist, generate new questions.
        if blank and not open_unanswered_exists:
            needs_human = True
            ctx = section_text(lines, span)
            proposed = llm.generate_open_questions(section_id, ctx)
            new_qs = []
            for item in proposed:
                q_text = (item.get("question") or "").strip()
                target = (item.get("section_target") or section_id).strip()
                if q_text:
                    new_qs.append((q_text, target, iso_today()))
            if new_qs and not dry_run:
                lines, inserted = open_questions_insert(lines, new_qs)
                if inserted:
                    changed = True
                    open_qs, _, _ = open_questions_parse(lines)
                    summaries.append(f"{section_id}: generated {inserted} open questions.")
            continue

        if blank:
            needs_human = True

    return lines, changed, blocked, needs_human, summaries
