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

    # Check for placeholder token
    has_placeholder = any(
        PLACEHOLDER_TOKEN in line for line in lines[span.start_line : span.end_line]
    )

    # Determine if using section-specific questions
    use_section_qs = (
        handler_config is not None
        and hasattr(handler_config, "questions_table")
        and handler_config.questions_table is not None
    )

    # Check for open questions
    if use_section_qs:
        # Try section-specific table first
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
                "Failed to parse section questions for '%s': %s, falling back to global",
                target_id,
                e,
            )
            # Fall back to global table
            use_section_qs = False

    if not use_section_qs:
        # Use global questions table
        try:
            open_qs, _, _ = open_questions_parse(lines)
        except Exception as e:
            logging.warning("Failed to parse open questions: %s", e)
            open_qs = []

        # Include subsections when checking questions
        subs = find_subsections_within(lines, span)
        target_ids = {target_id} | {s.subsection_id for s in subs}

        targeted_questions = [q for q in open_qs if _canon_target(q.section_target) in target_ids]

        has_open_questions = any(
            q.status.strip() in ("Open", "Deferred") and q.answer.strip() in ("", "-", "Pending")
            for q in targeted_questions
        )

        # Note: Questions with status "Open"/"Deferred" and non-empty answers
        # are considered "answered but not yet integrated". After integration,
        # they are marked as "Resolved" by the phase processors.
        has_answered_questions = any(
            q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
            for q in targeted_questions
        )

    return SectionState(
        section_id=target_id,
        exists=True,
        locked=locked,
        is_blank=is_blank,
        has_placeholder=has_placeholder,
        has_open_questions=has_open_questions,
        has_answered_questions=has_answered_questions,
    )


def gather_prior_sections(
    lines: List[str], workflow_order: List[str], target_id: str
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

        # Check if section is complete
        state = get_section_state(lines, section_id)

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
