from __future__ import annotations
from typing import List
from .config import SECTION_LOCK_RE, PLACEHOLDER_TOKEN
from .utils_io import split_lines
from .sanitize import sanitize_llm_body
from .structural_validator import StructuralValidator
from .validation_errors import StructuralError, InvalidSpanError

def replace_block_body_preserving_markers(lines: List[str], start: int, end: int, *, section_id: str, new_body: str) -> List[str]:
    """
    Replace a section body while preserving markers, headings, and locks.
    
    Validates document structure before and after the replacement to prevent corruption.
    
    Args:
        lines: Document content as list of strings
        start: Start line index of section span
        end: End line index of section span
        section_id: ID of the section being edited
        new_body: New body content to insert
        
    Returns:
        Updated document lines
        
    Raises:
        InvalidSpanError: If span is invalid
        StructuralError: If edit would corrupt structure
    """
    # Validate structure before edit
    validator = StructuralValidator(lines)
    validator.validate_or_raise()
    
    # Validate span is sensible
    if start >= end:
        if start == end:
            raise InvalidSpanError(section_id, f"Empty span: start={start} equals end={end}")
        else:
            raise InvalidSpanError(section_id, f"Invalid span: start={start} is greater than end={end}")
    
    if start < 0 or end > len(lines):
        raise InvalidSpanError(section_id, f"Span out of bounds: start={start}, end={end}, len={len(lines)}")
    
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

    new_lines = lines[:start] + new_block + lines[end:]
    
    # Validate structure after edit
    validator_after = StructuralValidator(new_lines)
    errors_after = validator_after.validate_all()
    if errors_after:
        raise StructuralError(
            f"Edit to '{section_id}' would corrupt structure: {errors_after[0]}"
        )
    
    return new_lines
