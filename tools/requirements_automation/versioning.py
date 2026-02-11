"""Document versioning system for requirements automation.

Implements semantic versioning tied to workflow completion milestones,
automatically incrementing from 0.0 to 1.0 as sections complete.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from .parsing import find_subsections_within, get_section_span
from .utils_io import iso_today

# Version mapping: section_id → target version
VERSION_MILESTONES = {
    "problem_statement": "0.1",
    "goals_objectives": "0.2",
    "success_criteria": "0.3",
    "stakeholders_users": "0.4",
    "assumptions": "0.5",
    "constraints": "0.6",
    "review_gate:coherence_check": "0.7",
    "requirements": "0.8",
    "interfaces_integrations": "0.8",
    "data_considerations": "0.8",
    "review_gate:final_review": "0.9",
    "approval_record": "1.0",
}


def get_version_for_section(section_id: str) -> str:
    """Return target version when section completes.
    
    Args:
        section_id: Section identifier
        
    Returns:
        Version string (e.g., "0.1") or "0.0" if no milestone defined
    """
    return VERSION_MILESTONES.get(section_id, "0.0")


def _parse_version(version: str) -> Tuple[int, int]:
    """Parse version string into major, minor components.
    
    Args:
        version: Version string in X.Y format
        
    Returns:
        Tuple of (major, minor) integers
        
    Raises:
        ValueError: If version format is invalid
    """
    match = re.match(r"^(\d+)\.(\d+)$", version.strip())
    if not match:
        raise ValueError(f"Invalid version format: {version}. Expected X.Y where X, Y are integers")
    return int(match.group(1)), int(match.group(2))


def _compare_versions(version1: str, version2: str) -> int:
    """Compare two version strings.
    
    Args:
        version1: First version string
        version2: Second version string
        
    Returns:
        Negative if version1 < version2
        Zero if version1 == version2
        Positive if version1 > version2
    """
    major1, minor1 = _parse_version(version1)
    major2, minor2 = _parse_version(version2)
    
    if major1 != major2:
        return major1 - major2
    return minor1 - minor2


def should_increment_version(section_id: str, current_version: str) -> bool:
    """Check if version should increment after section completion.
    
    Args:
        section_id: Section identifier that was completed
        current_version: Current document version
        
    Returns:
        True if version should increment, False otherwise
    """
    target = get_version_for_section(section_id)
    if target == "0.0":
        return False
    
    try:
        return _compare_versions(target, current_version) > 0
    except ValueError:
        # If current version is invalid, allow increment
        return True


def _extract_current_version(lines: List[str]) -> str:
    """Extract current version from document metadata.
    
    Args:
        lines: Document content as list of strings
        
    Returns:
        Current version string or "0.0" if not found
    """
    # Look for <!-- meta:version --> marker
    meta_version_re = re.compile(r"<!--\s*meta:version\s*-->")
    version_value_re = re.compile(r"-\s*\*\*Version:\*\*\s*(\d+\.\d+)")
    
    for i, line in enumerate(lines):
        if meta_version_re.search(line):
            # Check next line for version value
            if i + 1 < len(lines):
                match = version_value_re.search(lines[i + 1])
                if match:
                    return match.group(1)
    
    return "0.0"


def _update_version_history_table(lines: List[str], new_version: str, changes: str) -> List[str]:
    """Add entry to Version History table.
    
    Args:
        lines: Document content as list of strings
        new_version: New version to add to history
        changes: Description of changes for this version
        
    Returns:
        Updated lines with new version history entry
    """
    from .config import AUTOMATION_ACTOR
    
    # Find the Version History subsection
    subsection_marker_re = re.compile(r"<!--\s*subsection:version_history\s*-->")
    placeholder_re = re.compile(r"<!--\s*PLACEHOLDER\s*-->")
    
    result_lines = lines[:]
    marker_idx = None
    placeholder_idx = None
    
    for i, line in enumerate(result_lines):
        if subsection_marker_re.search(line):
            marker_idx = i
        elif marker_idx is not None and placeholder_re.search(line):
            placeholder_idx = i
            break
    
    if placeholder_idx is None:
        # Can't find version history table, return unchanged
        return result_lines
    
    # Create new version entry
    today = iso_today()
    new_entry = f"| {new_version} | {today} | {AUTOMATION_ACTOR} | {changes} |"
    
    # Replace placeholder line with new entry
    result_lines[placeholder_idx] = new_entry
    
    return result_lines


def _update_meta_version(lines: List[str], new_version: str) -> List[str]:
    """Update <!-- meta:version --> marker and associated value.
    
    Args:
        lines: Document content as list of strings
        new_version: New version to set
        
    Returns:
        Updated lines with new version
    """
    meta_version_re = re.compile(r"<!--\s*meta:version\s*-->")
    version_value_re = re.compile(r"(-\s*\*\*Version:\*\*\s*)(\d+\.\d+)")
    
    result_lines = lines[:]
    
    for i, line in enumerate(result_lines):
        if meta_version_re.search(line):
            # Update next line if it contains version value
            if i + 1 < len(result_lines):
                match = version_value_re.search(result_lines[i + 1])
                if match:
                    result_lines[i + 1] = version_value_re.sub(
                        rf"\g<1>{new_version}", result_lines[i + 1]
                    )
                    break
    
    return result_lines


def _update_document_control_table(lines: List[str], new_version: str) -> List[str]:
    """Update Current Version in Document Control table.
    
    Args:
        lines: Document content as list of strings
        new_version: New version to set
        
    Returns:
        Updated lines with new version in Document Control table
    """
    # Find Document Control table and update Current Version row
    table_re = re.compile(r"<!--\s*table:document_control\s*-->")
    version_row_re = re.compile(r"(\|\s*Current Version\s*\|\s*)(\d+\.\d+)(\s*\|)")
    
    result_lines = lines[:]
    in_table = False
    
    for i, line in enumerate(result_lines):
        if table_re.search(line):
            in_table = True
            continue
        
        if in_table:
            match = version_row_re.search(line)
            if match:
                result_lines[i] = version_row_re.sub(rf"\g<1>{new_version}\g<3>", line)
                break
            # Stop if we hit another section marker or empty section
            if line.strip().startswith("<!--") and "section:" in line:
                break
    
    return result_lines


def update_document_version(lines: List[str], new_version: str, changes: str) -> List[str]:
    """Update version metadata throughout the document.
    
    Updates:
    - <!-- meta:version --> marker and associated value
    - Current Version in Document Control table
    - Adds entry to Version History table
    
    Args:
        lines: Document content as list of strings
        new_version: New version to set
        changes: Description of changes for version history
        
    Returns:
        Updated lines with new version information
    """
    result = lines[:]
    
    # Update meta version marker
    result = _update_meta_version(result, new_version)
    
    # Update Document Control table
    result = _update_document_control_table(result, new_version)
    
    # Add entry to Version History
    result = _update_version_history_table(result, new_version, changes)
    
    return result


def get_current_version(lines: List[str]) -> str:
    """Get current document version.
    
    Args:
        lines: Document content as list of strings
        
    Returns:
        Current version string (e.g., "0.1") or "0.0" if not found
    """
    return _extract_current_version(lines)
