#!/usr/bin/env python3
"""Test script for review gate warnings insertion into section question tables."""

import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.models import HandlerConfig, ReviewIssue, ReviewResult
from requirements_automation.review_gate_handler import ReviewGateHandler
from requirements_automation.section_questions import parse_section_questions


def create_test_document_with_question_tables() -> list:
    """Create a test document with sections and question tables."""
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
        "## 1. Problem Statement",
        "This is a test problem statement.",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "",
        "<!-- section:assumptions -->",
        "## 2. Assumptions",
        "- Assumption 1",
        "- Assumption 2",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:assumptions_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| assumptions-Q1 | Existing question? | 2024-01-01 | | Open |",
        "",
        "<!-- section:constraints -->",
        "## 3. Constraints",
        "### Technical Constraints",
        "- Constraint 1",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:constraints_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "",
        "<!-- section:requirements -->",
        "## 4. Requirements",
        "<!-- PLACEHOLDER -->",
        "",
    ]


def test_insert_warnings_into_section_tables():
    """Test inserting review warnings into section question tables."""
    print("\nTest: Insert review warnings into section question tables...")

    lines = create_test_document_with_question_tables()

    # Create a mock LLM client (won't be used for this test)
    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Create a review result with issues for different sections
    review_result = ReviewResult(
        gate_id="review_gate:coherence_check",
        passed=False,
        issues=[
            ReviewIssue(
                severity="warning",
                section="problem_statement",
                description="The problem statement is too vague",
                suggestion="Add more specific details",
            ),
            ReviewIssue(
                severity="blocker",
                section="assumptions",
                description="Assumption 1 contradicts constraint 1",
                suggestion=None,
            ),
            ReviewIssue(
                severity="warning",
                section="assumptions",
                description="Assumption 2 needs validation",
                suggestion="Verify with stakeholders",
            ),
            ReviewIssue(
                severity="warning",
                section="constraints",
                description="Missing performance constraints",
                suggestion="Define acceptable performance metrics",
            ),
        ],
        patches=[],
        scope_sections=["problem_statement", "assumptions", "constraints"],
        summary="Review found 4 issues",
    )

    # Insert issues into section tables
    updated_lines, total_inserted = handler.insert_issues_into_section_tables(
        review_result, lines
    )

    # Verify insertions
    print(f"  Total questions inserted: {total_inserted}")

    # Check problem_statement table
    ps_questions, _ = parse_section_questions(updated_lines, "problem_statement")
    ps_new = [q for q in ps_questions if "[WARNING]" in q.question or "[BLOCKER]" in q.question]
    print(f"  problem_statement table has {len(ps_new)} new review issue(s)")
    assert len(ps_new) == 1, f"Expected 1 issue in problem_statement, got {len(ps_new)}"
    assert "[WARNING]" in ps_new[0].question
    assert "too vague" in ps_new[0].question

    # Check assumptions table
    assump_questions, _ = parse_section_questions(updated_lines, "assumptions")
    assump_new = [q for q in assump_questions if "[WARNING]" in q.question or "[BLOCKER]" in q.question]
    print(f"  assumptions table has {len(assump_new)} new review issue(s)")
    assert len(assump_new) == 2, f"Expected 2 issues in assumptions, got {len(assump_new)}"
    
    # Check that existing question is preserved
    existing = [q for q in assump_questions if q.question_id == "assumptions-Q1"]
    assert len(existing) == 1, "Existing question should be preserved"

    # Check constraints table
    const_questions, _ = parse_section_questions(updated_lines, "constraints")
    const_new = [q for q in const_questions if "[WARNING]" in q.question or "[BLOCKER]" in q.question]
    print(f"  constraints table has {len(const_new)} new review issue(s)")
    assert len(const_new) == 1, f"Expected 1 issue in constraints, got {len(const_new)}"

    # Verify question IDs are properly generated
    assert ps_new[0].question_id == "problem_statement-Q1"
    # assumptions should have Q2 and Q3 (Q1 already exists)
    assump_ids = sorted([q.question_id for q in assump_new])
    assert "assumptions-Q2" in assump_ids
    assert "assumptions-Q3" in assump_ids
    assert const_new[0].question_id == "constraints-Q1"

    # Verify all questions have "Open" status and today's date
    for q in ps_new + assump_new + const_new:
        assert q.status == "Open", f"Question {q.question_id} status should be 'Open'"
        assert q.answer == "", f"Question {q.question_id} answer should be empty"
        # Date should be in YYYY-MM-DD format
        assert len(q.date) == 10, f"Date format should be YYYY-MM-DD, got {q.date}"

    print("  ✓ All review warnings correctly inserted into section tables")
    return True


def test_duplicate_insertion_prevention():
    """Test that duplicate warnings are not inserted."""
    print("\nTest: Duplicate warning insertion prevention...")

    lines = create_test_document_with_question_tables()

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Create a review result with the same issue
    review_result = ReviewResult(
        gate_id="review_gate:test",
        passed=False,
        issues=[
            ReviewIssue(
                severity="warning",
                section="problem_statement",
                description="The problem statement is too vague",
                suggestion=None,
            ),
        ],
        patches=[],
        scope_sections=["problem_statement"],
        summary="Review found 1 issue",
    )

    # First insertion
    lines, inserted1 = handler.insert_issues_into_section_tables(review_result, lines)
    assert inserted1 == 1, f"First insertion should add 1 question, got {inserted1}"

    # Update handler's lines reference
    handler.lines = lines

    # Second insertion with same issue (should be skipped as duplicate)
    lines, inserted2 = handler.insert_issues_into_section_tables(review_result, lines)
    assert inserted2 == 0, f"Second insertion should skip duplicate, got {inserted2} insertions"

    # Verify only one question exists
    ps_questions, _ = parse_section_questions(lines, "problem_statement")
    assert len(ps_questions) == 1, f"Should have only 1 question, got {len(ps_questions)}"

    print("  ✓ Duplicate warnings correctly prevented")
    return True


def test_section_without_question_table():
    """Test handling of sections without question tables."""
    print("\nTest: Handling sections without question tables...")

    # Create document with section that has no question table
    lines = [
        '<!-- meta:doc_type value="requirements" -->',
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "Content here",
        "",
        "<!-- section:assumptions -->",
        "## Assumptions",
        "Content here",
        "",
    ]

    class MockLLM:
        pass

    handler = ReviewGateHandler(MockLLM(), lines, "requirements")

    # Create a review result with issue for section without table
    review_result = ReviewResult(
        gate_id="review_gate:test",
        passed=False,
        issues=[
            ReviewIssue(
                severity="warning",
                section="problem_statement",
                description="Missing details",
                suggestion=None,
            ),
        ],
        patches=[],
        scope_sections=["problem_statement"],
        summary="Review found 1 issue",
    )

    # Insert should handle gracefully (log warning but not crash)
    lines, inserted = handler.insert_issues_into_section_tables(review_result, lines)
    
    # No insertion should happen since table doesn't exist
    assert inserted == 0, f"Should insert 0 when table missing, got {inserted}"

    print("  ✓ Sections without question tables handled gracefully")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Review Gate Warnings Insertion Test Suite")
    print("=" * 70)

    tests = [
        test_insert_warnings_into_section_tables,
        test_duplicate_insertion_prevention,
        test_section_without_question_table,
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
