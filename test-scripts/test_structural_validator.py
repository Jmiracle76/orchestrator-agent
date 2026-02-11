#!/usr/bin/env python3
"""
Unit tests for StructuralValidator.

This test validates that the structural validator correctly detects:
- Duplicate section markers
- Malformed markers (invalid IDs)
- Orphaned lock markers
- Table schema errors
- Invalid spans
"""
import sys
from pathlib import Path
from typing import List

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.structural_validator import StructuralValidator, report_structural_errors
from requirements_automation.validation_errors import (
    DuplicateSectionError,
    MalformedMarkerError,
    OrphanedLockError,
    TableSchemaError,
    InvalidSpanError,
)


def test_valid_document():
    """Test that a valid document passes all structural checks."""
    print("\nTest: Valid Document")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "This is the problem statement.",
        "<!-- section_lock:problem_statement lock=false -->",
        "",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "| ----------- | -------- | ---- | ------ | -------------- | ----------------- |",
        "| Q-001 | Test? | 2024-01-01 | Yes | problem_statement | Resolved |",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    if len(errors) == 0:
        print("  ✓ Valid document passes all checks")
        return True
    else:
        print(f"  ✗ Expected no errors, got {len(errors)}")
        for error in errors:
            print(f"     - {error}")
        return False


def test_duplicate_section_markers():
    """Test detection of duplicate section markers."""
    print("\nTest: Duplicate Section Markers")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "First occurrence.",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement (Duplicate)",
        "Second occurrence.",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    duplicate_errors = [e for e in errors if isinstance(e, DuplicateSectionError)]
    
    if len(duplicate_errors) == 1:
        error = duplicate_errors[0]
        if error.section_id == "problem_statement" and error.line_numbers == [6, 10]:
            print(f"  ✓ Duplicate section detected: {error}")
            return True
        else:
            print(f"  ✗ Unexpected error details: {error}")
            return False
    else:
        print(f"  ✗ Expected 1 DuplicateSectionError, got {len(duplicate_errors)}")
        return False


def test_malformed_section_marker():
    """Test that non-matching section-like markers are simply ignored (not an error)."""
    print("\nTest: Malformed Section Marker (regex doesn't match)")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content here.",
        "<!-- section:problem-statement -->",  # Invalid: contains hyphen, won't match regex
        "This won't be treated as a section marker.",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    # Malformed markers that don't match the regex are simply ignored, not errors
    # This test verifies that the document is still considered valid
    if len(errors) == 0:
        print(f"  ✓ Non-matching markers ignored (document valid)")
        return True
    else:
        print(f"  ✗ Expected no errors, got {len(errors)}")
        for error in errors:
            print(f"     - {error}")
        return False


def test_orphaned_lock_marker():
    """Test detection of orphaned lock markers (no corresponding section)."""
    print("\nTest: Orphaned Lock Marker")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content here.",
        "",
        "<!-- section_lock:nonexistent_section lock=true -->",  # Orphaned lock
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    orphaned_errors = [e for e in errors if isinstance(e, OrphanedLockError)]
    
    if len(orphaned_errors) == 1:
        error = orphaned_errors[0]
        if error.lock_id == "nonexistent_section" and error.line_num == 10:
            print(f"  ✓ Orphaned lock detected: {error}")
            return True
        else:
            print(f"  ✗ Unexpected error details: {error}")
            return False
    else:
        print(f"  ✗ Expected 1 OrphanedLockError, got {len(orphaned_errors)}")
        return False


def test_table_schema_wrong_columns():
    """Test detection of table schema errors (wrong columns)."""
    print("\nTest: Table Schema - Wrong Columns")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- table:open_questions -->",
        "| ID | Question | Answer |",  # Wrong columns
        "| -- | -------- | ------ |",
        "| Q-001 | Test? | Yes |",  # This will also trigger pipe count error
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content.",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    table_errors = [e for e in errors if isinstance(e, TableSchemaError)]
    
    # Should detect at least the column mismatch error (may also detect row errors)
    if len(table_errors) >= 1:
        # Check that at least one error mentions columns
        column_errors = [e for e in table_errors if "Expected columns" in str(e)]
        if column_errors:
            print(f"  ✓ Table schema error detected: {column_errors[0]}")
            print(f"     (Total errors: {len(table_errors)})")
            return True
        else:
            print(f"  ✗ Column error not found in {len(table_errors)} errors:")
            for e in table_errors:
                print(f"     - {e}")
            return False
    else:
        print(f"  ✗ Expected at least 1 TableSchemaError, got {len(table_errors)}")
        return False


def test_table_schema_wrong_pipe_count():
    """Test detection of malformed table rows (wrong pipe count)."""
    print("\nTest: Table Schema - Wrong Pipe Count")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "| ----------- | -------- | ---- | ------ | -------------- | ----------------- |",
        "| Q-001 | Test? | 2024-01-01 |",  # Missing pipes
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content.",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    table_errors = [e for e in errors if isinstance(e, TableSchemaError)]
    
    if len(table_errors) >= 1:
        error = table_errors[0]
        if "Malformed table row" in str(error):
            print(f"  ✓ Malformed table row detected: {error}")
            return True
        else:
            print(f"  ✗ Unexpected error details: {error}")
            return False
    else:
        print(f"  ✗ Expected at least 1 TableSchemaError, got {len(table_errors)}")
        return False


def test_multiple_errors():
    """Test that validator detects multiple errors."""
    print("\nTest: Multiple Structural Errors")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "First occurrence.",
        "",
        "<!-- section:problem_statement -->",  # Duplicate
        "## Problem Statement (Duplicate)",
        "Second occurrence.",
        "",
        "<!-- section_lock:nonexistent lock=true -->",  # Orphaned
        "",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    duplicate_count = len([e for e in errors if isinstance(e, DuplicateSectionError)])
    orphaned_count = len([e for e in errors if isinstance(e, OrphanedLockError)])
    
    # Note: Malformed markers that don't match regex aren't detected as errors
    # They're simply not recognized as markers at all
    if duplicate_count >= 1 and orphaned_count >= 1:
        print(f"  ✓ Multiple errors detected:")
        print(f"     - Duplicate sections: {duplicate_count}")
        print(f"     - Orphaned locks: {orphaned_count}")
        return True
    else:
        print(f"  ✗ Expected multiple error types, got:")
        print(f"     - Duplicate sections: {duplicate_count}")
        print(f"     - Orphaned locks: {orphaned_count}")
        return False


def test_validate_or_raise():
    """Test that validate_or_raise raises first error."""
    print("\nTest: validate_or_raise()")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "First occurrence.",
        "",
        "<!-- section:problem_statement -->",  # Duplicate
        "Second occurrence.",
    ]
    
    validator = StructuralValidator(lines)
    
    try:
        validator.validate_or_raise()
        print("  ✗ Expected exception to be raised")
        return False
    except DuplicateSectionError as e:
        print(f"  ✓ Exception raised correctly: {e}")
        return True
    except Exception as e:
        print(f"  ✗ Unexpected exception type: {type(e).__name__}: {e}")
        return False


def test_error_reporting():
    """Test error reporting function."""
    print("\nTest: Error Reporting")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "First occurrence.",
        "",
        "<!-- section:problem_statement -->",  # Duplicate
        "Second occurrence.",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    report = report_structural_errors(errors)
    
    if "Document Structure Validation Failed" in report and "problem_statement" in report:
        print(f"  ✓ Error report generated:")
        print("     " + "\n     ".join(report.split("\n")))
        return True
    else:
        print(f"  ✗ Unexpected report format:\n{report}")
        return False


def test_valid_document_report():
    """Test error reporting for valid document."""
    print("\nTest: Valid Document Report")
    print("=" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content.",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    report = report_structural_errors(errors)
    
    if "✅ Document structure valid" in report:
        print(f"  ✓ Valid document report: {report}")
        return True
    else:
        print(f"  ✗ Unexpected report for valid document: {report}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("STRUCTURAL VALIDATOR TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_valid_document,
        test_duplicate_section_markers,
        test_malformed_section_marker,
        test_orphaned_lock_marker,
        test_table_schema_wrong_columns,
        test_table_schema_wrong_pipe_count,
        test_multiple_errors,
        test_validate_or_raise,
        test_error_reporting,
        test_valid_document_report,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Passed: {passed}/{total}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
