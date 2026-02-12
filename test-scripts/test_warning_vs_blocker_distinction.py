#!/usr/bin/env python3
"""Test script to validate that warnings don't block gate progression while blockers do."""

import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.parsing import (
    check_section_table_for_open_blockers,
    check_section_table_for_open_questions,
)
from requirements_automation.models import ReviewIssue, ReviewResult
from requirements_automation.review_gate_handler import ReviewGateHandler


def create_test_document_with_mixed_questions() -> list:
    """Create a test document with warnings, blockers, and regular questions."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:doc_format version="1.0" -->',
        "<!-- workflow:order",
        "problem_statement",
        "assumptions",
        "review_gate:coherence_check",
        "-->",
        "",
        "# Test Requirements Document",
        "",
        "<!-- section:problem_statement -->",
        "## 1. Problem Statement",
        "This is a test problem statement.",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| problem_statement-Q1 | [WARNING] Minor style issue | 2024-01-01 | | Open |",
        "| problem_statement-Q2 | [BLOCKER] Critical missing information | 2024-01-01 | | Open |",
        "| problem_statement-Q3 | Regular question without prefix | 2024-01-01 | | Open |",
        "",
        "<!-- section:assumptions -->",
        "## 2. Assumptions",
        "- Assumption 1",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:assumptions_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| assumptions-Q1 | [WARNING] Should validate this assumption | 2024-01-01 | | Open |",
        "| assumptions-Q2 | [WARNING] Another minor warning | 2024-01-01 | | Open |",
        "",
    ]


def test_check_open_questions_counts_all():
    """Test that check_section_table_for_open_questions counts all open questions."""
    print("\nTest: check_section_table_for_open_questions counts all open questions...")
    
    lines = create_test_document_with_mixed_questions()
    
    # problem_statement has 3 open questions (1 warning, 1 blocker, 1 regular)
    has_open, count = check_section_table_for_open_questions(lines, "problem_statement")
    assert has_open, "Should detect open questions"
    assert count == 3, f"Expected 3 open questions, got {count}"
    
    # assumptions has 2 open warnings
    has_open, count = check_section_table_for_open_questions(lines, "assumptions")
    assert has_open, "Should detect open questions"
    assert count == 2, f"Expected 2 open questions, got {count}"
    
    print("  ✓ check_section_table_for_open_questions counts all open questions")
    return True


def test_check_open_blockers_excludes_warnings():
    """Test that check_section_table_for_open_blockers only counts blockers."""
    print("\nTest: check_section_table_for_open_blockers excludes warnings...")
    
    lines = create_test_document_with_mixed_questions()
    
    # problem_statement has 1 blocker and 1 regular (warnings excluded)
    has_blockers, count = check_section_table_for_open_blockers(lines, "problem_statement")
    assert has_blockers, "Should detect open blockers"
    assert count == 2, f"Expected 2 open blockers (1 [BLOCKER] + 1 unprefixed), got {count}"
    
    # assumptions has only warnings (should not be counted as blockers)
    has_blockers, count = check_section_table_for_open_blockers(lines, "assumptions")
    assert not has_blockers, "Should NOT detect blockers (only warnings present)"
    assert count == 0, f"Expected 0 open blockers, got {count}"
    
    print("  ✓ check_section_table_for_open_blockers excludes warnings")
    return True


def test_warnings_dont_block_coherence_gate():
    """Test that warnings don't block the coherence gate."""
    print("\nTest: Warnings don't block coherence gate...")
    
    # Create document with only warnings
    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:coherence_check",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## 1. Problem Statement",
        "Content here",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| problem_statement-Q1 | [WARNING] Minor issue | 2024-01-01 | | Open |",
        "| problem_statement-Q2 | [WARNING] Another warning | 2024-01-01 | | Open |",
        "",
    ]
    
    class MockLLM:
        pass
    
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    # Run coherence validation
    result = handler._validate_coherence_requirements(["problem_statement"])
    
    # Should pass because only warnings exist (no blockers)
    assert result.passed, "Gate should pass when only warnings are present"
    assert len(result.issues) == 0, f"Expected 0 blocker issues, got {len(result.issues)}"
    
    print("  ✓ Warnings don't block coherence gate")
    return True


def test_blockers_do_block_coherence_gate():
    """Test that blockers do block the coherence gate."""
    print("\nTest: Blockers do block coherence gate...")
    
    # Create document with blockers
    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:coherence_check",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## 1. Problem Statement",
        "Content here",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| problem_statement-Q1 | [WARNING] Minor issue | 2024-01-01 | | Open |",
        "| problem_statement-Q2 | [BLOCKER] Critical problem | 2024-01-01 | | Open |",
        "",
    ]
    
    class MockLLM:
        pass
    
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    # Run coherence validation
    result = handler._validate_coherence_requirements(["problem_statement"])
    
    # Should fail because a blocker exists
    assert not result.passed, "Gate should fail when blockers are present"
    assert len(result.issues) > 0, "Expected blocker issues"
    assert result.issues[0].severity == "blocker"
    
    print("  ✓ Blockers do block coherence gate")
    return True


def test_unprefixed_questions_treated_as_blockers():
    """Test that questions without severity prefix are treated as blockers (backward compatibility)."""
    print("\nTest: Unprefixed questions treated as blockers...")
    
    # Create document with unprefixed question
    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:coherence_check",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## 1. Problem Statement",
        "Content here",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| problem_statement-Q1 | Regular question without prefix | 2024-01-01 | | Open |",
        "",
    ]
    
    class MockLLM:
        pass
    
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    # Run coherence validation
    result = handler._validate_coherence_requirements(["problem_statement"])
    
    # Should fail because unprefixed questions are treated as blockers
    assert not result.passed, "Gate should fail for unprefixed open questions (backward compatibility)"
    assert len(result.issues) > 0, "Expected blocker issues for unprefixed questions"
    
    # Check via direct function call
    has_blockers, count = check_section_table_for_open_blockers(lines, "problem_statement")
    assert has_blockers, "Unprefixed questions should be counted as blockers"
    assert count == 1, f"Expected 1 blocker, got {count}"
    
    print("  ✓ Unprefixed questions treated as blockers (backward compatibility)")
    return True


def test_mixed_warnings_and_blockers():
    """Test handling of mixed warnings and blockers in the same section."""
    print("\nTest: Mixed warnings and blockers in same section...")
    
    lines = create_test_document_with_mixed_questions()
    
    class MockLLM:
        pass
    
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    # Run coherence validation on problem_statement (has 1 warning, 1 blocker, 1 unprefixed)
    result = handler._validate_coherence_requirements(["problem_statement"])
    
    # Should fail because blockers exist (even though warnings also exist)
    assert not result.passed, "Gate should fail when blockers are present (regardless of warnings)"
    assert len(result.issues) > 0, "Expected blocker issues"
    
    # The blocker count should be 2 (1 [BLOCKER] + 1 unprefixed)
    # The description should mention the correct count
    assert "2 open blocker(s)" in result.issues[0].description
    
    print("  ✓ Mixed warnings and blockers handled correctly")
    return True


def test_resolved_questions_dont_block():
    """Test that resolved questions (including blockers) don't block progression."""
    print("\nTest: Resolved questions don't block...")
    
    # Create document with resolved blockers and warnings
    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:coherence_check",
        "-->",
        "",
        "<!-- section:problem_statement -->",
        "## 1. Problem Statement",
        "Content here",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| problem_statement-Q1 | [WARNING] Minor issue | 2024-01-01 | Acknowledged | Resolved |",
        "| problem_statement-Q2 | [BLOCKER] Critical problem | 2024-01-01 | Fixed | Resolved |",
        "",
    ]
    
    class MockLLM:
        pass
    
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    # Run coherence validation
    result = handler._validate_coherence_requirements(["problem_statement"])
    
    # Should pass because all questions are resolved
    assert result.passed, "Gate should pass when all questions are resolved"
    assert len(result.issues) == 0, "Expected no blocker issues"
    
    print("  ✓ Resolved questions don't block")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Warning vs Blocker Distinction Test Suite")
    print("=" * 70)
    
    tests = [
        test_check_open_questions_counts_all,
        test_check_open_blockers_excludes_warnings,
        test_warnings_dont_block_coherence_gate,
        test_blockers_do_block_coherence_gate,
        test_unprefixed_questions_treated_as_blockers,
        test_mixed_warnings_and_blockers,
        test_resolved_questions_dont_block,
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
