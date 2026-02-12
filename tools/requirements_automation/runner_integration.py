"""Answer integration and section drafting logic."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .editing import replace_block_body_preserving_markers
from .open_questions import open_questions_insert, open_questions_parse, open_questions_resolve
from .parsing import (
    find_sections,
    find_subsections_within,
    get_section_span,
    section_body,
    section_is_blank,
)
from .runner_state import _canon_target, _get_replacement_end_boundary
from .section_questions import (
    insert_section_questions_batch,
    parse_section_questions,
    resolve_section_questions_batch,
    section_has_answered_questions,
)
from .table_routing import route_table_content_to_subsections
from .utils_io import iso_today


# Subsections that contain table content
TABLE_SUBSECTIONS = {
    "primary_stakeholders",
    "end_users",
    "external_systems",
    "data_exchange",
    "risks",
    "functional_requirements",
    "non_functional_requirements",
}


def _build_subsection_structure(
    lines: List[str], span: Any, handler_config: Any
) -> Optional[List[dict]]:
    """Build subsection structure information for LLM prompts.
    
    Args:
        lines: Document lines
        span: Section span
        handler_config: Handler configuration
        
    Returns:
        List of subsection dicts with 'id' and 'type' keys, or None if no subsections
    """
    # Only build structure if handler supports subsections
    # Check both handler_config.subsections flag AND output_format because:
    # - subsections=True means handler explicitly declares subsection support
    # - output_format="subsections" means LLM should organize content with subsection headers
    # Both conditions ensure subsection-aware content generation
    if not handler_config.subsections and handler_config.output_format != "subsections":
        return None
    
    subs = find_subsections_within(lines, span)
    if not subs:
        return None
    
    # Filter out question-related subsections as they're metadata, not content
    # - subsections ending with '_questions' (e.g., 'goals_objectives_questions')
    # - 'questions_issues' subsection (doesn't end with '_questions')
    content_subs = [s for s in subs if not s.subsection_id.endswith("_questions") 
                    and s.subsection_id != "questions_issues"]
    
    if not content_subs:
        return None
    
    structure = []
    for sub in content_subs:
        sub_info = {"id": sub.subsection_id}
        
        # Determine content type
        if sub.subsection_id in TABLE_SUBSECTIONS:
            sub_info["type"] = "table"
        elif handler_config.output_format in ("bullets", "numbered"):
            # Use handler's output format for subsection content
            sub_info["type"] = handler_config.output_format
        else:
            # For "subsections" or "prose" output format, infer type from template content
            # Check the subsection content to determine the format
            sub_body_lines = lines[sub.start_line:sub.end_line]
            
            # Look for bullet list markers (dash at start of line)
            if any(line.strip().startswith("-") for line in sub_body_lines if line.strip()):
                sub_info["type"] = "bullets"
            # Look for numbered list markers (digit followed by period at start of line)
            # Use regex to match pattern like "1. " or "2. " to avoid false positives
            elif any(re.match(r'^\s*\d+\.\s', line) for line in sub_body_lines if line.strip()):
                sub_info["type"] = "numbered"
            else:
                sub_info["type"] = "prose"
        
        structure.append(sub_info)
    
    return structure if structure else None


def _use_section_questions(handler_config: Any) -> bool:
    """Determine if section uses per-section questions table.

    Args:
        handler_config: Handler configuration from registry

    Returns:
        True if section uses per-section questions, False for global
    """
    return (
        handler_config is not None
        and hasattr(handler_config, "questions_table")
        and handler_config.questions_table is not None
    )


def _get_section_questions(
    lines: List[str], target_id: str, handler_config: Any
) -> tuple[List[Any], bool]:
    """Get questions for a section using per-section table.

    Args:
        lines: Document content
        target_id: Section identifier
        handler_config: Handler configuration

    Returns:
        Tuple of (questions_list, found_section_questions)
        - questions_list: List of questions from section-specific table, or empty list if:
          * handler_config is None
          * handler doesn't specify a questions_table
          * section questions table doesn't exist or can't be parsed
        - found_section_questions: True if section questions table was found and parsed, False otherwise
    """
    if _use_section_questions(handler_config):
        try:
            # parse_section_questions returns (questions, table_span)
            # We only need the questions list here
            qs, _ = parse_section_questions(lines, target_id)
            return qs, True
        except ValueError:
            logging.debug(
                "Section questions table not found for '%s'",
                target_id,
            )
            return [], False

    # If handler doesn't specify section questions, return empty list
    return [], False


def integrate_answered_questions(
    lines: List[str],
    target_id: str,
    llm: Any,
    handler_config: Any,
    prior_sections: dict[str, str],
    dry_run: bool = False,
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

    # Get questions using the appropriate table (section-specific or global)
    use_section_qs = _use_section_questions(handler_config)

    if use_section_qs:
        # Use section-specific questions
        try:
            all_questions, _ = parse_section_questions(lines, target_id)
            targeted_questions = all_questions
        except Exception as e:
            logging.debug("Failed to parse section questions for '%s': %s", target_id, e)
            targeted_questions = []
    else:
        # No section-specific questions configured, return without processing
        logging.debug(
            "No section-specific questions table configured for '%s'", target_id
        )
        targeted_questions = []

    # Find questions with answers (status "Open"/"Deferred" with non-empty answers)
    answered_questions = [
        q
        for q in targeted_questions
        if q.answer.strip() not in ("", "-", "Pending") and q.status.strip() in ("Open", "Deferred")
    ]

    if not answered_questions:
        return lines, False, 0, []

    logging.info(
        "Integrating %d answered questions into section: %s",
        len(answered_questions),
        target_id,
    )

    # Include subsections for boundary calculation
    subs = find_subsections_within(lines, span)
    
    # Build subsection structure for LLM prompt
    subsection_structure = _build_subsection_structure(lines, span, handler_config)

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
            # Check if section contains questions_issues subsection
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
            subsection_structure=subsection_structure,
        )

        if new_body.strip() and new_body.strip() != context.strip():
            if not dry_run:
                # Route table content only when integrating into main section, not subsections
                if tgt == target_id:
                    # Route table content to subsections if applicable
                    # This extracts table rows from new_body and inserts them into table subsections
                    lines, preamble_content = route_table_content_to_subsections(
                        lines,
                        span,
                        new_body,
                        subsection_structure,
                    )
                else:
                    # Integrating into a subsection - use content as-is
                    preamble_content = new_body
                
                # Write the non-table content (preamble) to the section body
                # Table content has already been inserted into subsections above (if applicable)
                lines = replace_block_body_preserving_markers(
                    lines,
                    target_start,
                    target_end,
                    section_id=tgt,
                    new_body=preamble_content,
                )
                # Update spans after modification
                spans = find_sections(lines)
            any_integrated = True

    if any_integrated:
        changed = True
        questions_resolved = len(answered_questions)

        # Mark questions as resolved in the appropriate table
        qids = [q.question_id for q in answered_questions]
        if not dry_run:
            try:
                if use_section_qs:
                    # Resolve in section-specific table
                    lines, resolved = resolve_section_questions_batch(lines, target_id, qids)
                else:
                    # Resolve in global table
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
    llm: Any,
    handler_config: Any,
    prior_sections: dict[str, str],
    dry_run: bool = False,
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
        
        # Build subsection structure for LLM prompt
        subsection_structure = _build_subsection_structure(lines, span, handler_config)
        
        draft = llm.draft_section(
            target_id,
            ctx,
            prior_sections,
            llm_profile=handler_config.llm_profile,
            output_format=handler_config.output_format,
            subsection_structure=subsection_structure,
        )

        if draft.strip() and draft.strip() != ctx.strip():
            if not dry_run:
                # Calculate effective end boundary to preserve open_questions subsection
                subs = find_subsections_within(lines, span)
                draft_end = _get_replacement_end_boundary(lines, span, subs)

                # Route table content to subsections if applicable
                # This extracts table rows from draft and inserts them into table subsections
                lines, preamble_content = route_table_content_to_subsections(
                    lines,
                    span,
                    draft,
                    subsection_structure,
                )

                # Write the non-table content (preamble) to the section body
                # Table content has already been inserted into subsections above
                lines = replace_block_body_preserving_markers(
                    lines,
                    span.start_line,
                    draft_end,
                    section_id=target_id,
                    new_body=preamble_content,
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
        logging.warning(
            "Failed to draft section '%s': %s; falling back to question generation", target_id, e
        )

    return lines, False, []


def generate_questions_for_section(
    lines: List[str],
    target_id: str,
    llm: Any,
    handler_config: Any,
    prior_sections: dict[str, str],
    dry_run: bool = False,
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

    # Determine if using section-specific questions
    use_section_qs = _use_section_questions(handler_config)

    # Check for existing unanswered questions
    if use_section_qs:
        # Check section-specific table
        try:
            qs, _ = parse_section_questions(lines, target_id)
            open_unanswered = [
                q
                for q in qs
                if q.status.strip() in ("Open", "Deferred")
                and q.answer.strip() in ("", "-", "Pending")
            ]
        except Exception as e:
            logging.debug("Failed to parse section questions for '%s': %s", target_id, e)
            open_unanswered = []
    else:
        # No section-specific questions configured, no open questions
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
    
    # Build subsection structure for LLM prompt
    subsection_structure = _build_subsection_structure(lines, span, handler_config)
    
    proposed = llm.generate_open_questions(
        target_id,
        ctx,
        llm_profile=handler_config.llm_profile,
        prior_sections=prior_sections,
        subsection_structure=subsection_structure,
    )

    new_qs = []
    if use_section_qs:
        # For section-specific tables, questions are always for this section
        for item in proposed:
            q_text = (item.get("question") or "").strip()
            if q_text:
                new_qs.append((q_text, iso_today()))
    else:
        # No section-specific table configured, cannot insert questions
        logging.debug(
            "No section-specific questions table configured for '%s', cannot insert questions",
            target_id,
        )
        return lines, False, 0, []

    if new_qs and not dry_run:
        try:
            # Insert into section-specific table
            lines, inserted = insert_section_questions_batch(lines, target_id, new_qs)

            if inserted:
                summaries.append(f"Generated {inserted} open questions for {target_id}")
                return lines, True, inserted, summaries
        except Exception as e:
            logging.warning("Failed to insert questions: %s", e)
            summaries.append(
                f"Generated {len(new_qs)} questions but could not insert (no questions table)"
            )

    return lines, False, 0, summaries
