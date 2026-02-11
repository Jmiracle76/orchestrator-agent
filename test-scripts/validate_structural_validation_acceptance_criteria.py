#!/usr/bin/env python3
"""
Acceptance criteria validation for structural validation.

This test validates that all acceptance criteria from the issue are met.
"""
import sys
import tempfile
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.cli import main
from requirements_automation.structural_validator import StructuralValidator
from requirements_automation.editing import replace_block_body_preserving_markers
from requirements_automation.parsing import apply_patch, find_sections, get_section_span
from requirements_automation.validation_errors import (
    DuplicateSectionError,
    OrphanedLockError,
    TableSchemaError,
    InvalidSpanError,
    StructuralError,
)


def test_ac1_validator_validates_all_elements():
    """✅ StructuralValidator class validates all document structure elements"""
    print("\nAC1: StructuralValidator validates all document structure elements")
    print("-" * 70)
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content.",
        "<!-- section_lock:problem_statement lock=false -->",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "| ----------- | -------- | ---- | ------ | -------------- | ----------------- |",
        "<!-- subsection:test -->",
        "### Test Subsection",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    # Validator runs without crashing and returns empty list for valid doc
    if len(errors) == 0:
        print("  ✓ Validator checks all element types without errors")
        return True
    else:
        print(f"  ✗ Unexpected errors: {errors}")
        return False


def test_ac2_duplicate_sections_detected():
    """✅ Duplicate section markers detected and reported with line numbers"""
    print("\nAC2: Duplicate section markers detected with line numbers")
    print("-" * 70)
    
    lines = [
        "<!-- section:test -->",
        "Content 1",
        "<!-- section:test -->",
        "Content 2",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    duplicate_errors = [e for e in errors if isinstance(e, DuplicateSectionError)]
    
    if len(duplicate_errors) == 1:
        error = duplicate_errors[0]
        if error.section_id == "test" and error.line_numbers == [1, 3]:
            print(f"  ✓ Duplicate detected: {error}")
            return True
    
    print(f"  ✗ Expected 1 DuplicateSectionError, got {len(duplicate_errors)}")
    return False


def test_ac3_orphaned_locks_detected():
    """✅ Orphaned lock markers (no corresponding section) detected"""
    print("\nAC3: Orphaned lock markers detected")
    print("-" * 70)
    
    lines = [
        "<!-- section:valid -->",
        "Content",
        "<!-- section_lock:orphaned lock=true -->",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    orphaned_errors = [e for e in errors if isinstance(e, OrphanedLockError)]
    
    if len(orphaned_errors) == 1:
        error = orphaned_errors[0]
        if error.lock_id == "orphaned":
            print(f"  ✓ Orphaned lock detected: {error}")
            return True
    
    print(f"  ✗ Expected 1 OrphanedLockError, got {len(orphaned_errors)}")
    return False


def test_ac4_table_schema_validated():
    """✅ Open Questions table schema validated (columns, row format)"""
    print("\nAC4: Table schema validated")
    print("-" * 70)
    
    lines = [
        "<!-- table:open_questions -->",
        "| Wrong | Columns |",
        "| ----- | ------- |",
        "| Data | Here |",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    table_errors = [e for e in errors if isinstance(e, TableSchemaError)]
    
    if len(table_errors) >= 1:
        print(f"  ✓ Table schema error detected: {table_errors[0]}")
        return True
    
    print(f"  ✗ Expected TableSchemaError, got none")
    return False


def test_ac5_patches_rejected_if_corrupt():
    """✅ Patches rejected if they would corrupt structure (markers, invalid spans)"""
    print("\nAC5: Patches rejected if they would corrupt structure")
    print("-" * 70)
    
    lines = [
        "<!-- workflow:order",
        "test",
        "-->",
        "<!-- section:test -->",
        "Content",
    ]
    
    # Try to apply patch with forbidden markers
    try:
        apply_patch("test", "<!-- section:injected -->", lines)
        print("  ✗ Patch with markers was accepted")
        return False
    except (ValueError, StructuralError) as e:
        print(f"  ✓ Patch rejected: {e}")
        return True


def test_ac6_invalid_spans_detected():
    """✅ Invalid or ambiguous spans detected before edit operations"""
    print("\nAC6: Invalid spans detected before edit operations")
    print("-" * 70)
    
    lines = [
        "<!-- workflow:order",
        "test",
        "-->",
        "<!-- section:test -->",
        "Content",
    ]
    
    # Try to edit with invalid span
    try:
        replace_block_body_preserving_markers(
            lines, 3, 3, section_id="test", new_body="New"
        )
        print("  ✗ Invalid span was accepted")
        return False
    except InvalidSpanError as e:
        print(f"  ✓ Invalid span rejected: {e}")
        return True


def test_ac7_no_silent_corruption():
    """✅ No silent corruption allowed (all structural changes validated)"""
    print("\nAC7: No silent corruption - all changes validated")
    print("-" * 70)
    
    lines = [
        "<!-- workflow:order",
        "test",
        "-->",
        "<!-- section:test -->",
        "Content",
    ]
    
    spans = find_sections(lines)
    span = get_section_span(spans, "test")
    
    # Valid edit should succeed
    try:
        new_lines = replace_block_body_preserving_markers(
            lines, span.start_line, span.end_line,
            section_id="test", new_body="New content"
        )
        print("  ✓ Valid edit accepted after validation")
        return True
    except Exception as e:
        print(f"  ✗ Valid edit rejected: {e}")
        return False


def test_ac8_startup_validation_fails_fast():
    """✅ Startup validation fails fast if document corrupted"""
    print("\nAC8: Startup validation fails fast on corrupted document")
    print("-" * 70)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
test
-->
<!-- section:test -->
First
<!-- section:test -->
Duplicate
""")
        temp_doc = Path(f.name)
    
    try:
        result = main([
            '--template', str(repo_root / 'docs/templates/requirements-template.md'),
            '--doc', str(temp_doc),
            '--repo-root', str(repo_root),
            '--no-commit'
        ])
        
        if result == 2:
            print("  ✓ Startup validation failed with exit code 2")
            return True
        else:
            print(f"  ✗ Expected exit code 2, got {result}")
            return False
    finally:
        temp_doc.unlink()


def test_ac9_validate_structure_flag():
    """✅ --validate-structure CLI flag performs standalone validation"""
    print("\nAC9: --validate-structure CLI flag works")
    print("-" * 70)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
test
-->
<!-- section:test -->
Valid content.
""")
        temp_doc = Path(f.name)
    
    try:
        result = main([
            '--template', str(repo_root / 'docs/templates/requirements-template.md'),
            '--doc', str(temp_doc),
            '--repo-root', str(repo_root),
            '--validate-structure'
        ])
        
        if result == 0:
            print("  ✓ --validate-structure flag works (exit code 0)")
            return True
        else:
            print(f"  ✗ Expected exit code 0, got {result}")
            return False
    finally:
        temp_doc.unlink()


def test_ac10_clear_error_messages():
    """✅ Clear error messages with line numbers and actionable guidance"""
    print("\nAC10: Clear error messages with line numbers")
    print("-" * 70)
    
    lines = [
        "<!-- section:test -->",
        "Content 1",
        "<!-- section:test -->",
        "Content 2",
    ]
    
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    
    if errors:
        error_msg = str(errors[0])
        has_section_id = "test" in error_msg
        has_line_nums = "[1, 3]" in error_msg
        
        if has_section_id and has_line_nums:
            print(f"  ✓ Error message includes section ID and line numbers:")
            print(f"     {error_msg}")
            return True
    
    print("  ✗ Error message format incorrect")
    return False


def main_test():
    """Run all acceptance criteria tests."""
    print("\n" + "=" * 70)
    print("ACCEPTANCE CRITERIA VALIDATION")
    print("=" * 70)
    
    tests = [
        test_ac1_validator_validates_all_elements,
        test_ac2_duplicate_sections_detected,
        test_ac3_orphaned_locks_detected,
        test_ac4_table_schema_validated,
        test_ac5_patches_rejected_if_corrupt,
        test_ac6_invalid_spans_detected,
        test_ac7_no_silent_corruption,
        test_ac8_startup_validation_fails_fast,
        test_ac9_validate_structure_flag,
        test_ac10_clear_error_messages,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__doc__.strip(), result))
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__doc__.strip(), False))
    
    print("\n" + "=" * 70)
    print("ACCEPTANCE CRITERIA RESULTS")
    print("=" * 70)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print()
    print(f"Passed: {passed}/{total}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main_test())
