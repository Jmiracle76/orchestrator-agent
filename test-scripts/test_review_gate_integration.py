#!/usr/bin/env python3
"""Integration test for review gate warnings insertion through runner."""

import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.models import HandlerConfig, ReviewIssue, ReviewResult
from requirements_automation.runner_handlers import execute_review_gate
from requirements_automation.section_questions import parse_section_questions


def create_test_document() -> list:
    """Create a test document with sections and question tables."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:doc_format version="1.0" -->',
        "<!-- workflow:order",
        "problem_statement",
        "assumptions",
        "review_gate:initial_review",
        "requirements",
        "-->",
        "",
        "# Test Requirements Document",
        "",
        "<!-- section:problem_statement -->",
        "## 1. Problem Statement",
        "This is a test problem statement that may have issues.",
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
        "- Assumption 1: Database will be available",
        "- Assumption 2: Users have internet access",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:assumptions_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "",
        "<!-- section:requirements -->",
        "## 3. Requirements",
        "<!-- PLACEHOLDER -->",
        "",
    ]


class MockLLM:
    """Mock LLM client that returns predefined review results."""

    def perform_review(self, gate_id, doc_type, section_contents, llm_profile, validation_rules):
        """Return mock review data with issues."""
        return {
            "passed": False,
            "summary": "Review found several issues that need attention",
            "issues": [
                {
                    "severity": "warning",
                    "section": "problem_statement",
                    "description": "Problem statement lacks quantifiable success criteria",
                    "suggestion": "Add measurable outcomes",
                },
                {
                    "severity": "blocker",
                    "section": "assumptions",
                    "description": "Assumption 1 is not validated with stakeholders",
                    "suggestion": "Schedule stakeholder review",
                },
                {
                    "severity": "warning",
                    "section": "assumptions",
                    "description": "Assumption 2 conflicts with offline usage requirement",
                    "suggestion": None,
                },
            ],
            "patches": [],
        }


def test_execute_review_gate_integration():
    """Test complete review gate execution through runner."""
    print("\nTest: Complete review gate execution with warnings insertion...")

    lines = create_test_document()
    
    # Create handler config
    handler_config = HandlerConfig(
        section_id="review_gate:initial_review",
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

    # Execute review gate through runner
    updated_lines, result = execute_review_gate(
        lines=lines,
        target_id="review_gate:initial_review",
        llm=MockLLM(),
        doc_type="requirements",
        handler_config=handler_config,
        dry_run=False,
    )

    # Verify WorkflowResult
    print(f"  Action taken: {result.action_taken}")
    print(f"  Changed: {result.changed}")
    print(f"  Blocked: {result.blocked}")
    print(f"  Questions generated: {result.questions_generated}")
    print(f"  Blocked reasons: {result.blocked_reasons}")
    
    assert result.action_taken == "review_gate"
    assert result.changed == True, "Document should be marked as changed"
    assert result.blocked == True, "Should be blocked due to blocker issue"
    assert result.questions_generated == 3, f"Expected 3 questions generated, got {result.questions_generated}"
    assert len(result.blocked_reasons) == 1, f"Expected 1 blocker reason, got {len(result.blocked_reasons)}"
    
    # Verify review gate result marker was written
    marker_found = False
    for line in updated_lines:
        if "review_gate_result:review_gate:initial_review" in line:
            marker_found = True
            assert "status=failed" in line
            assert "issues=1" in line  # 1 blocker
            assert "warnings=2" in line  # 2 warnings
            break
    assert marker_found, "Review gate result marker not found in document"
    
    # Verify questions were inserted into problem_statement table
    ps_questions, _ = parse_section_questions(updated_lines, "problem_statement")
    ps_new = [q for q in ps_questions if "[WARNING]" in q.question]
    assert len(ps_new) == 1, f"Expected 1 warning in problem_statement, got {len(ps_new)}"
    assert "lacks quantifiable success criteria" in ps_new[0].question
    assert ps_new[0].question_id == "problem_statement-Q1"
    assert ps_new[0].status == "Open"
    
    # Verify questions were inserted into assumptions table
    assump_questions, _ = parse_section_questions(updated_lines, "assumptions")
    assump_warnings = [q for q in assump_questions if "[WARNING]" in q.question]
    assump_blockers = [q for q in assump_questions if "[BLOCKER]" in q.question]
    
    assert len(assump_warnings) == 1, f"Expected 1 warning in assumptions, got {len(assump_warnings)}"
    assert len(assump_blockers) == 1, f"Expected 1 blocker in assumptions, got {len(assump_blockers)}"
    
    # Check specific content
    assert "not validated with stakeholders" in assump_blockers[0].question
    assert "conflicts with offline usage" in assump_warnings[0].question
    
    # Verify IDs are sequential
    assump_ids = sorted([q.question_id for q in assump_questions])
    assert assump_ids == ["assumptions-Q1", "assumptions-Q2"]
    
    print("  ✓ Review gate executed successfully with warnings inserted")
    print("  ✓ WorkflowResult contains correct question count")
    print("  ✓ Review gate result marker written to document")
    print("  ✓ All warnings inserted into correct section tables")
    
    return True


def test_subsequent_run_skips_duplicate_warnings():
    """Test that running review gate again doesn't duplicate warnings."""
    print("\nTest: Subsequent review gate run doesn't duplicate warnings...")

    lines = create_test_document()
    
    handler_config = HandlerConfig(
        section_id="review_gate:initial_review",
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

    # First run
    lines, result1 = execute_review_gate(
        lines=lines,
        target_id="review_gate:initial_review",
        llm=MockLLM(),
        doc_type="requirements",
        handler_config=handler_config,
        dry_run=False,
    )
    
    assert result1.questions_generated == 3
    
    # Second run with same warnings
    lines, result2 = execute_review_gate(
        lines=lines,
        target_id="review_gate:initial_review",
        llm=MockLLM(),
        doc_type="requirements",
        handler_config=handler_config,
        dry_run=False,
    )
    
    # Second run should detect duplicates and not insert
    assert result2.questions_generated == 0, f"Expected 0 questions on second run, got {result2.questions_generated}"
    
    # Verify total question count didn't increase
    ps_questions, _ = parse_section_questions(lines, "problem_statement")
    assert len(ps_questions) == 1, f"Expected 1 question in problem_statement, got {len(ps_questions)}"
    
    assump_questions, _ = parse_section_questions(lines, "assumptions")
    assert len(assump_questions) == 2, f"Expected 2 questions in assumptions, got {len(assump_questions)}"
    
    print("  ✓ Duplicate warnings correctly prevented on subsequent runs")
    
    return True


def test_console_output_still_shown():
    """Test that console output is still displayed for human readability."""
    print("\nTest: Console output still displayed...")

    lines = create_test_document()
    
    handler_config = HandlerConfig(
        section_id="review_gate:initial_review",
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

    # Capture would require redirecting stdout, but we can verify that
    # the formatting function is still called by checking the result
    lines, result = execute_review_gate(
        lines=lines,
        target_id="review_gate:initial_review",
        llm=MockLLM(),
        doc_type="requirements",
        handler_config=handler_config,
        dry_run=False,
    )
    
    # Verify summaries are populated (these are what get formatted and printed)
    assert len(result.summaries) > 0, "Summaries should be populated for console output"
    assert any("warning:" in s.lower() for s in result.summaries), "Should include warning summaries"
    assert any("blocker:" in s.lower() for s in result.summaries), "Should include blocker summaries"
    
    print("  ✓ Console output summaries are still populated")
    
    return True


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("Review Gate Integration Test Suite")
    print("=" * 70)

    tests = [
        test_execute_review_gate_integration,
        test_subsequent_run_skips_duplicate_warnings,
        test_console_output_still_shown,
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
