from __future__ import annotations

from typing import List, Tuple

from .config import PHASES, TARGET_CANONICAL_MAP
from .open_questions import open_questions_parse
from .parsing import (
    find_sections,
    find_subsections_within,
    get_section_span,
    section_is_blank,
    section_is_locked,
)


def _canon_target(t: str) -> str:
    """Normalize section targets so aliases map to canonical section IDs."""
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)


def validate_section_complete(section_id: str, lines: List[str]) -> Tuple[bool, List[str]]:
    """Return completeness for a single section target."""
    issues: List[str] = []
    spans = find_sections(lines)
    sp = get_section_span(spans, section_id)
    if not sp:
        return False, [f"Missing section: {section_id}"]
    if section_is_locked(lines, sp):
        return True, []

    if section_is_blank(lines, sp):
        return False, [f"Section still blank: {section_id}"]

    try:
        open_qs, _, _ = open_questions_parse(lines)
    except Exception as e:
        return False, [f"Open Questions parse failed: {e}"]

    subs = find_subsections_within(lines, sp)
    target_ids = {section_id} | {s.subsection_id for s in subs}
    for q in open_qs:
        if q.status.strip() != "Open":
            continue
        if _canon_target(q.section_target) in target_ids:
            issues.append(f"Open questions remain for section: {section_id}")
            break

    return (len(issues) == 0), issues


def validate_phase_1_complete(lines: List[str]) -> Tuple[bool, List[str]]:
    """Phase 1 completes when sections are filled and open questions resolved."""
    issues: List[str] = []
    spans = find_sections(lines)
    try:
        open_qs, _, _ = open_questions_parse(lines)
    except Exception as e:
        return False, [f"Open Questions parse failed: {e}"]

    for sid in PHASES["phase_1_intent_scope"]:
        sp = get_section_span(spans, sid)
        if not sp:
            issues.append(f"Missing section: {sid}")
            continue
        if section_is_blank(lines, sp):
            issues.append(f"Section still blank: {sid}")
        # Phase 1 requires no remaining Open questions targeting this section.
        if any(
            _canon_target(q.section_target) == sid and q.status.strip() == "Open" for q in open_qs
        ):
            issues.append(f"Open questions remain for section: {sid}")
    return (len(issues) == 0), issues


def validate_phase_2_complete(lines: List[str]) -> Tuple[bool, List[str]]:
    """Phase 2 completes when sections are filled and no Open/Deferred remain."""
    issues: List[str] = []
    spans = find_sections(lines)
    try:
        open_qs, _, _ = open_questions_parse(lines)
    except Exception as e:
        return False, [f"Open Questions parse failed: {e}"]

    for sid in PHASES["phase_2_assumptions_constraints"]:
        sp = get_section_span(spans, sid)
        if not sp:
            issues.append(f"Missing section: {sid}")
            continue
        if section_is_blank(lines, sp):
            issues.append(f"Section still blank: {sid}")
        # Phase 2 requires Open or Deferred questions to be resolved.
        if any(
            q.section_target.strip() == sid and q.status.strip() in ("Open", "Deferred")
            for q in open_qs
        ):
            issues.append(f"Open questions remain for section: {sid}")
    return (len(issues) == 0), issues
