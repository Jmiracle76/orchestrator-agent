#!/usr/bin/env python3
"""
Test script for Review Gate Handler functionality.

This script validates the review gate implementation by testing:
1. Scope determination logic
2. Patch validation
3. Auto-apply configurations
4. Integration with WorkflowRunner
"""
import sys
import tempfile
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.models import HandlerConfig, ReviewIssue, ReviewPatch, ReviewResult
from requirements_automation.parsing import (
    contains_markers,
    extract_all_section_ids,
    section_exists,
)
from requirements_automation.review_gate_handler import ReviewGateHandler


def create_test_document() -> list:
    """Create a test document with workflow order and sections."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:doc_format version="1.0" -->',
        "<!-- workflow:order",
        "problem_statement",
        "assumptions",
        "constraints",
        "review_gate:coherence_check",
        "requirements",
        "-->",
        "",
        "# Test Requirements Document",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "This is a test problem statement.",
        "",
        "<!-- section:assumptions -->",
        "## Assumptions",
        "- Assumption 1",
        "- Assumption 2",
        "",
        "<!-- section:constraints -->",
        "## Constraints",
        "### Technical Constraints",
        "- Constraint 1",
        "",
        "<!-- section:requirements -->",
        "## Requirements",
        "<!-- PLACEHOLDER -->",
        "",
    ]


def test_determine_scope_all_prior():
    """Test _determine_scope with 'all_prior_sections' config."""
    print("Test 1: Determine scope with 'all_prior_sections'...")

    lines = create_test_document()

    # Create a mock LLM client (won't be used for this test)
    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Test scope determination
    scope = handler._determine_scope("review_gate:coherence_check", "all_prior_sections")

    expected = ["problem_statement", "assumptions", "constraints"]
    if scope == expected:
        print(f"  ✓ Scope correctly determined: {scope}")
        return True
    else:
        print(f"  ✗ Expected {expected}, got {scope}")
        return False


def test_determine_scope_entire_document():
    """Test _determine_scope with 'entire_document' config."""
    print("\nTest 2: Determine scope with 'entire_document'...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Test scope determination
    scope = handler._determine_scope("review_gate:coherence_check", "entire_document")

    expected = ["problem_statement", "assumptions", "constraints", "requirements"]
    if scope == expected:
        print(f"  ✓ Scope correctly determined: {scope}")
        return True
    else:
        print(f"  ✗ Expected {expected}, got {scope}")
        return False


def test_determine_scope_explicit():
    """Test _determine_scope with explicit section list."""
    print("\nTest 3: Determine scope with explicit section list...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Test scope determination
    scope = handler._determine_scope(
        "review_gate:coherence_check", "sections:assumptions,constraints"
    )

    expected = ["assumptions", "constraints"]
    if scope == expected:
        print(f"  ✓ Scope correctly determined: {scope}")
        return True
    else:
        print(f"  ✗ Expected {expected}, got {scope}")
        return False


def test_validate_patches_valid():
    """Test _validate_patches with valid patches."""
    print("\nTest 4: Validate patches with valid patches...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Create a test result with valid patches
    result = ReviewResult(
        gate_id="test_gate",
        passed=False,
        issues=[],
        patches=[
            ReviewPatch(
                section="assumptions",
                suggestion="Updated assumptions content",
                rationale="Need to clarify assumptions",
                validated=False,
            )
        ],
        scope_sections=["assumptions"],
        summary="Test review",
    )

    validated_result = handler._validate_patches(result)

    if all(p.validated for p in validated_result.patches):
        print(f"  ✓ Valid patch correctly validated")
        return True
    else:
        print(f"  ✗ Valid patch failed validation")
        return False


def test_validate_patches_with_markers():
    """Test _validate_patches with patches containing markers."""
    print("\nTest 5: Validate patches with structure markers...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Create a test result with invalid patches (contains markers)
    result = ReviewResult(
        gate_id="test_gate",
        passed=False,
        issues=[],
        patches=[
            ReviewPatch(
                section="assumptions",
                suggestion="<!-- section:test --> Invalid content",
                rationale="This should fail validation",
                validated=False,
            )
        ],
        scope_sections=["assumptions"],
        summary="Test review",
    )

    validated_result = handler._validate_patches(result)

    if not any(p.validated for p in validated_result.patches):
        print(f"  ✓ Patch with markers correctly rejected")
        return True
    else:
        print(f"  ✗ Patch with markers should have been rejected")
        return False


def test_validate_patches_unknown_section():
    """Test _validate_patches with unknown section."""
    print("\nTest 6: Validate patches with unknown section...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Create a test result with patch for unknown section
    result = ReviewResult(
        gate_id="test_gate",
        passed=False,
        issues=[],
        patches=[
            ReviewPatch(
                section="unknown_section",
                suggestion="Some content",
                rationale="This should fail validation",
                validated=False,
            )
        ],
        scope_sections=["assumptions"],
        summary="Test review",
    )

    validated_result = handler._validate_patches(result)

    if not any(p.validated for p in validated_result.patches):
        print(f"  ✓ Patch for unknown section correctly rejected")
        return True
    else:
        print(f"  ✗ Patch for unknown section should have been rejected")
        return False


def test_auto_apply_never():
    """Test auto_apply_patches='never' configuration."""
    print("\nTest 7: Test auto_apply_patches='never'...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    config = HandlerConfig(
        section_id="review_gate:test",
        mode="review_gate",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements_review",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
    )

    result = ReviewResult(
        gate_id="test_gate",
        passed=False,
        issues=[],
        patches=[
            ReviewPatch(
                section="assumptions",
                suggestion="Updated content",
                rationale="Test patch",
                validated=True,
            )
        ],
        scope_sections=["assumptions"],
        summary="Test review",
    )

    updated_lines, patches_applied = handler.apply_patches_if_configured(result, config)

    if not patches_applied:
        print(f"  ✓ Patches not applied with 'never' config")
        return True
    else:
        print(f"  ✗ Patches should not have been applied")
        return False


def test_auto_apply_if_validation_passes_success():
    """Test auto_apply_patches='if_validation_passes' with valid patches."""
    print("\nTest 8: Test auto_apply_patches='if_validation_passes' with valid patches...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    config = HandlerConfig(
        section_id="review_gate:test",
        mode="review_gate",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements_review",
        auto_apply_patches="if_validation_passes",
        scope="all_prior_sections",
        validation_rules=[],
    )

    result = ReviewResult(
        gate_id="test_gate",
        passed=False,
        issues=[],
        patches=[
            ReviewPatch(
                section="assumptions",
                suggestion="Updated content",
                rationale="Test patch",
                validated=True,  # All patches validated
            )
        ],
        scope_sections=["assumptions"],
        summary="Test review",
    )

    updated_lines, patches_applied = handler.apply_patches_if_configured(result, config)

    if patches_applied:
        print(f"  ✓ Patches applied with 'if_validation_passes' and valid patches")
        return True
    else:
        print(f"  ✗ Patches should have been applied")
        return False


def test_auto_apply_if_validation_passes_failure():
    """Test auto_apply_patches='if_validation_passes' with invalid patches."""
    print("\nTest 9: Test auto_apply_patches='if_validation_passes' with invalid patches...")

    lines = create_test_document()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    config = HandlerConfig(
        section_id="review_gate:test",
        mode="review_gate",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements_review",
        auto_apply_patches="if_validation_passes",
        scope="all_prior_sections",
        validation_rules=[],
    )

    result = ReviewResult(
        gate_id="test_gate",
        passed=False,
        issues=[],
        patches=[
            ReviewPatch(
                section="assumptions",
                suggestion="Updated content",
                rationale="Test patch",
                validated=False,  # Invalid patch
            )
        ],
        scope_sections=["assumptions"],
        summary="Test review",
    )

    updated_lines, patches_applied = handler.apply_patches_if_configured(result, config)

    if not patches_applied:
        print(f"  ✓ Patches not applied with 'if_validation_passes' and invalid patches")
        return True
    else:
        print(f"  ✗ Patches should not have been applied")
        return False


def test_extract_all_section_ids():
    """Test extract_all_section_ids helper."""
    print("\nTest 10: Test extract_all_section_ids helper...")

    lines = create_test_document()

    section_ids = extract_all_section_ids(lines)
    expected = ["problem_statement", "assumptions", "constraints", "requirements"]

    if section_ids == expected:
        print(f"  ✓ Section IDs correctly extracted: {section_ids}")
        return True
    else:
        print(f"  ✗ Expected {expected}, got {section_ids}")
        return False


def test_section_exists():
    """Test section_exists helper."""
    print("\nTest 11: Test section_exists helper...")

    lines = create_test_document()

    # Test existing section
    if not section_exists("assumptions", lines):
        print(f"  ✗ section_exists failed for existing section")
        return False

    # Test non-existing section
    if section_exists("nonexistent", lines):
        print(f"  ✗ section_exists returned True for non-existing section")
        return False

    print(f"  ✓ section_exists working correctly")
    return True


def test_contains_markers():
    """Test contains_markers helper."""
    print("\nTest 12: Test contains_markers helper...")

    # Test with markers
    if not contains_markers("<!-- section:test -->"):
        print(f"  ✗ contains_markers failed to detect section marker")
        return False

    # Test without markers
    if contains_markers("Normal text without markers"):
        print(f"  ✗ contains_markers detected markers in clean text")
        return False

    print(f"  ✓ contains_markers working correctly")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Review Gate Handler Test Suite")
    print("=" * 70)

    tests = [
        test_determine_scope_all_prior,
        test_determine_scope_entire_document,
        test_determine_scope_explicit,
        test_validate_patches_valid,
        test_validate_patches_with_markers,
        test_validate_patches_unknown_section,
        test_auto_apply_never,
        test_auto_apply_if_validation_passes_success,
        test_auto_apply_if_validation_passes_failure,
        test_extract_all_section_ids,
        test_section_exists,
        test_contains_markers,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
