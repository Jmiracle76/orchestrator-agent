from __future__ import annotations
from typing import List, Tuple
from .config import PHASES, TARGET_CANONICAL_MAP
from .parsing import find_sections, get_section_span, section_is_blank
from .open_questions import open_questions_parse

def _canon_target(t: str) -> str:
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)

def validate_phase_1_complete(lines: List[str]) -> Tuple[bool, List[str]]:
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
        if any(_canon_target(q.section_target) == sid and q.status.strip() == "Open" for q in open_qs):
            issues.append(f"Open questions remain for section: {sid}")
    return (len(issues) == 0), issues

def validate_phase_2_complete(lines: List[str]) -> Tuple[bool, List[str]]:
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
        if any(q.section_target.strip() == sid and q.status.strip() in ("Open", "Deferred") for q in open_qs):
            issues.append(f"Open questions remain for section: {sid}")
    return (len(issues) == 0), issues
