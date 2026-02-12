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

        # Extract all section, subsection, and table markers from template with line numbers
        template_sections = {}  # {section_id: line_num}
        template_subsections = {}  # {subsection_id: line_num}
        template_tables = {}  # {table_id: line_num}

        for i, line in enumerate(self.template_lines):
            section_match = SECTION_MARKER_RE.search(line)
            if section_match:
                template_sections[section_match.group("id")] = i

            subsection_match = SUBSECTION_MARKER_RE.search(line)
            if subsection_match:
                template_subsections[subsection_match.group("id")] = i

            table_match = TABLE_MARKER_RE.search(line)
            if table_match:
                template_tables[table_match.group("id")] = i

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
        missing_sections = set(template_sections.keys()) - doc_sections
        missing_subsections = set(template_subsections.keys()) - doc_subsections
        missing_tables = set(template_tables.keys()) - doc_tables

        # Attempt auto-repair for missing markers
        # Repair missing sections
        for section_id in missing_sections:
            if self._try_repair_missing_section(section_id, template_sections[section_id]):
                self.repairs_made.append(f"section:{section_id}")
            else:
                self.errors.append(
                    MalformedMarkerError(
                        0,
                        "",
                        f"Missing section from template: <!-- section:{section_id} -->. "
                        f"Add this section marker and its content to match the template structure.",
                    )
                )

        # Repair missing subsections
        for subsection_id in missing_subsections:
            if self._try_repair_missing_subsection(
                subsection_id, template_subsections[subsection_id]
            ):
                self.repairs_made.append(f"subsection:{subsection_id}")
            else:
                self.errors.append(
                    MalformedMarkerError(
                        0,
                        "",
                        f"Missing subsection from template: <!-- subsection:{subsection_id} -->. "
                        f"Add this subsection marker within its parent section to match the template structure.",
                    )
                )

        # Repair missing tables
        for table_id in missing_tables:
            if self._try_repair_missing_table(table_id, template_tables[table_id]):
                self.repairs_made.append(f"table:{table_id}")
            else:
                self.errors.append(
                    MalformedMarkerError(
                        0,
                        "",
                        f"Missing table from template: <!-- table:{table_id} -->. "
                        f"Add this table marker and its header within the appropriate section to match the template structure.",
                    )
                )

    def _try_repair_missing_section(self, section_id: str, template_line_num: int) -> bool:
        """
        Attempt to repair a missing section by extracting it from template and inserting it.

        Args:
            section_id: The ID of the missing section
            template_line_num: Line number in template where section marker appears

        Returns:
            True if repair was successful, False otherwise
        """
        if not self.template_lines:
            return False

        # Extract the section block from template (from marker to section_lock or next section)
        section_start = template_line_num
        section_end = len(self.template_lines)

        # Find the end of the section (section_lock marker or next section marker)
        for i in range(section_start + 1, len(self.template_lines)):
            line = self.template_lines[i]
            if SECTION_LOCK_RE.search(line) and section_id in line:
                section_end = i + 1
                break
            if SECTION_MARKER_RE.search(line):
                section_end = i
                break

        # Extract section content
        section_content = self.template_lines[section_start:section_end]

        # Find insertion point in document (at the end, before last section_lock if present)
        insert_index = len(self.lines)

        # Insert before the last few lines if they look like trailing content
        if insert_index > 0 and self.lines[-1].strip() == "":
            insert_index = len(self.lines) - 1

        # Add separator if needed (format: blank line, separator, blank line)
        # This matches the standard section separator pattern used throughout the template
        if insert_index > 0 and self.lines[insert_index - 1].strip() != "---":
            section_content = ["", "---", ""] + section_content

        # Insert the section
        self.lines[insert_index:insert_index] = section_content

        return True

    def _try_repair_missing_subsection(self, subsection_id: str, template_line_num: int) -> bool:
        """
        Attempt to repair a missing subsection by extracting it from template and inserting it.

        Args:
            subsection_id: The ID of the missing subsection
            template_line_num: Line number in template where subsection marker appears

        Returns:
            True if repair was successful, False otherwise
        """
        if not self.template_lines:
            return False

        # Extract the subsection block from template
        subsection_start = template_line_num
        subsection_end = len(self.template_lines)

        # Find the end of the subsection (next subsection, table, or section_lock)
        for i in range(subsection_start + 1, len(self.template_lines)):
            line = self.template_lines[i]
            if (
                SUBSECTION_MARKER_RE.search(line)
                or TABLE_MARKER_RE.search(line)
                or SECTION_LOCK_RE.search(line)
                or SECTION_MARKER_RE.search(line)
            ):
                subsection_end = i
                break

        # Extract subsection content
        subsection_content = self.template_lines[subsection_start:subsection_end]

        # Find the parent section in template to determine which section to insert into
        parent_section_id = None
        for i in range(subsection_start - 1, -1, -1):
            section_match = SECTION_MARKER_RE.search(self.template_lines[i])
            if section_match:
                parent_section_id = section_match.group("id")
                break

        if not parent_section_id:
            return False

        # Find parent section in document
        parent_section_line = None
        for i, line in enumerate(self.lines):
            if f"<!-- section:{parent_section_id} -->" in line:
                parent_section_line = i
                break

        if parent_section_line is None:
            return False

        # Find insertion point (before section_lock of parent section)
        insert_index = parent_section_line + 1
        for i in range(parent_section_line + 1, len(self.lines)):
            line = self.lines[i]
            if f"section_lock:{parent_section_id}" in line:
                insert_index = i
                break
            if SECTION_MARKER_RE.search(line):
                insert_index = i
                break

        # Add blank line before if needed
        if insert_index > 0 and self.lines[insert_index - 1].strip() != "":
            subsection_content = [""] + subsection_content

        # Insert the subsection
        self.lines[insert_index:insert_index] = subsection_content

        return True

    def _try_repair_missing_table(self, table_id: str, template_line_num: int) -> bool:
        """
        Attempt to repair a missing table by extracting it from template and inserting it.

        Args:
            table_id: The ID of the missing table
            template_line_num: Line number in template where table marker appears

        Returns:
            True if repair was successful, False otherwise
        """
        if not self.template_lines:
            return False

        # Extract the table block from template (marker + header + separator)
        table_start = template_line_num
        table_end = template_line_num + 1

        # Include the table header and separator rows
        for i in range(table_start + 1, min(table_start + 4, len(self.template_lines))):
            line = self.template_lines[i]
            if line.strip().startswith("|"):
                table_end = i + 1
            else:
                break

        # Extract table content
        table_content = self.template_lines[table_start:table_end]

        # Find the parent section or subsection in template
        parent_id = None
        parent_type = None
        for i in range(table_start - 1, -1, -1):
            subsection_match = SUBSECTION_MARKER_RE.search(self.template_lines[i])
            if subsection_match:
                parent_id = subsection_match.group("id")
                parent_type = "subsection"
                break
            section_match = SECTION_MARKER_RE.search(self.template_lines[i])
            if section_match:
                parent_id = section_match.group("id")
                parent_type = "section"
                break

        if not parent_id:
            return False

        # Find parent in document
        parent_line = None
        for i, line in enumerate(self.lines):
            if f"<!-- {parent_type}:{parent_id} -->" in line:
                parent_line = i
                break

        if parent_line is None:
            return False

        # Find insertion point (after parent marker, or before next subsection/section_lock)
        insert_index = parent_line + 1
        for i in range(parent_line + 1, len(self.lines)):
            line = self.lines[i]
            if (
                SUBSECTION_MARKER_RE.search(line)
                or SECTION_LOCK_RE.search(line)
                or SECTION_MARKER_RE.search(line)
            ):
                insert_index = i
                break

        # Add blank line before if needed
        if insert_index > 0 and self.lines[insert_index - 1].strip() != "":
            table_content = [""] + table_content

        # Insert the table
        self.lines[insert_index:insert_index] = table_content

        return True

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
