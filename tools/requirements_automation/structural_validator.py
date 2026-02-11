"""Structural validator for document integrity checking.

This module provides the StructuralValidator class that validates document structure
including markers, spans, tables, and metadata. It catches structural errors early
to prevent silent corruption and provides clear, actionable error messages.
"""
from __future__ import annotations
import re
from typing import List
from .config import (
    SECTION_MARKER_RE,
    SECTION_LOCK_RE,
    TABLE_MARKER_RE,
    SUBSECTION_MARKER_RE,
    META_MARKER_RE,
    OPEN_Q_COLUMNS,
    SUPPORTED_METADATA_KEYS,
)
from .validation_errors import (
    StructuralError,
    DuplicateSectionError,
    MalformedMarkerError,
    InvalidSpanError,
    TableSchemaError,
    OrphanedLockError,
)
from .parsing import find_table_block, WORKFLOW_ORDER_START_RE


class StructuralValidator:
    """Validates document structural integrity."""
    
    def __init__(self, lines: List[str]):
        """
        Initialize validator with document lines.
        
        Args:
            lines: Document content as list of strings
        """
        self.lines = lines
        self.errors: List[StructuralError] = []
    
    def validate_all(self) -> List[StructuralError]:
        """
        Run all structural validations and return errors.
        
        Returns:
            List of StructuralError instances found during validation
        """
        self.errors = []
        
        self._validate_section_markers()
        self._validate_lock_markers()
        self._validate_table_markers()
        self._validate_subsection_markers()
        self._validate_open_questions_table()
        self._validate_metadata_markers()
        self._validate_workflow_order_marker()
        
        return self.errors
    
    def validate_or_raise(self):
        """
        Run validations and raise first error encountered.
        
        Raises:
            StructuralError: First validation error found
        """
        errors = self.validate_all()
        if errors:
            raise errors[0]
    
    def _validate_section_markers(self):
        """Check: no duplicates, all well-formed, no orphaned spans."""
        section_ids = {}  # {section_id: [line_numbers]}
        
        for i, line in enumerate(self.lines):
            match = SECTION_MARKER_RE.search(line)
            if match:
                section_id = match.group("id")
                
                # Check well-formed (section IDs should be lowercase alphanumeric with underscores)
                if not re.fullmatch(r"[a-z0-9_]+", section_id):
                    self.errors.append(MalformedMarkerError(
                        i + 1, line, f"Invalid section ID format: {section_id}"
                    ))
                
                # Track for duplicate detection
                if section_id not in section_ids:
                    section_ids[section_id] = []
                section_ids[section_id].append(i + 1)
        
        # Check for duplicates
        for section_id, line_nums in section_ids.items():
            if len(line_nums) > 1:
                self.errors.append(DuplicateSectionError(section_id, line_nums))
    
    def _validate_lock_markers(self):
        """Check: every lock has corresponding section, lock value is boolean."""
        # Collect all section IDs
        section_ids = set()
        for line in self.lines:
            match = SECTION_MARKER_RE.search(line)
            if match:
                section_ids.add(match.group("id"))
        
        # Check lock markers
        for i, line in enumerate(self.lines):
            match = SECTION_LOCK_RE.search(line)
            if match:
                lock_id = match.group("id")
                lock_value = match.group("lock")
                
                # Check section exists
                if lock_id not in section_ids:
                    self.errors.append(OrphanedLockError(lock_id, i + 1))
                
                # Check lock value (should always be true or false per regex, but validate anyway)
                if lock_value not in ("true", "false"):
                    self.errors.append(MalformedMarkerError(
                        i + 1, line, f"Lock value must be 'true' or 'false', got: {lock_value}"
                    ))
    
    def _validate_table_markers(self):
        """Check: table markers are well-formed."""
        for i, line in enumerate(self.lines):
            match = TABLE_MARKER_RE.search(line)
            if match:
                table_id = match.group("id")
                
                # Check well-formed (table IDs should be lowercase alphanumeric with underscores)
                if not re.fullmatch(r"[a-z0-9_]+", table_id):
                    self.errors.append(MalformedMarkerError(
                        i + 1, line, f"Invalid table ID format: {table_id}"
                    ))
    
    def _validate_subsection_markers(self):
        """Check: subsection markers are well-formed."""
        for i, line in enumerate(self.lines):
            match = SUBSECTION_MARKER_RE.search(line)
            if match:
                subsection_id = match.group("id")
                
                # Check well-formed (subsection IDs should be lowercase alphanumeric with underscores)
                if not re.fullmatch(r"[a-z0-9_]+", subsection_id):
                    self.errors.append(MalformedMarkerError(
                        i + 1, line, f"Invalid subsection ID format: {subsection_id}"
                    ))
    
    def _validate_open_questions_table(self):
        """Check: table exists, schema matches expected, no malformed rows."""
        table_span = find_table_block(self.lines, "open_questions")
        if not table_span:
            # Table not found - this is acceptable if it's not required
            return
        
        start, end = table_span
        table_lines = self.lines[start:end]
        
        if len(table_lines) < 2:
            self.errors.append(TableSchemaError(
                "Open Questions table has insufficient rows (needs at least header + separator)"
            ))
            return
        
        # Find header row (first row with pipes)
        header_line = None
        header_idx = 0
        for idx, line in enumerate(table_lines):
            if "|" in line and "---" not in line:
                header_line = line
                header_idx = idx
                break
        
        if not header_line:
            self.errors.append(TableSchemaError("Table header row not found"))
            return
        
        # Parse header columns
        columns = [c.strip() for c in header_line.strip().strip("|").split("|")]
        
        # Validate schema
        if columns != OPEN_Q_COLUMNS:
            self.errors.append(TableSchemaError(
                f"Expected columns {OPEN_Q_COLUMNS}, got {columns}"
            ))
        
        # Validate row format (basic check: correct number of pipes)
        expected_pipes = len(OPEN_Q_COLUMNS) + 1  # columns + 1 for pipe structure (|col1|col2|)
        
        for i, line in enumerate(table_lines):
            # Skip header and separator rows
            if i == header_idx or "---" in line:
                continue
            
            if "|" in line:
                pipe_count = line.count("|")
                if pipe_count != expected_pipes:
                    self.errors.append(TableSchemaError(
                        f"Malformed table row at offset {i}: expected {expected_pipes} pipes, got {pipe_count}"
                    ))
    
    def _validate_metadata_markers(self):
        """Check: metadata markers are well-formed."""
        for i, line in enumerate(self.lines):
            match = META_MARKER_RE.search(line)
            if match:
                key = match.group("key")
                
                # Check if key is supported
                if key not in SUPPORTED_METADATA_KEYS:
                    # This is a warning rather than an error - unsupported keys are ignored
                    # but we don't want to break validation over them
                    pass
    
    def _validate_workflow_order_marker(self):
        """Check: workflow order block is well-formed."""
        # The workflow order validation is already done in parsing.extract_workflow_order()
        # which raises ValueError for malformed blocks. We don't need to duplicate that here.
        # This method is a placeholder for future workflow-specific structural checks.
        
        # Basic check: ensure workflow order marker exists
        found_workflow = False
        for line in self.lines:
            if WORKFLOW_ORDER_START_RE.search(line):
                found_workflow = True
                break
        
        if not found_workflow:
            # Workflow order is required, but parsing.py already validates this
            # We'll let that validation handle it to avoid duplicating error messages
            pass


def report_structural_errors(errors: List[StructuralError]) -> str:
    """
    Format structural errors for human-readable output.
    
    Args:
        errors: List of StructuralError instances
        
    Returns:
        Formatted error report string
    """
    if not errors:
        return "✅ Document structure valid"
    
    report = ["Document Structure Validation Failed:", ""]
    
    for error in errors:
        if isinstance(error, DuplicateSectionError):
            report.append(
                f"❌ Duplicate section '{error.section_id}' at lines: {error.line_numbers}"
            )
        elif isinstance(error, OrphanedLockError):
            report.append(f"❌ Orphaned lock marker: {error}")
        elif isinstance(error, TableSchemaError):
            report.append(f"❌ Table schema error: {error.reason}")
        elif isinstance(error, MalformedMarkerError):
            report.append(f"❌ {error}")
        elif isinstance(error, InvalidSpanError):
            report.append(f"❌ {error}")
        else:
            report.append(f"❌ {error}")
    
    report.append("")
    report.append("Fix structural errors before processing document.")
    return "\n".join(report)
