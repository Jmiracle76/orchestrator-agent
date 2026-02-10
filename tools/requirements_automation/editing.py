from __future__ import annotations
from typing import List
from .config import SECTION_LOCK_RE, PLACEHOLDER_TOKEN
from .utils_io import split_lines
from .sanitize import sanitize_llm_body

def replace_block_body_preserving_markers(lines: List[str], start: int, end: int, *, section_id: str, new_body: str) -> List[str]:
    """Replace a section body while preserving markers, headings, and locks."""
    block_lines = lines[start:end]
    if not block_lines:
        return lines

    # The first line is expected to be the section marker.
    marker_line = block_lines[0]
    heading_line = None
    # Preserve the first nearby heading as the section title.
    for ln in block_lines[1:8]:
        if ln.lstrip().startswith("## ") or ln.lstrip().startswith("### "):
            heading_line = ln
            break

    # Keep the last lock marker and trailing divider if present.
    lock_lines = [ln for ln in block_lines if SECTION_LOCK_RE.search(ln)]
    keep_divider = ("---" in block_lines[-3:])

    new_block: List[str] = [marker_line]
    if heading_line:
        new_block.append(heading_line)

    # Clean any LLM output before inserting into the document.
    body_clean = sanitize_llm_body(section_id, new_body)
    if body_clean:
        new_block.extend(split_lines(body_clean))
    else:
        new_block.append(PLACEHOLDER_TOKEN)

    if lock_lines:
        new_block.append(lock_lines[-1])
    if keep_divider:
        new_block.append("---")

    return lines[:start] + new_block + lines[end:]
