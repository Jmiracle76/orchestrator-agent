from __future__ import annotations

import re
from typing import List

from .config import SECTION_LOCK_RE, SECTION_MARKER_RE, TABLE_MARKER_RE


def sanitize_llm_body(section_id: str, body: str) -> str:
    """Normalize LLM output by removing markers, headers, and duplicates."""
    if not body:
        return ""
    lines = body.splitlines()
    cleaned: List[str] = []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            cleaned.append("")
            continue
        # Strip any structural markers or headings that should not re-enter the doc.
        if SECTION_MARKER_RE.search(s) or SECTION_LOCK_RE.search(s) or TABLE_MARKER_RE.search(s):
            continue
        if s.strip() == "---":
            continue
        if s.strip().startswith("<!--") and s.strip().endswith("-->"):
            continue
        if s.lstrip().startswith("#"):
            continue
        cleaned.append(s)

    # Assumptions should avoid constraint headings and duplicates.
    if section_id == "assumptions":
        keep: List[str] = []
        for s in cleaned:
            st = s.strip()
            if not st:
                keep.append("")
                continue
            if st.startswith("###") or st.startswith("##"):
                continue
            if re.match(
                r"(?i)^technical constraints|^operational constraints|^resource constraints", st
            ):
                continue
            keep.append(s)
        seen = set()
        deduped: List[str] = []
        for s in keep:
            st = s.strip()
            if not st:
                deduped.append("")
                continue
            norm = re.sub(r"\s+", " ", re.sub(r"^[\-\*\d]+\.\s*", "", st)).strip().lower()
            if norm in seen:
                continue
            seen.add(norm)
            deduped.append(s)
        cleaned = deduped

    # Constraints should only keep the known constraint sub-headings.
    elif section_id == "constraints":
        allowed = {
            "### Technical Constraints",
            "### Operational Constraints",
            "### Resource Constraints",
        }
        keep_constraints: List[str] = []
        for s in cleaned:
            st = s.strip()
            if not st:
                keep_constraints.append("")
                continue
            if st.startswith("###"):
                if st in allowed:
                    keep_constraints.append(st)
                continue
            if st.startswith("##"):
                continue
            keep_constraints.append(s)
        cleaned = keep_constraints

    # Collapse repeated blank lines to keep formatting tight.
    out: List[str] = []
    blank_run = 0
    for s in cleaned:
        if not s.strip():
            blank_run += 1
            if blank_run > 1:
                continue
            out.append("")
        else:
            blank_run = 0
            out.append(s)

    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()

    return "\n".join(out).strip()
