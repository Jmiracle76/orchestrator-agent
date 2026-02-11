"""Structural validation error types for document integrity checking.

This module defines exception types raised when document structure validation fails.
These errors help catch corruption early and provide clear, actionable error messages.
"""
from __future__ import annotations
from typing import List


class StructuralError(Exception):
    """Base class for document structure validation errors."""
    pass


class DuplicateSectionError(StructuralError):
    """Multiple sections with same ID found."""
    
    def __init__(self, section_id: str, line_numbers: List[int]):
        self.section_id = section_id
        self.line_numbers = line_numbers
        super().__init__(
            f"Duplicate section '{section_id}' at lines: {line_numbers}"
        )


class MalformedMarkerError(StructuralError):
    """Marker has invalid syntax."""
    
    def __init__(self, line_num: int, line_content: str, reason: str):
        self.line_num = line_num
        self.line_content = line_content
        self.reason = reason
        super().__init__(
            f"Malformed marker at line {line_num}: {reason}\n  {line_content}"
        )


class InvalidSpanError(StructuralError):
    """Section span is invalid or ambiguous."""
    
    def __init__(self, section_id: str, reason: str):
        self.section_id = section_id
        self.reason = reason
        super().__init__(f"Invalid span for section '{section_id}': {reason}")


class TableSchemaError(StructuralError):
    """Open Questions table schema is invalid."""
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Table schema error: {reason}")


class OrphanedLockError(StructuralError):
    """Lock marker exists without corresponding section marker."""
    
    def __init__(self, lock_id: str, line_num: int):
        self.lock_id = lock_id
        self.line_num = line_num
        super().__init__(
            f"Lock marker for '{lock_id}' at line {line_num} has no corresponding section"
        )
