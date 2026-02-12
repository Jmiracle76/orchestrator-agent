"""Section handler execution logic."""

from __future__ import annotations

import logging
import re
from typing import Any, List

from .config import PHASES
from .formatting import format_review_gate_output
from .models import SectionState, WorkflowResult
from .open_questions import open_questions_parse
from .parsing import find_sections, get_section_span, section_is_blank
from .phases import process_phase_1, process_phase_2, process_placeholder_phase
from .review_gate_handler import ReviewGateHandler
from .runner_integration import (
    draft_section_content,
    generate_questions_for_section,
    integrate_answered_questions,
)
from .runner_state import _canon_target, get_section_state


def execute_review_gate(
    lines: List[str],
    target_id: str,
    llm: Any,
    doc_type: str,
    handler_config: Any,
    dry_run: bool = False,
) -> tuple[List[str], WorkflowResult]:
    """
    Execute a review gate handler.

    Args:
        lines: Document content as list of strings
        target_id: Review gate ID
        llm: LLM client instance
        doc_type: Document type
        handler_config: Handler configuration from registry
        dry_run: If True, don't modify the document

    Returns:
        Tuple of (updated_lines, WorkflowResult)
    """
    # Execute review gate
    handler = ReviewGateHandler(llm, lines, doc_type)
    review_result = handler.execute_review(target_id, handler_config)

    # Get any document changes made during execute_review (e.g., section locks, approval updates)
    lines = handler.lines

    # Write review gate result marker to document
    lines, marker_changed = handler.write_review_gate_result(review_result, lines)

    # Sync handler state with updated document lines (now includes result marker)
    handler.lines = lines

    # Insert issues/warnings into section-specific question tables
    lines, questions_inserted = handler.insert_issues_into_section_tables(review_result, lines)

    # Sync handler state again after inserting questions
    handler.lines = lines

    # Optionally apply patches
    lines, patches_applied = handler.apply_patches_if_configured(review_result, handler_config)

    # Convert to WorkflowResult
    result = WorkflowResult(
        target_id=target_id,
        action_taken="review_gate",
        changed=marker_changed or patches_applied or questions_inserted > 0,
        blocked=not review_result.passed,
        blocked_reasons=[
            f"{i.severity}: {i.description}"
            for i in review_result.issues
            if i.severity == "blocker"
        ],
        summaries=[review_result.summary]
        + [f"{i.severity}: {i.description}" for i in review_result.issues],
        questions_generated=questions_inserted,
        questions_resolved=0,
    )

    # Log formatted output for human readability
    formatted_output = format_review_gate_output(result)
    if formatted_output:
        print(formatted_output)

    return lines, result


def execute_unified_handler(
    lines: List[str],
    target_id: str,
    state: SectionState,
    llm: Any,
    handler_config: Any,
    prior_sections: dict[str, str],
    dry_run: bool = False,
) -> tuple[List[str], WorkflowResult]:
    """
    Execute unified handler using handler config parameters.

    This implements the integrate-then-questions pattern using configuration
    from the handler registry, replacing hardcoded phase-specific logic.

    Args:
        lines: Document content as list of strings
        target_id: Section ID to process
        state: Section state information
        llm: LLM client instance
        handler_config: Handler configuration from registry
        prior_sections: Dict of completed section IDs to their content
        dry_run: If True, don't modify the document

    Returns:
        Tuple of (updated_lines, WorkflowResult)
    """
    changed = False
    blocked_reasons = []
    summaries = []
    questions_generated = 0
    questions_resolved = 0

    # Step 1: If section has answered questions, integrate them
    lines, int_changed, int_resolved, int_summaries = integrate_answered_questions(
        lines, target_id, llm, handler_config, prior_sections, dry_run
    )

    if int_changed:
        changed = True
        questions_resolved = int_resolved
        summaries.extend(int_summaries)

    # Get updated section span after integration
    spans = find_sections(lines)
    span = get_section_span(spans, target_id)

    if not span:
        return lines, WorkflowResult(
            target_id=target_id,
            action_taken="error",
            changed=False,
            blocked=True,
            blocked_reasons=[f"Section span not found: {target_id}"],
            summaries=[],
            questions_generated=0,
            questions_resolved=0,
        )

    # Step 2: Check if section is still blank after integration
    is_blank = section_is_blank(lines, span)

    # Step 2.5: If section is blank and prior context is available, try drafting first
    # Skip drafting if answered_questions exist because Step 1 just integrated them
    if is_blank and prior_sections and not int_changed:
        lines, draft_changed, draft_summaries = draft_section_content(
            lines, target_id, llm, handler_config, prior_sections, dry_run
        )

        if draft_changed:
            changed = True
            summaries.extend(draft_summaries)

            # Re-check if section is still blank after drafting
            spans = find_sections(lines)
            span = get_section_span(spans, target_id)
            if span is not None:
                is_blank = section_is_blank(lines, span)

    # Step 3: If section is blank and no open questions exist, generate new ones
    if is_blank:
        lines, gen_changed, gen_count, gen_summaries = generate_questions_for_section(
            lines, target_id, llm, handler_config, prior_sections, dry_run
        )

        if gen_changed:
            changed = True
            questions_generated = gen_count
            summaries.extend(gen_summaries)
        elif gen_count == 0 and not gen_changed:
            # Section is blank but has open questions - blocked waiting for answers
            try:
                from .section_questions import parse_section_questions

                # Try to get section-specific questions
                if handler_config and hasattr(handler_config, "questions_table") and handler_config.questions_table:
                    try:
                        qs, _ = parse_section_questions(lines, target_id)
                        open_unanswered = [
                            q
                            for q in qs
                            if q.status.strip() in ("Open", "Deferred")
                            and q.answer.strip() in ("", "-", "Pending")
                        ]

                        if open_unanswered:
                            blocked_reasons.append(
                                f"Waiting for {len(open_unanswered)} questions to be answered"
                            )
                    except Exception:
                        # No section questions available
                        pass
            except Exception:
                pass

    # Determine action taken
    action = "no_action"
    if questions_generated > 0:
        action = "question_gen"
    elif questions_resolved > 0 or changed:
        action = "integration"

    return lines, WorkflowResult(
        target_id=target_id,
        action_taken=action,
        changed=changed,
        blocked=len(blocked_reasons) > 0,
        blocked_reasons=blocked_reasons,
        summaries=summaries,
        questions_generated=questions_generated,
        questions_resolved=questions_resolved,
    )


def execute_phase_based_handler(
    lines: List[str], target_id: str, llm: Any, dry_run: bool = False
) -> tuple[List[str], WorkflowResult]:
    """
    Execute phase-based handler for backward compatibility.

    Args:
        lines: Document content as list of strings
        target_id: Section ID to process
        llm: LLM client instance
        dry_run: If True, don't modify the document

    Returns:
        Tuple of (updated_lines, WorkflowResult)
    """
    # Map section to phase for backward compatibility
    phase_name = None
    for phase, sections in PHASES.items():
        if target_id in sections:
            phase_name = phase
            break

    if not phase_name:
        # Unknown section, use placeholder processor
        lines, changed, blocked, needs_human, summaries = process_placeholder_phase(
            target_id, lines, llm, dry_run
        )
        return lines, WorkflowResult(
            target_id=target_id,
            action_taken="placeholder",
            changed=changed,
            blocked=len(blocked) > 0,
            blocked_reasons=blocked,
            summaries=summaries,
            questions_generated=0,
            questions_resolved=0,
        )

    # Count questions before processing
    try:
        open_qs_before, _, _ = open_questions_parse(lines)
        questions_before = len(
            [q for q in open_qs_before if _canon_target(q.section_target) == target_id]
        )
    except Exception:
        questions_before = 0

    # Call appropriate phase processor
    if phase_name == "phase_1_intent_scope":
        lines, changed, blocked, needs_human, summaries = process_phase_1(
            lines, llm, dry_run, target_section=target_id
        )
    elif phase_name == "phase_2_assumptions_constraints":
        lines, changed, blocked, needs_human, summaries = process_phase_2(
            lines, llm, dry_run, target_section=target_id
        )
    else:
        lines, changed, blocked, needs_human, summaries = process_placeholder_phase(
            target_id, lines, llm, dry_run
        )

    # Count questions after processing
    try:
        open_qs_after, _, _ = open_questions_parse(lines)
        questions_after = len(
            [q for q in open_qs_after if _canon_target(q.section_target) == target_id]
        )
        resolved_count = 0
        # Count resolved questions from summaries
        for summary in summaries:
            if "resolved" in summary.lower():
                # Try to extract count from summary
                match = re.search(r"(\d+)\s+questions?\s+resolved", summary.lower())
                if match:
                    resolved_count = int(match.group(1))
    except Exception:
        questions_after = 0
        resolved_count = 0

    questions_generated = max(0, questions_after - questions_before)

    # Determine action taken
    action = "no_action"
    if questions_generated > 0:
        action = "question_gen"
    elif resolved_count > 0 or changed:
        action = "integration"

    return lines, WorkflowResult(
        target_id=target_id,
        action_taken=action,
        changed=changed,
        blocked=len(blocked) > 0,
        blocked_reasons=blocked,
        summaries=summaries,
        questions_generated=questions_generated,
        questions_resolved=resolved_count,
    )
