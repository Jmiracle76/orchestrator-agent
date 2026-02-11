#!/usr/bin/env python3
"""
Unit tests for open questions table validation and auto-repair.

This test validates that the structural validator correctly:
- Detects missing open questions subsection marker
- Detects missing open questions table marker
- Detects missing table structure
- Auto-repairs missing structures
- Validates against template
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.structural_validator import (
    StructuralValidator,
    report_structural_errors,
)


def test_missing_subsection_and_table():
    """Test detection and repair when both subsection and table are missing."""
    print("\nTest: Missing Subsection and Table")
    print("=" * 70)

    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "risks_open_issues",
        "-->",
        "",
        "<!-- section:risks_open_issues -->",
        "## Risks and Open Issues",
        "",
        "<!-- subsection:identified_risks -->",
        "### Identified Risks",
        "Some risks here.",
        "",
        "<!-- section_lock:risks_open_issues lock=false -->",
        "---",
    ]

    validator = StructuralValidator(lines)
    errors = validator.validate_all()

    # Should have no errors but repairs should be made
    if len(errors) == 0 and len(validator.repairs_made) > 0:
        print(f"  ✓ Auto-repair triggered: {validator.repairs_made}")

        # Verify the repaired content
        repaired_text = "\n".join(validator.lines)
        if "<!-- subsection:open_questions -->" in repaired_text:
            print("  ✓ Subsection marker inserted")
        else:
            print("  ✗ Subsection marker not found")
            return False

        if "<!-- table:open_questions -->" in repaired_text:
            print("  ✓ Table marker inserted")
        else:
            print("  ✗ Table marker not found")
            return False

        if (
            "| Question ID | Question | Date | Answer | Section Target | Resolution Status |"
            in repaired_text
        ):
            print("  ✓ Table header inserted")
        else:
            print("  ✗ Table header not found")
            return False

        return True
    else:
        print(
            f"  ✗ Expected repairs but got: errors={len(errors)}, repairs={len(validator.repairs_made)}"
        )
        for error in errors:
            print(f"     Error: {error}")
        return False


def test_missing_table_only():
    """Test detection and repair when subsection exists but table is missing."""
    print("\nTest: Missing Table Only")
    print("=" * 70)

    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "risks_open_issues",
        "-->",
        "",
        "<!-- section:risks_open_issues -->",
        "## Risks and Open Issues",
        "",
        "<!-- subsection:open_questions -->",
        "### Open Questions",
        "",
        "<!-- section_lock:risks_open_issues lock=false -->",
        "---",
    ]

    validator = StructuralValidator(lines)
    errors = validator.validate_all()

    # Should have no errors but repairs should be made
    if len(errors) == 0 and len(validator.repairs_made) > 0:
        print(f"  ✓ Auto-repair triggered: {validator.repairs_made}")

        # Verify the repaired content
        repaired_text = "\n".join(validator.lines)
        if "<!-- table:open_questions -->" in repaired_text:
            print("  ✓ Table marker inserted")
        else:
            print("  ✗ Table marker not found")
            return False

        if (
            "| Question ID | Question | Date | Answer | Section Target | Resolution Status |"
            in repaired_text
        ):
            print("  ✓ Table header inserted")
        else:
            print("  ✗ Table header not found")
            return False

        return True
    else:
        print(
            f"  ✗ Expected repairs but got: errors={len(errors)}, repairs={len(validator.repairs_made)}"
        )
        return False


def test_complete_table_no_repair():
    """Test that complete table structure passes without repair."""
    print("\nTest: Complete Table Structure - No Repair Needed")
    print("=" * 70)

    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "risks_open_issues",
        "-->",
        "",
        "<!-- section:risks_open_issues -->",
        "## Risks and Open Issues",
        "",
        "<!-- subsection:open_questions -->",
        "### Open Questions",
        "",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "|-------------|----------|------|--------|----------------|-------------------|",
        "| Q-001 | Test? | 2024-01-01 | Yes | problem_statement | Resolved |",
        "",
        "<!-- section_lock:risks_open_issues lock=false -->",
        "---",
    ]

    validator = StructuralValidator(lines)
    errors = validator.validate_all()

    if len(errors) == 0 and len(validator.repairs_made) == 0:
        print("  ✓ Complete table structure validated without repairs")
        return True
    else:
        print(
            f"  ✗ Expected no errors/repairs but got: errors={len(errors)}, repairs={len(validator.repairs_made)}"
        )
        for error in errors:
            print(f"     Error: {error}")
        return False


def test_no_risks_section_no_repair():
    """Test that missing table is OK if risks_open_issues section doesn't exist."""
    print("\nTest: No Risks Section - No Repair Needed")
    print("=" * 70)

    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content here.",
    ]

    validator = StructuralValidator(lines)
    errors = validator.validate_all()

    if len(errors) == 0 and len(validator.repairs_made) == 0:
        print("  ✓ No repairs needed when risks_open_issues section missing")
        return True
    else:
        print(
            f"  ✗ Expected no errors/repairs but got: errors={len(errors)}, repairs={len(validator.repairs_made)}"
        )
        return False


def test_template_validation_missing_markers():
    """Test template-based validation detects missing markers."""
    print("\nTest: Template Validation - Missing Markers")
    print("=" * 70)

    template_lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "risks_open_issues",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "",
        "<!-- section:risks_open_issues -->",
        "## Risks and Open Issues",
        "",
        "<!-- subsection:open_questions -->",
        "### Open Questions",
        "",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "|-------------|----------|------|--------|----------------|-------------------|",
    ]

    # Document is missing the risks_open_issues section and its subsections/tables
    doc_lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content here.",
    ]

    validator = StructuralValidator(doc_lines, template_lines)
    errors = validator.validate_all()

    # Should detect missing section, subsection, and table markers
    error_strs = [str(e) for e in errors]

    has_section_error = any("section:risks_open_issues" in e for e in error_strs)
    has_subsection_error = any("subsection:open_questions" in e for e in error_strs)
    has_table_error = any("table:open_questions" in e for e in error_strs)

    if has_section_error and has_subsection_error and has_table_error:
        print("  ✓ Template validation detected missing markers:")
        print(f"     - Section marker: {has_section_error}")
        print(f"     - Subsection marker: {has_subsection_error}")
        print(f"     - Table marker: {has_table_error}")
        return True
    else:
        print(f"  ✗ Expected all markers detected but got:")
        print(f"     - Section marker: {has_section_error}")
        print(f"     - Subsection marker: {has_subsection_error}")
        print(f"     - Table marker: {has_table_error}")
        print("  Errors found:")
        for e in errors:
            print(f"     - {e}")
        return False


def test_template_validation_complete_document():
    """Test template-based validation passes for complete document."""
    print("\nTest: Template Validation - Complete Document")
    print("=" * 70)

    template_lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
    ]

    doc_lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content here.",
    ]

    validator = StructuralValidator(doc_lines, template_lines)
    errors = validator.validate_all()

    if len(errors) == 0:
        print("  ✓ Template validation passed for complete document")
        return True
    else:
        print(f"  ✗ Expected no errors but got {len(errors)}:")
        for e in errors:
            print(f"     - {e}")
        return False


def test_repair_output_format():
    """Test that repair output is formatted correctly."""
    print("\nTest: Repair Output Format")
    print("=" * 70)

    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "risks_open_issues",
        "-->",
        "",
        "<!-- section:risks_open_issues -->",
        "## Risks and Open Issues",
        "",
        "<!-- section_lock:risks_open_issues lock=false -->",
        "---",
    ]

    validator = StructuralValidator(lines)
    errors = validator.validate_all()

    report = report_structural_errors(errors, validator.repairs_made)

    if "⚠️" in report and "Document structure repaired" in report:
        print("  ✓ Repair output formatted correctly:")
        print("     " + "\n     ".join(report.split("\n")))
        return True
    else:
        print(f"  ✗ Unexpected repair output format:\n{report}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("OPEN QUESTIONS VALIDATION AND REPAIR TEST SUITE")
    print("=" * 70)

    tests = [
        test_missing_subsection_and_table,
        test_missing_table_only,
        test_complete_table_no_repair,
        test_no_risks_section_no_repair,
        test_template_validation_missing_markers,
        test_template_validation_complete_document,
        test_repair_output_format,
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
