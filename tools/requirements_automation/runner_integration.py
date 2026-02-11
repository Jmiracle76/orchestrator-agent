"""Answer integration and section drafting logic."""
from __future__ import annotations
import logging
from typing import List, Dict
from .parsing import find_sections, get_section_span, section_is_blank, find_subsections_within, section_body
from .open_questions import open_questions_parse, open_questions_resolve, open_questions_insert
from .editing import replace_block_body_preserving_markers
from .utils_io import iso_today
from .runner_state import _canon_target, _get_replacement_end_boundary


def integrate_answered_questions(
    lines: List[str],
    target_id: str,
    llm,
    handler_config,
    prior_sections: dict[str, str],
    dry_run: bool = False
) -> tuple[List[str], bool, int, List[str]]:
    """
    Integrate answered questions into a section.
    
    Args:
        lines: Document content as list of strings
        target_id: Section ID to process
        llm: LLM client instance
        handler_config: Handler configuration from registry
        prior_sections: Dict of completed section IDs to their content
        dry_run: If True, don't modify the document
        
    Returns:
        Tuple of (updated_lines, changed, questions_resolved, summaries)
    """
    changed = False
    questions_resolved = 0
    summaries = []
    
    # Get current section span
    spans = find_sections(lines)
    span = get_section_span(spans, target_id)
    
    if not span:
        return lines, False, 0, [f"Section span not found: {target_id}"]
    
    # Parse open questions
    try:
        open_qs, _, _ = open_questions_parse(lines)
    except Exception as e:
        logging.warning("Failed to parse open questions: %s", e)
        open_qs = []
    
    # Include subsections when checking questions
    subs = find_subsections_within(lines, span)
    target_ids = {target_id} | {s.subsection_id for s in subs}
    
    targeted_questions = [
        q for q in open_qs if _canon_target(q.section_target) in target_ids
    ]
    
    # Find questions with answers (status "Open"/"Deferred" with non-empty answers)
    answered_questions = [
        q for q in targeted_questions
        if q.answer.strip() not in ("", "-", "Pending")
        and q.status.strip() in ("Open", "Deferred")
    ]
    
    if not answered_questions:
        return lines, False, 0, []
    
    logging.info(
        "Integrating %d answered questions into section: %s",
        len(answered_questions),
        target_id,
    )
    
    # Group questions by target (section or subsection)
    by_target: Dict[str, List] = {}
    for q in answered_questions:
        tgt = _canon_target(q.section_target)
        by_target.setdefault(tgt, []).append(q)
    
    any_integrated = False
    for tgt, qs in by_target.items():
        # Get the span for this target (section or subsection)
        if tgt == target_id:
            target_start = span.start_line
            # Check if section contains open_questions subsection
            # If it does, stop replacement before that subsection
            target_end = _get_replacement_end_boundary(lines, span, subs)
        else:
            # Find subsection span
            subspan = None
            for s in subs:
                if s.subsection_id == tgt:
                    subspan = s
                    break
            if not subspan:
                logging.warning(
                    "Answered questions target '%s' but no matching subsection exists; skipping.",
                    tgt,
                )
                continue
            target_start, target_end = subspan.start_line, subspan.end_line
        
        # Get current context for this target
        context = "\n".join(lines[target_start:target_end])
        
        # Call LLM to integrate answers using handler config parameters
        new_body = llm.integrate_answers(
            tgt,
            context,
            qs,
            llm_profile=handler_config.llm_profile,
            output_format=handler_config.output_format,
            prior_sections=prior_sections,
        )
        
        if new_body.strip() and new_body.strip() != context.strip():
            if not dry_run:
                lines = replace_block_body_preserving_markers(
                    lines,
                    target_start,
                    target_end,
                    section_id=tgt,
                    new_body=new_body,
                )
                # Update spans after modification
                spans = find_sections(lines)
            any_integrated = True
    
    if any_integrated:
        changed = True
        questions_resolved = len(answered_questions)
        
        # Mark questions as resolved
        qids = [q.question_id for q in answered_questions]
        if not dry_run:
            try:
                lines, resolved = open_questions_resolve(lines, qids)
                if resolved:
                    summaries.append(
                        f"Integrated {len(answered_questions)} answers; resolved {resolved} questions"
                    )
            except Exception as e:
                logging.warning("Failed to resolve questions: %s", e)
                summaries.append(
                    f"Integrated {len(answered_questions)} answers (questions table not available)"
                )
    
    return lines, changed, questions_resolved, summaries


def draft_section_content(
    lines: List[str],
    target_id: str,
    llm,
    handler_config,
    prior_sections: dict[str, str],
    dry_run: bool = False
) -> tuple[List[str], bool, List[str]]:
    """
    Draft initial content for a blank section using prior context.
    
    Args:
        lines: Document content as list of strings
        target_id: Section ID to process
        llm: LLM client instance
        handler_config: Handler configuration from registry
        prior_sections: Dict of completed section IDs to their content
        dry_run: If True, don't modify the document
        
    Returns:
        Tuple of (updated_lines, changed, summaries)
    """
    summaries = []
    
    # Get current section span
    spans = find_sections(lines)
    span = get_section_span(spans, target_id)
    
    if not span:
        return lines, False, [f"Section span not found: {target_id}"]
    
    # Check if section is blank
    is_blank = section_is_blank(lines, span)
    if not is_blank:
        return lines, False, []
    
    # Only draft if prior context is available
    if not prior_sections:
        return lines, False, []
    
    logging.info(
        "Section '%s' is blank with prior context available; attempting to draft content",
        target_id,
    )
    
    try:
        ctx = section_body(lines, span)
        draft = llm.draft_section(
            target_id,
            ctx,
            prior_sections,
            llm_profile=handler_config.llm_profile,
            output_format=handler_config.output_format,
        )
        
        if draft.strip() and draft.strip() != ctx.strip():
            if not dry_run:
                # Calculate effective end boundary to preserve open_questions subsection
                subs = find_subsections_within(lines, span)
                draft_end = _get_replacement_end_boundary(lines, span, subs)
                
                # Write the draft to the section body
                lines = replace_block_body_preserving_markers(
                    lines,
                    span.start_line,
                    draft_end,
                    section_id=target_id,
                    new_body=draft,
                )
            
            summaries.append(f"Drafted initial content for {target_id} using prior section context")
            logging.info("Draft completed for '%s'", target_id)
            return lines, True, summaries
        else:
            logging.info(
                "Draft for '%s' was empty or unchanged; will fall through to question generation",
                target_id,
            )
    except Exception as e:
        logging.warning("Failed to draft section '%s': %s; falling back to question generation", target_id, e)
    
    return lines, False, []


def generate_questions_for_section(
    lines: List[str],
    target_id: str,
    llm,
    handler_config,
    prior_sections: dict[str, str],
    dry_run: bool = False
) -> tuple[List[str], bool, int, List[str]]:
    """
    Generate new open questions for a blank section.
    
    Args:
        lines: Document content as list of strings
        target_id: Section ID to process
        llm: LLM client instance
        handler_config: Handler configuration from registry
        prior_sections: Dict of completed section IDs to their content
        dry_run: If True, don't modify the document
        
    Returns:
        Tuple of (updated_lines, changed, questions_generated, summaries)
    """
    summaries = []
    
    # Get current section span
    spans = find_sections(lines)
    span = get_section_span(spans, target_id)
    
    if not span:
        return lines, False, 0, [f"Section span not found: {target_id}"]
    
    # Include subsections when checking questions
    subs = find_subsections_within(lines, span)
    target_ids = {target_id} | {s.subsection_id for s in subs}
    
    # Check for existing unanswered questions
    try:
        open_qs, _, _ = open_questions_parse(lines)
        targeted_questions = [
            q for q in open_qs if _canon_target(q.section_target) in target_ids
        ]
        open_unanswered = [
            q for q in targeted_questions
            if q.status.strip() in ("Open", "Deferred")
            and q.answer.strip() in ("", "-", "Pending")
        ]
    except Exception as e:
        logging.warning("Failed to parse open questions: %s", e)
        open_unanswered = []
    
    if open_unanswered:
        # Section has open questions - don't generate new ones
        return lines, False, 0, []
    
    # Generate new questions
    logging.info(
        "Section '%s' is blank and has no open questions; generating questions",
        target_id,
    )
    
    ctx = section_body(lines, span)
    proposed = llm.generate_open_questions(
        target_id,
        ctx,
        llm_profile=handler_config.llm_profile,
        prior_sections=prior_sections,
    )
    
    new_qs = []
    for item in proposed:
        q_text = (item.get("question") or "").strip()
        q_target = _canon_target(
            (item.get("section_target") or target_id).strip()
        )
        # Validate that target is this section or a subsection
        if q_target not in target_ids:
            q_target = target_id
        if q_text:
            new_qs.append((q_text, q_target, iso_today()))
    
    if new_qs and not dry_run:
        try:
            lines, inserted = open_questions_insert(lines, new_qs)
            if inserted:
                summaries.append(
                    f"Generated {inserted} open questions for {target_id}"
                )
                return lines, True, inserted, summaries
        except Exception as e:
            logging.warning("Failed to insert open questions: %s", e)
            summaries.append(
                f"Generated {len(new_qs)} questions but could not insert (no questions table)"
            )
    
    return lines, False, 0, summaries
