"""Section state management for workflow runner."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from .config import PLACEHOLDER_TOKEN, TARGET_CANONICAL_MAP
from .models import SectionSpan, SectionState, SubsectionSpan
from .open_questions import open_questions_parse
from .parsing import (
    find_sections,
    find_subsections_within,
    get_section_span,
    has_placeholder,
    section_body,
    section_is_blank,
    section_is_locked,
)
from .section_questions import (
    has_open_section_questions,
    parse_section_questions,
    section_has_answered_questions,
)


def _canon_target(t: str) -> str:
    """Normalize alias section IDs to canonical targets."""
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)


def _get_replacement_end_boundary(
    lines: List[str], section_span: SectionSpan, subsections: List[SubsectionSpan]
) -> int:
    """
    Calculate the effective end boundary for section body replacement.

    If the section contains a 'questions_issues' or 'open_questions' subsection,
    returns the line where that subsection starts to prevent overwriting it.
    Otherwise, returns the original section end boundary.

    Args:
        lines: Document content as list of strings
        section_span: SectionSpan object for the section
        subsections: List of SubsectionSpan objects within the section

    Returns:
        Line number to use as end boundary for replacement
    """
    # Check for questions_issues (new style) or open_questions (legacy) subsection
    for sub in subsections:
        if sub.subsection_id in ("questions_issues", "open_questions"):
            # Return the start line of the questions subsection as the boundary
            return sub.start_line

    # No questions subsection found, use the full section span
    return section_span.end_line


def get_section_state(
    lines: List[str], target_id: str, handler_config: Optional[Any] = None
) -> SectionState:
    """
    Extract section state for decision-making.

    Args:
        lines: Document content as list of strings
        target_id: Section ID to analyze
        handler_config: Optional handler configuration (to determine question table)

    Returns:
        SectionState object with section information
    """
    spans = find_sections(lines)
    span = get_section_span(spans, target_id)

    if not span:
        return SectionState(
            section_id=target_id,
            exists=False,
            locked=False,
            is_blank=False,
            has_placeholder=False,
            has_open_questions=False,
            has_answered_questions=False,
        )

    locked = section_is_locked(lines, span)
    is_blank = section_is_blank(lines, span)

    # Check for placeholder token in preamble only (ignoring subsections)
    section_has_placeholder = has_placeholder(span, lines)

    # Determine if using section-specific questions
    use_section_qs = (
        handler_config is not None
        and hasattr(handler_config, "questions_table")
        and handler_config.questions_table is not None
    )

    # Initialize question state
    has_open_questions = False
    has_answered_questions = False

    # Check for open questions
    if use_section_qs:
        # Use section-specific table
        try:
            qs, _ = parse_section_questions(lines, target_id)
            has_open_questions = any(
                q.status.strip() in ("Open", "Deferred")
                and q.answer.strip() in ("", "-", "Pending")
                for q in qs
            )
            has_answered_questions = any(
                q.answer.strip() not in ("", "-", "Pending")
                and q.status.strip() in ("Open", "Deferred")
                for q in qs
            )
        except Exception as e:
            logging.debug(
                "Failed to parse section questions for '%s': %s",
                target_id,
                e,
            )
            # When handler_config is None or section table parsing fails,
            # default to no questions rather than falling back to global table
            has_open_questions = False
            has_answered_questions = False
    elif handler_config is None:
        # When handler_config is None, try to use section-specific questions
        # using the naming convention {section_id}_questions
        try:
            qs, _ = parse_section_questions(lines, target_id)
            has_open_questions = any(
                q.status.strip() in ("Open", "Deferred")
                and q.answer.strip() in ("", "-", "Pending")
                for q in qs
            )
            has_answered_questions = any(
                q.answer.strip() not in ("", "-", "Pending")
                and q.status.strip() in ("Open", "Deferred")
                for q in qs
            )
        except Exception:
            # If section table doesn't exist, default to no questions
            has_open_questions = False
            has_answered_questions = False

    return SectionState(
        section_id=target_id,
        exists=True,
        locked=locked,
        is_blank=is_blank,
        has_placeholder=section_has_placeholder,
        has_open_questions=has_open_questions,
        has_answered_questions=has_answered_questions,
    )


def gather_prior_sections(
    lines: List[str],
    workflow_order: List[str],
    target_id: str,
    handler_registry: Optional[Any] = None,
    doc_type: Optional[str] = None,
) -> dict[str, str]:
    """
    Gather completed prior section content before the target section.

    Iterates through workflow_order up to (but not including) target_id,
    skips review gates, checks if each section is complete (no placeholder,
    no open questions), and extracts the section body.

    Args:
        lines: Document content as list of strings
        workflow_order: List of workflow target IDs
        target_id: Section ID to gather prior sections for
        handler_registry: Optional handler registry for looking up section configs
        doc_type: Optional document type for looking up section configs

    Returns:
        Dict mapping section_id → body content for all completed prior sections
    """
    from .config import is_special_workflow_target

    prior_sections: dict[str, str] = {}

    # Find the index of target_id in workflow_order
    try:
        target_index = workflow_order.index(target_id)
    except ValueError:
        # Target not in workflow order, return empty dict
        return prior_sections

    # Parse sections once for efficiency
    spans = find_sections(lines)

    # Iterate through sections before target_id
    for section_id in workflow_order[:target_index]:
        # Skip review gates
        if is_special_workflow_target(section_id):
            continue

        # Get handler config for this section if available
        handler_config = None
        if handler_registry and doc_type:
            try:
                handler_config = handler_registry.get_handler_config(doc_type, section_id)
            except Exception:
                # If handler config not found, continue without it
                pass

        # Check if section is complete
        state = get_section_state(lines, section_id, handler_config)

        # Section must exist, not be blank, have no placeholder, and no open questions
        if not state.exists:
            continue
        if state.has_placeholder or state.has_open_questions:
            continue

        # Extract section body
        span = get_section_span(spans, section_id)

        if span:
            body = section_body(lines, span)
            # Only include non-empty sections
            if body.strip():
                prior_sections[section_id] = body

    return prior_sections
