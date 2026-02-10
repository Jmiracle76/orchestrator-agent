from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from .config import SECTION_MARKER_RE, SECTION_LOCK_RE, TABLE_MARKER_RE, SUBSECTION_MARKER_RE, PLACEHOLDER_TOKEN
from .models import SectionSpan, SubsectionSpan

def find_sections(lines: List[str]) -> List[SectionSpan]:
    """Locate section markers and return their line spans."""
    starts: List[Tuple[str,int]] = []
    for i, ln in enumerate(lines):
        m = SECTION_MARKER_RE.search(ln)
        if m:
            starts.append((m.group("id"), i))
    spans: List[SectionSpan] = []
    for idx, (sid, start) in enumerate(starts):
        end = starts[idx+1][1] if idx+1 < len(starts) else len(lines)
        spans.append(SectionSpan(sid, start, end))
    return spans

def get_section_span(spans: List[SectionSpan], section_id: str) -> Optional[SectionSpan]:
    """Return the span for a specific section ID, if present."""
    for sp in spans:
        if sp.section_id == section_id:
            return sp
    return None

def validate_required_section_spans(lines: List[str], required_ids: List[str]) -> List[str]:
    """Validate required sections exist, are unique, and non-nested."""
    spans = find_sections(lines)
    by_id: Dict[str, List[SectionSpan]] = {}
    for sp in spans:
        by_id.setdefault(sp.section_id, []).append(sp)

    issues: List[str] = []
    for sid in required_ids:
        hits = by_id.get(sid, [])
        if not hits:
            issues.append(f"Missing required section marker: {sid}")
            continue
        if len(hits) > 1:
            issues.append(f"Duplicate section markers for {sid} (count={len(hits)})")
            continue
        sp = hits[0]
        if sp.end_line <= sp.start_line:
            issues.append(f"Invalid span for {sid}: start={sp.start_line}, end={sp.end_line}")
            continue
        # Ensure section spans do not contain another marker (nested/corrupt).
        inner = "\n".join(lines[sp.start_line+1:sp.end_line])
        if SECTION_MARKER_RE.search(inner):
            issues.append(f"Section {sid} span contains another <!-- section:... --> marker (nested/corrupt).")
    return issues

def section_text(lines: List[str], span: SectionSpan) -> str:
    """Return full raw text for the section span (including markers)."""
    return "\n".join(lines[span.start_line:span.end_line])

def section_body(lines: List[str], span: SectionSpan) -> str:
    """Extract the data-plane body text, excluding markers and headers."""
    block = lines[span.start_line:span.end_line]
    body: List[str] = []
    for ln in block:
        if SECTION_MARKER_RE.search(ln): 
            continue
        if SECTION_LOCK_RE.search(ln):
            continue
        if ln.lstrip().startswith("##"):
            continue
        if ln.strip() == "---":
            continue
        body.append(ln)
    return "\n".join(body).strip("\n")

def section_is_locked(lines: List[str], span: SectionSpan) -> bool:
    """Return True if the last lock marker in the section is lock=true."""
    block = section_text(lines, span)
    locks = list(SECTION_LOCK_RE.finditer(block))
    return bool(locks) and locks[-1].group("lock") == "true"

def section_is_blank(lines: List[str], span: SectionSpan) -> bool:
    """Return True if the placeholder token exists in the section."""
    return PLACEHOLDER_TOKEN in section_text(lines, span)

def find_table_block(lines: List[str], table_id: str) -> Optional[Tuple[int,int]]:
    """Find a markdown table block that follows a <!-- table:... --> marker."""
    marker_line = None
    for i, ln in enumerate(lines):
        m = TABLE_MARKER_RE.search(ln)
        if m and m.group("id") == table_id:
            marker_line = i
            break
    if marker_line is None:
        return None
    start = None
    # Table starts at the first row that begins with a pipe.
    for j in range(marker_line+1, len(lines)):
        if lines[j].lstrip().startswith("|"):
            start = j
            break
        if SECTION_MARKER_RE.search(lines[j]):
            return None
    if start is None:
        return None
    end = start
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1
    return (start, end)

def find_subsections_within(lines: List[str], section_span: SectionSpan) -> List[SubsectionSpan]:
    """Return all subsection spans within a parent section span."""
    starts: List[Tuple[str,int]] = []
    for i in range(section_span.start_line, section_span.end_line):
        m = SUBSECTION_MARKER_RE.search(lines[i])
        if m:
            starts.append((m.group("id"), i))
    subs: List[SubsectionSpan] = []
    for idx, (sid, start) in enumerate(starts):
        end = starts[idx+1][1] if idx+1 < len(starts) else section_span.end_line
        subs.append(SubsectionSpan(sid, start, end))
    return subs

def get_subsection_span(subs: List[SubsectionSpan], subsection_id: str) -> Optional[SubsectionSpan]:
    """Return the span for a specific subsection ID, if present."""
    for s in subs:
        if s.subsection_id == subsection_id:
            return s
    return None
