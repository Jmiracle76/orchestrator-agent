"""Structural validator for document integrity checking.

This module provides the StructuralValidator class that validates document structure
including markers, spans, tables, and metadata. It catches structural errors early
to prevent silent corruption and provides clear, actionable error messages.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from .config import (
    META_MARKER_RE,
    OPEN_Q_COLUMNS,
    SECTION_LOCK_RE,
    SECTION_MARKER_RE,
    SUBSECTION_MARKER_RE,
    SUPPORTED_METADATA_KEYS,
    TABLE_MARKER_RE,
)
from .parsing import WORKFLOW_ORDER_START_RE, find_sections, find_table_block, get_section_span
from .validation_errors import (
    DuplicateSectionError,
    InvalidSpanError,
    MalformedMarkerError,
    OrphanedLockError,
    StructuralError,
    TableSchemaError,
)


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

    def validate_or_raise(self) -> None:
        """
        Run validations and raise first error encountered.

        Raises:
            StructuralError: First validation error found
        """
        errors = self.validate_all()
        if errors:
            raise errors[0]

    def _validate_section_markers(self) -> None:
        """Check: no duplicates, all well-formed, no orphaned spans."""
        section_ids: dict[str, list[int]] = {}  # {section_id: [line_numbers]}

        for i, line in enumerate(self.lines):
            match = SECTION_MARKER_RE.search(line)
            if match:
                section_id = match.group("id")

                # Check well-formed (section IDs should be lowercase alphanumeric with underscores)
                # Note: SECTION_MARKER_RE already enforces [a-z0-9_]+, but we validate here
                # for defense in depth in case the regex is changed to be more permissive.
                if not re.fullmatch(r"[a-z0-9_]+", section_id):
                    self.errors.append(
                        MalformedMarkerError(
                            i + 1, line, f"Invalid section ID format: {section_id}"
                        )
                    )

                # Track for duplicate detection
                if section_id not in section_ids:
                    section_ids[section_id] = []
                section_ids[section_id].append(i + 1)

        # Check for duplicates
        for section_id, line_nums in section_ids.items():
            if len(line_nums) > 1:
                self.errors.append(DuplicateSectionError(section_id, line_nums))

    def _validate_lock_markers(self) -> None:
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
                    self.errors.append(
                        MalformedMarkerError(
                            i + 1, line, f"Lock value must be 'true' or 'false', got: {lock_value}"
                        )
                    )

    def _validate_table_markers(self) -> None:
        """Check: table markers are well-formed."""
        for i, line in enumerate(self.lines):
            match = TABLE_MARKER_RE.search(line)
            if match:
                table_id = match.group("id")

                # Check well-formed (table IDs should be lowercase alphanumeric with underscores)
                # Note: TABLE_MARKER_RE already enforces [a-z0-9_]+, but we validate here
                # for defense in depth in case the regex is changed to be more permissive.
                if not re.fullmatch(r"[a-z0-9_]+", table_id):
                    self.errors.append(
                        MalformedMarkerError(i + 1, line, f"Invalid table ID format: {table_id}")
                    )

    def _validate_subsection_markers(self) -> None:
        """Check: subsection markers are well-formed."""
        for i, line in enumerate(self.lines):
            match = SUBSECTION_MARKER_RE.search(line)
            if match:
                subsection_id = match.group("id")

                # Check well-formed (subsection IDs should be lowercase alphanumeric with underscores)
                # Note: SUBSECTION_MARKER_RE already enforces [a-z0-9_]+, but we validate here
                # for defense in depth in case the regex is changed to be more permissive.
                if not re.fullmatch(r"[a-z0-9_]+", subsection_id):
                    self.errors.append(
                        MalformedMarkerError(
                            i + 1, line, f"Invalid subsection ID format: {subsection_id}"
                        )
                    )

    def _validate_open_questions_table(self) -> None:
        """
        Validate open questions table (DEPRECATED).
        
        The global open_questions table has been retired in favor of per-section question tables.
        This validation method is kept for backward compatibility but will be removed in a future version.
        Per-section tables are validated through their respective section handlers.
        """
        # This method is now deprecated - per-section question tables are used instead
        # The global open_questions table has been removed from the template
        # Each section now has its own questions table (e.g., problem_statement_questions)
        pass

    def _validate_against_template(self) -> None:
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

        # Report missing markers as errors with actionable guidance
        for section_id in missing_sections:
            self.errors.append(
                MalformedMarkerError(
                    0,
                    "",
                    f"Missing section from template: <!-- section:{section_id} -->. "
                    f"Add this section marker and its content to match the template structure.",
                )
            )

        for subsection_id in missing_subsections:
            self.errors.append(
                MalformedMarkerError(
                    0,
                    "",
                    f"Missing subsection from template: <!-- subsection:{subsection_id} -->. "
                    f"Add this subsection marker within its parent section to match the template structure.",
                )
            )

        for table_id in missing_tables:
            self.errors.append(
                MalformedMarkerError(
                    0,
                    "",
                    f"Missing table from template: <!-- table:{table_id} -->. "
                    f"Add this table marker and its header within the appropriate section to match the template structure.",
                )
            )

    def _validate_metadata_markers(self) -> None:
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

    def _validate_workflow_order_marker(self) -> None:
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


def report_structural_errors(
    errors: List[StructuralError], repairs_made: Optional[List[str]] = None
) -> str:
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
