#!/usr/bin/env python3
"""
Unit tests for DocumentValidator completion criteria checking.

This test validates that the document validator correctly checks all
completion criteria and provides accurate status reporting.
"""
import sys
from pathlib import Path
from typing import List

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.document_validator import DocumentValidator
from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.parsing import extract_workflow_order
from requirements_automation.utils_io import read_text, split_lines

def create_test_document(
    has_placeholder: bool = False,
    has_open_questions: bool = False,
    has_review_gate_result: bool = False,
    review_gate_passed: bool = True,
    has_duplicate_markers: bool = False,
) -> List[str]:
    """Create a test document with various states."""
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- meta:doc_format version=\"1.0\" -->",
        "",
        "<!-- workflow:order",
        "problem_statement",
        "goals_objectives",
        "review_gate:test_gate",
        "assumptions",
        "-->",
        "",
    ]
    
    # Add review gate result marker if requested
    if has_review_gate_result:
        status = "passed" if review_gate_passed else "failed"
        issues = 0 if review_gate_passed else 1
        lines.append(f"<!-- review_gate_result:review_gate:test_gate status={status} issues={issues} warnings=0 -->")
        lines.append("")
    
    lines.extend([
        "# Requirements Document",
        "",
        "## Open Questions",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "| ----------- | -------- | ---- | ------ | -------------- | ----------------- |",
    ])
    
    if has_open_questions:
        lines.append("| Q-001 | Test question? | 2024-01-01 |  | problem_statement | Open |")
    else:
        lines.append("| Q-001 | Test question? | 2024-01-01 | Test answer | problem_statement | Resolved |")
    
    lines.extend([
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
    ])
    
    if has_placeholder:
        lines.append("<!-- PLACEHOLDER -->")
    else:
        lines.append("This is the problem statement.")
    
    lines.extend([
        "",
        "<!-- section:goals_objectives -->",
        "## Goals & Objectives",
        "- Goal 1",
        "- Goal 2",
        "",
    ])
    
    # Add duplicate marker if requested
    if has_duplicate_markers:
        lines.append("<!-- section:goals_objectives -->")
        lines.append("## Duplicate Goals")
        lines.append("")
    
    lines.extend([
        "<!-- section:assumptions -->",
        "## Assumptions",
        "- Assumption 1",
        "",
    ])
    
    return lines


def test_complete_document():
    """Test that a fully complete document passes all criteria."""
    print("Test 1: Complete document (all criteria pass)...")
    
    lines = create_test_document(
        has_placeholder=False,
        has_open_questions=False,
        has_review_gate_result=True,
        review_gate_passed=True,
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if status.complete:
        print("  ✓ Document marked as COMPLETE")
        print(f"  ✓ All {len(status.checks)} checks passed")
        return True
    else:
        print(f"  ✗ Document marked as INCOMPLETE")
        print(f"  ✗ Blocking failures: {status.blocking_failures}")
        for check in status.checks:
            if not check.passed:
                print(f"     - {check.criterion}: {check.details}")
        return False


def test_document_with_placeholder():
    """Test that document with PLACEHOLDER fails completion."""
    print("\nTest 2: Document with PLACEHOLDER token...")
    
    lines = create_test_document(
        has_placeholder=True,
        has_open_questions=False,
        has_review_gate_result=True,
        review_gate_passed=True,
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if not status.complete and "no_placeholders_in_required_sections" in status.blocking_failures:
        print("  ✓ Document correctly marked as INCOMPLETE")
        print(f"  ✓ Failed criterion: no_placeholders_in_required_sections")
        return True
    else:
        print(f"  ✗ Document should be INCOMPLETE due to placeholder")
        print(f"  ✗ Blocking failures: {status.blocking_failures}")
        return False


def test_document_with_open_questions():
    """Test that document with Open questions fails completion."""
    print("\nTest 3: Document with Open questions...")
    
    lines = create_test_document(
        has_placeholder=False,
        has_open_questions=True,
        has_review_gate_result=True,
        review_gate_passed=True,
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if not status.complete and "no_open_questions" in status.blocking_failures:
        print("  ✓ Document correctly marked as INCOMPLETE")
        print(f"  ✓ Failed criterion: no_open_questions")
        # Find the check details
        for check in status.checks:
            if check.criterion == "no_open_questions":
                print(f"  ✓ Details: {check.details}")
        return True
    else:
        print(f"  ✗ Document should be INCOMPLETE due to open questions")
        print(f"  ✗ Blocking failures: {status.blocking_failures}")
        return False


def test_document_with_failed_review_gate():
    """Test that document with failed review gate fails completion."""
    print("\nTest 4: Document with failed review gate...")
    
    lines = create_test_document(
        has_placeholder=False,
        has_open_questions=False,
        has_review_gate_result=True,
        review_gate_passed=False,
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if not status.complete and "all_review_gates_pass" in status.blocking_failures:
        print("  ✓ Document correctly marked as INCOMPLETE")
        print(f"  ✓ Failed criterion: all_review_gates_pass")
        return True
    else:
        print(f"  ✗ Document should be INCOMPLETE due to failed review gate")
        print(f"  ✗ Blocking failures: {status.blocking_failures}")
        return False


def test_document_with_duplicate_markers():
    """Test that document with duplicate section markers fails completion."""
    print("\nTest 5: Document with duplicate section markers...")
    
    lines = create_test_document(
        has_placeholder=False,
        has_open_questions=False,
        has_review_gate_result=True,
        review_gate_passed=True,
        has_duplicate_markers=True,
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if not status.complete and "structure_valid" in status.blocking_failures:
        print("  ✓ Document correctly marked as INCOMPLETE")
        print(f"  ✓ Failed criterion: structure_valid")
        return True
    else:
        print(f"  ✗ Document should be INCOMPLETE due to duplicate markers")
        print(f"  ✗ Blocking failures: {status.blocking_failures}")
        return False


def test_document_without_review_gate_result():
    """Test that document without review gate execution fails completion."""
    print("\nTest 6: Document with unexecuted review gate...")
    
    lines = create_test_document(
        has_placeholder=False,
        has_open_questions=False,
        has_review_gate_result=False,  # No review gate result
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if not status.complete and "all_review_gates_pass" in status.blocking_failures:
        print("  ✓ Document correctly marked as INCOMPLETE")
        print(f"  ✓ Failed criterion: all_review_gates_pass")
        return True
    else:
        print(f"  ✗ Document should be INCOMPLETE due to unexecuted review gate")
        print(f"  ✗ Blocking failures: {status.blocking_failures}")
        return False


def test_strict_mode_with_deferred_questions():
    """Test that strict mode fails on Deferred questions."""
    print("\nTest 7: Strict mode with Deferred questions...")
    
    lines = create_test_document(
        has_placeholder=False,
        has_open_questions=False,
        has_review_gate_result=True,
        review_gate_passed=True,
    )
    
    # Replace resolved question with deferred one
    for i, line in enumerate(lines):
        if "| Q-001 |" in line:
            lines[i] = "| Q-001 | Test question? | 2024-01-01 | Answer later | problem_statement | Deferred |"
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    
    # Normal mode should pass
    status_normal = validator.validate_completion(strict=False)
    # Strict mode should fail
    status_strict = validator.validate_completion(strict=True)
    
    if status_normal.complete and not status_strict.complete:
        print("  ✓ Normal mode: COMPLETE (Deferred questions OK)")
        print("  ✓ Strict mode: INCOMPLETE (Deferred questions not OK)")
        return True
    else:
        print(f"  ✗ Normal mode complete: {status_normal.complete}, Strict mode complete: {status_strict.complete}")
        return False


def test_human_readable_output():
    """Test that human-readable output is formatted correctly."""
    print("\nTest 8: Human-readable output format...")
    
    lines = create_test_document(
        has_placeholder=True,
        has_open_questions=True,
        has_review_gate_result=False,
    )
    
    workflow_order = extract_workflow_order(lines)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    validator = DocumentValidator(lines, workflow_order, registry, "requirements")
    status = validator.validate_completion(strict=False)
    
    if status.summary:
        print("  ✓ Summary generated")
        print("\n--- Summary Preview ---")
        print(status.summary[:500])
        print("--- End Preview ---\n")
        
        # Check for expected elements
        has_status = "INCOMPLETE" in status.summary or "COMPLETE" in status.summary
        has_icons = "✅" in status.summary or "❌" in status.summary
        has_blocking = "Blocking Issues:" in status.summary if not status.complete else True
        
        if has_status and has_icons and has_blocking:
            print("  ✓ Summary has status, icons, and blocking issues")
            return True
        else:
            print(f"  ✗ Summary missing elements: status={has_status}, icons={has_icons}, blocking={has_blocking}")
            return False
    else:
        print("  ✗ No summary generated")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Document Validator Test Suite")
    print("=" * 70)
    
    tests = [
        test_complete_document,
        test_document_with_placeholder,
        test_document_with_open_questions,
        test_document_with_failed_review_gate,
        test_document_with_duplicate_markers,
        test_document_without_review_gate_result,
        test_strict_mode_with_deferred_questions,
        test_human_readable_output,
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
