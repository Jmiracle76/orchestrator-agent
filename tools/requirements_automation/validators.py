from __future__ import annotations

from typing import List, Tuple

from .config import PHASES, TARGET_CANONICAL_MAP
from .parsing import (
    find_sections,
    get_section_span,
    section_is_blank,
    section_is_locked,
)
from .section_questions import parse_section_questions


def _canon_target(t: str) -> str:
    """Normalize section targets so aliases map to canonical section IDs."""
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)


def validate_section_complete(section_id: str, lines: List[str]) -> Tuple[bool, List[str]]:
    """Return completeness for a single section target.
    
    DEPRECATED: This function is legacy and should be replaced with handler-config-aware
    validation that properly checks per-section question tables. It now attempts to use
    per-section questions but may not work correctly without handler configuration.
    """
    issues: List[str] = []
    spans = find_sections(lines)
    sp = get_section_span(spans, section_id)
    if not sp:
        return False, [f"Missing section: {section_id}"]
    if section_is_locked(lines, sp):
        return True, []

    if section_is_blank(lines, sp):
        return False, [f"Section still blank: {section_id}"]

    # Try to use per-section questions table
    try:
        # parse_section_questions returns (questions, table_span)
        # We only need the questions list for validation
        qs, _ = parse_section_questions(lines, section_id)
        # Check for open questions
        if any(q.status.strip() == "Open" for q in qs):
            issues.append(f"Open questions remain for section: {section_id}")
    except Exception:
        # If section questions table doesn't exist, assume no open questions
        pass

    return (len(issues) == 0), issues


def validate_phase_1_complete(lines: List[str]) -> Tuple[bool, List[str]]:
    """Phase 1 completes when sections are filled and open questions resolved.
    
    DEPRECATED: This function is legacy and should be replaced with handler-config-aware
    validation that properly checks per-section question tables. It now attempts to use
    per-section questions but may not work correctly without handler configuration.
    """
    issues: List[str] = []
    spans = find_sections(lines)

    for sid in PHASES["phase_1_intent_scope"]:
        sp = get_section_span(spans, sid)
        if not sp:
            issues.append(f"Missing section: {sid}")
            continue
        if section_is_blank(lines, sp):
            issues.append(f"Section still blank: {sid}")
        # Phase 1 requires no remaining Open questions targeting this section.
        try:
            qs, _ = parse_section_questions(lines, sid)
            if any(q.status.strip() == "Open" for q in qs):
                issues.append(f"Open questions remain for section: {sid}")
        except Exception:
            # If section questions table doesn't exist, assume no open questions
            pass
    return (len(issues) == 0), issues


def validate_phase_2_complete(lines: List[str]) -> Tuple[bool, List[str]]:
    """Phase 2 completes when sections are filled and no Open/Deferred remain.
    
    DEPRECATED: This function is legacy and should be replaced with handler-config-aware
    validation that properly checks per-section question tables. It now attempts to use
    per-section questions but may not work correctly without handler configuration.
    """
    issues: List[str] = []
    spans = find_sections(lines)

    for sid in PHASES["phase_2_assumptions_constraints"]:
        sp = get_section_span(spans, sid)
        if not sp:
            issues.append(f"Missing section: {sid}")
            continue
        if section_is_blank(lines, sp):
            issues.append(f"Section still blank: {sid}")
        # Phase 2 requires Open or Deferred questions to be resolved.
        try:
            qs, _ = parse_section_questions(lines, sid)
            if any(q.status.strip() in ("Open", "Deferred") for q in qs):
                issues.append(f"Open questions remain for section: {sid}")
        except Exception:
            # If section questions table doesn't exist, assume no open questions
            pass
    return (len(issues) == 0), issues
