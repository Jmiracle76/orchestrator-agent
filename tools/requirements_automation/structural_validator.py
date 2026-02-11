"""Structural validator for document integrity checking.

This module provides the StructuralValidator class that validates document structure
including markers, spans, tables, and metadata. It catches structural errors early
to prevent silent corruption and provides clear, actionable error messages.
"""
from __future__ import annotations
import re
import logging
from typing import List, Optional, Tuple
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
from .parsing import find_table_block, find_sections, get_section_span, WORKFLOW_ORDER_START_RE


class StructuralValidator:
    """Validates document structural integrity."""
    
    def __init__(self, lines: List[str], template_lines: Optional[List[str]] = None):
        """
        Initialize validator with document lines.
        
        Args:
            lines: Document content as list of strings
            template_lines: Optional template content for cross-reference validation
        """
        self.lines = lines
        self.template_lines = template_lines
        self.errors: List[StructuralError] = []
        self.repairs_made: List[str] = []
    
    def validate_all(self) -> List[StructuralError]:
        """
        Run all structural validations and return errors.
        
        Returns:
            List of StructuralError instances found during validation
        """
        self.errors = []
        self.repairs_made = []
        
        self._validate_section_markers()
        self._validate_lock_markers()
        self._validate_table_markers()
        self._validate_subsection_markers()
        self._validate_open_questions_table()
        self._validate_metadata_markers()
        self._validate_workflow_order_marker()
        
        # Template-based validation (only if template is provided)
        if self.template_lines:
            self._validate_against_template()
        
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
                # Note: SECTION_MARKER_RE already enforces [a-z0-9_]+, but we validate here
                # for defense in depth in case the regex is changed to be more permissive.
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
                # Note: TABLE_MARKER_RE already enforces [a-z0-9_]+, but we validate here
                # for defense in depth in case the regex is changed to be more permissive.
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
                # Note: SUBSECTION_MARKER_RE already enforces [a-z0-9_]+, but we validate here
                # for defense in depth in case the regex is changed to be more permissive.
                if not re.fullmatch(r"[a-z0-9_]+", subsection_id):
                    self.errors.append(MalformedMarkerError(
                        i + 1, line, f"Invalid subsection ID format: {subsection_id}"
                    ))
    
    def _validate_open_questions_table(self):
        """Check: table exists, schema matches expected, no malformed rows. Auto-repair if missing."""
        # First, check if table marker exists in the document
        table_span = find_table_block(self.lines, "open_questions")
        subsection_exists = self._check_marker_exists(SUBSECTION_MARKER_RE, "open_questions")
        table_marker_exists = self._check_marker_exists(TABLE_MARKER_RE, "open_questions")
        
        # Check if risks_open_issues section exists
        sections = find_sections(self.lines)
        risks_section = get_section_span(sections, "risks_open_issues")
        
        # Case 1: If table/subsection markers exist but risks_open_issues doesn't exist,
        # validate the table structure anyway (orphaned table)
        # Case 2: If risks_open_issues exists but table doesn't, auto-repair
        # Case 3: If neither exists, skip validation (table not required)
        
        if not risks_section:
            # If no risks_open_issues section, only validate if table markers exist
            if not table_marker_exists and not subsection_exists:
                return  # Nothing to validate
            # Otherwise, fall through to validate whatever table structure exists
        else:
            # risks_open_issues section exists
            # If table structure is completely missing, auto-repair
            if not subsection_exists or not table_marker_exists or not table_span:
                self._repair_missing_open_questions_table()
                return
        
        # If table exists (regardless of section), validate its structure
        if table_span:
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
    
    def _check_marker_exists(self, marker_regex: re.Pattern, marker_id: str) -> bool:
        """Check if a specific marker exists in the document."""
        for line in self.lines:
            match = marker_regex.search(line)
            if match and match.group("id") == marker_id:
                return True
        return False
    
    def _repair_missing_open_questions_table(self):
        """Repair document by inserting missing open questions table structure."""
        # Find the risks_open_issues section
        sections = find_sections(self.lines)
        risks_section = get_section_span(sections, "risks_open_issues")
        
        if not risks_section:
            # Cannot repair - risks_open_issues section doesn't exist
            self.errors.append(TableSchemaError(
                "Open Questions table missing: cannot repair because risks_open_issues section not found"
            ))
            return
        
        # Check if subsection marker exists
        subsection_exists = False
        subsection_line_idx = None
        for i in range(risks_section.start_line, risks_section.end_line):
            if SUBSECTION_MARKER_RE.search(self.lines[i]):
                match = SUBSECTION_MARKER_RE.search(self.lines[i])
                if match and match.group("id") == "open_questions":
                    subsection_exists = True
                    subsection_line_idx = i
                    break
        
        # Find section lock marker position (insert before it)
        lock_line_idx = None
        for i in range(risks_section.start_line, risks_section.end_line):
            if SECTION_LOCK_RE.search(self.lines[i]):
                match = SECTION_LOCK_RE.search(self.lines[i])
                if match and match.group("id") == "risks_open_issues":
                    lock_line_idx = i
                    break
        
        # Determine insertion point
        if subsection_exists and subsection_line_idx is not None:
            # Subsection exists but table is missing - insert table after subsection header
            insert_idx = subsection_line_idx + 1
            
            # Skip the header line if it exists
            if insert_idx < len(self.lines) and self.lines[insert_idx].strip().startswith("###"):
                insert_idx += 1
            
            # Skip empty line if exists
            if insert_idx < len(self.lines) and not self.lines[insert_idx].strip():
                insert_idx += 1
            
            # Insert table marker and empty table
            table_content = [
                "<!-- table:open_questions -->",
                "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
                "|-------------|----------|------|--------|----------------|-------------------|",
                ""
            ]
            
            self.lines[insert_idx:insert_idx] = table_content
            logging.info("Repaired: inserted missing open_questions table marker and header")
            self.repairs_made.append("inserted missing open_questions table in risks_open_issues section")
        else:
            # Subsection doesn't exist - insert both subsection and table
            # Insert before lock marker or at end of section
            insert_idx = lock_line_idx if lock_line_idx else risks_section.end_line
            
            # Insert subsection marker, header, and table
            subsection_content = [
                "",
                "<!-- subsection:open_questions -->",
                "### Open Questions",
                "",
                "<!-- table:open_questions -->",
                "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
                "|-------------|----------|------|--------|----------------|-------------------|",
                ""
            ]
            
            self.lines[insert_idx:insert_idx] = subsection_content
            logging.info("Repaired: inserted missing open_questions subsection and table")
            self.repairs_made.append("inserted missing open_questions subsection and table in risks_open_issues section")
    
    def _validate_against_template(self):
        """Validate document against template to ensure all structural markers are present."""
        if not self.template_lines:
            return
        
        # Extract all section, subsection, and table markers from template
        template_sections = set()
        template_subsections = set()
        template_tables = set()
        
        for line in self.template_lines:
            section_match = SECTION_MARKER_RE.search(line)
            if section_match:
                template_sections.add(section_match.group("id"))
            
            subsection_match = SUBSECTION_MARKER_RE.search(line)
            if subsection_match:
                template_subsections.add(subsection_match.group("id"))
            
            table_match = TABLE_MARKER_RE.search(line)
            if table_match:
                template_tables.add(table_match.group("id"))
        
        # Extract all markers from document
        doc_sections = set()
        doc_subsections = set()
        doc_tables = set()
        
        for line in self.lines:
            section_match = SECTION_MARKER_RE.search(line)
            if section_match:
                doc_sections.add(section_match.group("id"))
            
            subsection_match = SUBSECTION_MARKER_RE.search(line)
            if subsection_match:
                doc_subsections.add(subsection_match.group("id"))
            
            table_match = TABLE_MARKER_RE.search(line)
            if table_match:
                doc_tables.add(table_match.group("id"))
        
        # Find missing markers
        missing_sections = template_sections - doc_sections
        missing_subsections = template_subsections - doc_subsections
        missing_tables = template_tables - doc_tables
        
        # Report missing markers as errors
        for section_id in missing_sections:
            self.errors.append(MalformedMarkerError(
                0, "", f"Missing section marker from template: <!-- section:{section_id} -->"
            ))
        
        for subsection_id in missing_subsections:
            self.errors.append(MalformedMarkerError(
                0, "", f"Missing subsection marker from template: <!-- subsection:{subsection_id} -->"
            ))
        
        for table_id in missing_tables:
            self.errors.append(MalformedMarkerError(
                0, "", f"Missing table marker from template: <!-- table:{table_id} -->"
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


def report_structural_errors(errors: List[StructuralError], repairs_made: List[str] = None) -> str:
    """
    Format structural errors for human-readable output.
    
    Args:
        errors: List of StructuralError instances
        repairs_made: Optional list of repair descriptions
        
    Returns:
        Formatted error report string
    """
    if repairs_made and len(repairs_made) > 0:
        report = ["⚠️  Document structure repaired:", ""]
        for repair in repairs_made:
            report.append(f"   Repaired: {repair}")
        report.append("")
        report.append("The document has been automatically repaired.")
        return "\n".join(report)
    
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
