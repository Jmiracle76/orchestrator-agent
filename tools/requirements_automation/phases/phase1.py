from __future__ import annotations
import logging
from typing import Dict, List, Tuple
from ..config import PHASES, TARGET_CANONICAL_MAP
from ..models import OpenQuestion
from ..parsing import find_sections, get_section_span, section_is_locked, section_is_blank, section_body, find_subsections_within, get_subsection_span
from ..open_questions import open_questions_parse, open_questions_insert, open_questions_resolve
from ..editing import replace_block_body_preserving_markers
from ..utils_io import iso_today

def _canon_target(t: str) -> str:
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)

def process_phase_1(lines: List[str], llm, dry_run: bool) -> Tuple[List[str], bool, List[str], bool, List[str]]:
    changed = False
    blocked: List[str] = []
    needs_human = False
    summaries: List[str] = []

    spans = find_sections(lines)
    open_qs, _, _ = open_questions_parse(lines)

    revised: Dict[str,int] = {sid: 0 for sid in PHASES["phase_1_intent_scope"]}

    for section_id in PHASES["phase_1_intent_scope"]:
        span = get_section_span(spans, section_id)
        if not span:
            blocked.append(f"Missing required section marker: {section_id}")
            continue
        if section_is_locked(lines, span):
            logging.info("Section locked, skipping edits: %s", section_id)
            continue

        blank = section_is_blank(lines, span)

        subs = find_subsections_within(lines, span)
        target_ids = {section_id} | {s.subsection_id for s in subs}
        targeted = [q for q in open_qs if _canon_target(q.section_target) in target_ids]
        answered = [q for q in targeted if q.answer.strip() not in ("", "-", "Pending") and q.status.strip() in ("Open","Deferred")]
        open_unanswered_exists = any(q.status.strip() in ("Open","Deferred") and q.answer.strip() in ("", "-", "Pending") for q in targeted)

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
                        logging.warning("Answered questions target '%s' but no matching subsection marker exists; skipping.", tgt)
                        continue
                    start, end = subspan.start_line, subspan.end_line
                context = "\n".join(lines[start:end])
                new_body = llm.integrate_answers(tgt, context, qs)
                if new_body.strip() and new_body.strip() != context.strip():
                    if not dry_run:
                        lines = replace_block_body_preserving_markers(lines, start, end, section_id=tgt, new_body=new_body)
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

        if blank:
            needs_human = True
            if open_unanswered_exists:
                logging.info("Section blank but already has open questions; not generating more: %s", section_id)
                continue
            ctx = section_body(lines, span)
            proposed = llm.generate_open_questions(section_id, ctx)
            new_qs = []
            allowed_targets = set(PHASES["phase_1_intent_scope"])
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
