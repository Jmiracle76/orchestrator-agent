"""Table content extraction and routing logic for LLM-generated content.

This module handles extracting table rows from LLM output and routing them
to the correct table subsections (e.g., functional_requirements, non_functional_requirements).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .parsing import find_subsections_within, get_subsection_span
from .models import SectionSpan, SubsectionSpan
from .config import SUBSECTION_MARKER_RE, TABLE_MARKER_RE, PLACEHOLDER_TOKEN


# Constants for markdown parsing
SUBSECTION_HEADER_PREFIX = "###"  # Markdown subsection header marker


def _extract_markdown_table_rows(text: str) -> List[str]:
    """Extract markdown table data rows from text.
    
    Extracts lines that appear to be markdown table rows (contain pipes).
    Skips header rows and separator rows.
    
    Args:
        text: Text containing potential markdown tables
        
    Returns:
        List of table row strings (without leading/trailing whitespace)
    """
    lines = text.split('\n')
    rows = []
    
    for line in lines:
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Must contain pipes to be a table row
        if '|' not in stripped:
            continue
        # Skip separator rows (e.g., |---|---|)
        if re.match(r'^\s*\|[\s\-:|]+\|\s*$', stripped):
            continue
        
        # All other pipe-delimited lines are considered table rows
        # The separator row check above is sufficient to filter out headers in most cases
        rows.append(stripped)
    
    return rows


def _identify_table_content_by_subsection(
    llm_output: str,
    subsection_structure: Optional[List[dict]]
) -> Dict[str, List[str]]:
    """Identify which table rows belong to which subsection.
    
    Parses LLM output looking for subsection headers followed by table content.
    
    Args:
        llm_output: LLM-generated text
        subsection_structure: List of subsection dicts with 'id' and 'type' keys
        
    Returns:
        Dict mapping subsection_id to list of table row strings
    """
    if not subsection_structure:
        return {}
    
    # Build map of table subsections
    table_subsections = {
        sub['id']: sub for sub in subsection_structure 
        if sub.get('type') == 'table'
    }
    
    if not table_subsections:
        return {}
    
    result: Dict[str, List[str]] = {sid: [] for sid in table_subsections.keys()}
    
    # Split by subsection headers
    lines = llm_output.split('\n')
    current_subsection: Optional[str] = None
    
    for line in lines:
        stripped = line.strip()
        
        # Check if this is a subsection header
        if stripped.startswith(SUBSECTION_HEADER_PREFIX):
            # Extract subsection name and convert to id format
            header_text = stripped[len(SUBSECTION_HEADER_PREFIX):].strip()
            # Normalize to subsection ID format: lowercase, spaces to underscores, remove special chars
            # Examples: "Functional Requirements" -> "functional_requirements"
            #           "Questions & Issues" -> "questions_issues"
            #           "Non-Functional  Requirements" -> "non_functional_requirements"
            subsection_id = re.sub(r'[^a-z0-9]+', '_', header_text.lower()).strip('_')
            
            # Check if this matches a table subsection we know about
            if subsection_id in table_subsections:
                current_subsection = subsection_id
            else:
                current_subsection = None
            continue
        
        # If we're in a table subsection, collect table rows
        if current_subsection and '|' in stripped:
            # Skip separator and header rows
            if re.match(r'^\s*\|[\s\-:|]+\|\s*$', stripped):
                continue
            result[current_subsection].append(stripped)
    
    return result


def _extract_non_table_content(llm_output: str) -> str:
    """Extract non-table content from LLM output (content for preamble).
    
    Removes table rows and subsection headers, keeping prose/list content.
    
    Args:
        llm_output: LLM-generated text
        
    Returns:
        Non-table content suitable for preamble
    """
    lines = llm_output.split('\n')
    filtered = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines at start/end (will be normalized later)
        if not stripped:
            # Keep empty lines in the middle for paragraph separation
            if filtered:
                filtered.append('')
            continue
        
        # Skip subsection headers (###)
        if stripped.startswith(SUBSECTION_HEADER_PREFIX):
            continue
        
        # Skip table rows
        if '|' in stripped:
            # Check if it's a table row
            if re.match(r'^\s*\|.*\|\s*$', stripped):
                continue
        
        filtered.append(line)
    
    # Join and normalize whitespace
    result = '\n'.join(filtered).strip()
    # Normalize multiple blank lines to single blank line
    result = re.sub(r'\n\n\n+', '\n\n', result)
    
    return result


def _insert_table_rows_into_subsection(
    lines: List[str],
    subsection_span: SubsectionSpan,
    table_rows: List[str]
) -> List[str]:
    """Insert table rows into a table subsection, replacing placeholders.
    
    Args:
        lines: Document lines
        subsection_span: Span of the subsection containing the table
        table_rows: List of markdown table row strings to insert
        
    Returns:
        Updated document lines
    """
    if not table_rows:
        return lines
    
    # Find the table within the subsection
    # Look for the table header row (contains | and typically column names)
    subsection_lines = lines[subsection_span.start_line:subsection_span.end_line]
    
    table_start = None
    header_row_idx = None
    separator_row_idx = None
    
    for i, line in enumerate(subsection_lines):
        if '|' in line:
            stripped = line.strip()
            # Found a table row
            if table_start is None:
                table_start = i
                # First row is likely the header
                if not re.match(r'^\s*\|[\s\-:|]+\|\s*$', stripped):
                    header_row_idx = i
            # Check for separator row
            elif re.match(r'^\s*\|[\s\-:|]+\|\s*$', stripped):
                separator_row_idx = i
                # Stop after separator - data rows should follow
                break
    
    if table_start is None or header_row_idx is None or separator_row_idx is None:
        # No table structure found - can't insert
        return lines
    
    # Insertion point is after the separator row
    insert_idx = subsection_span.start_line + separator_row_idx + 1
    
    # Find the end of existing table content (up to next blank line or subsection)
    table_end_idx = insert_idx
    for i in range(insert_idx, subsection_span.end_line):
        line = lines[i].strip()
        # Stop at blank line, next subsection, or section lock
        if not line or line.startswith('<!--'):
            table_end_idx = i
            break
        table_end_idx = i + 1
    
    # Remove any placeholder rows
    existing_content = lines[insert_idx:table_end_idx]
    non_placeholder_rows = [
        ln for ln in existing_content 
        if PLACEHOLDER_TOKEN not in ln and ln.strip()
    ]
    
    # Build new table content
    new_table_content = []
    
    # Keep any existing non-placeholder rows
    new_table_content.extend(non_placeholder_rows)
    
    # Add new rows from LLM
    new_table_content.extend(table_rows)
    
    # Reconstruct document
    result = (
        lines[:insert_idx] +
        new_table_content +
        lines[table_end_idx:]
    )
    
    return result


def route_table_content_to_subsections(
    lines: List[str],
    section_span: SectionSpan,
    llm_output: str,
    subsection_structure: Optional[List[dict]]
) -> Tuple[List[str], str]:
    """Route table content from LLM output to appropriate table subsections.
    
    Extracts table rows from LLM output and inserts them into the correct
    table subsections (e.g., functional_requirements, non_functional_requirements).
    Returns the modified document lines and any non-table content for the preamble.
    
    Args:
        lines: Document lines
        section_span: Span of the section being edited
        llm_output: LLM-generated content (may contain tables and prose)
        subsection_structure: List of subsection dicts with 'id' and 'type' keys
        
    Returns:
        Tuple of (updated_lines, preamble_content)
        - updated_lines: Document with table content inserted into subsections
        - preamble_content: Non-table content suitable for section preamble
    """
    if not subsection_structure:
        # No subsection structure - return everything as preamble
        return lines, llm_output
    
    # Identify table content by subsection
    table_content_map = _identify_table_content_by_subsection(llm_output, subsection_structure)
    
    # Check if there's any table content to route
    has_table_content = any(rows for rows in table_content_map.values())
    
    if not has_table_content:
        # No table content found - return everything as preamble
        return lines, llm_output
    
    # Get subsections within the section
    subsections = find_subsections_within(lines, section_span)
    
    # Insert table content into each subsection
    result_lines = lines
    for subsection_id, table_rows in table_content_map.items():
        if not table_rows:
            continue
        
        # Find the subsection span
        subspan = get_subsection_span(subsections, subsection_id)
        if not subspan:
            continue
        
        # Insert rows into the subsection
        result_lines = _insert_table_rows_into_subsection(
            result_lines,
            subspan,
            table_rows
        )
    
    # Extract non-table content for preamble
    preamble_content = _extract_non_table_content(llm_output)
    
    return result_lines, preamble_content
