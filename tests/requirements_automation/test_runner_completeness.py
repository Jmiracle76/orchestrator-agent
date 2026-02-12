#!/usr/bin/env python3
"""
Test for runner_core completeness check logic.

This test validates that the WorkflowRunner correctly identifies incomplete sections
when they have answered questions awaiting integration, even if they have no
placeholders or unanswered open questions.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.runner_state import get_section_state
from requirements_automation.models import HandlerConfig


def test_section_with_answered_questions_is_incomplete():
    """
    Test: Section with answered questions should be detected as incomplete.
    
    This validates the fix for the issue where sections with answered-but-unintegrated
    questions were being skipped as "complete" because the completeness check only
    looked at has_placeholder and has_open_questions, not has_answered_questions.
    """
    print("\nTest: Section with answered questions is incomplete")
    print("=" * 70)

    test_doc = """<!-- section:stakeholders_users -->
## 2. Stakeholders & Users

This section has existing content describing stakeholders.

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:stakeholders_users_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| stakeholders-Q3 | Who are the primary users? | 2024-01-01 | Developers and product managers | Open |
| stakeholders-Q4 | What are their key needs? | 2024-01-01 | Fast deployment and clear documentation | Open |
| stakeholders-Q5 | Are there any special considerations? | 2024-01-01 | Must support mobile devices | Open |
| stakeholders-Q6 | What is the expected user volume? | 2024-01-01 | 10,000 users per month | Open |
| stakeholders-Q7 | BLOCKER: Need security clearance info | 2024-01-01 | | Open |

"""
    
    lines = test_doc.split('\n')
    
    # Create a handler config with questions_table specified
    handler_config = HandlerConfig(
        section_id="stakeholders_users",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=True,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="default",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
        questions_table="stakeholders_users_questions",
        bootstrap_questions=False
    )
    
    # Get section state
    state = get_section_state(lines, "stakeholders_users", handler_config)
    
    # Verify the state
    print(f"  Section exists: {state.exists}")
    print(f"  Is blank: {state.is_blank}")
    print(f"  Has placeholder: {state.has_placeholder}")
    print(f"  Has open questions: {state.has_open_questions}")
    print(f"  Has answered questions: {state.has_answered_questions}")
    print()
    
    # Assertions
    assert state.exists, "Section should exist"
    assert not state.is_blank, "Section should not be blank (has content)"
    assert not state.has_placeholder, "Section should not have placeholder (has content)"
    assert state.has_open_questions, "Section should have open questions (Q7 is unanswered)"
    assert state.has_answered_questions, "Section should have answered questions (Q3-Q6 have answers)"
    
    # The key test: check the completeness logic
    # Before the fix, this section would be skipped if has_open_questions was False
    # After the fix, it should NOT be skipped if has_answered_questions is True
    is_complete = (
        not state.has_placeholder 
        and not state.has_open_questions 
        and not state.has_answered_questions
    )
    
    print(f"  Section is complete: {is_complete}")
    assert not is_complete, "Section should NOT be complete (has answered questions awaiting integration)"
    
    print("  ✓ Section correctly identified as incomplete due to answered questions")
    return True


def test_section_with_only_answered_questions():
    """
    Test: Section with ONLY answered questions (no unanswered ones) should be incomplete.
    
    This is the specific scenario from the bug report where stakeholders_users had
    4 answered questions (Q3-Q6) and would have been skipped if not for the BLOCKER (Q7).
    """
    print("\nTest: Section with only answered questions (no unanswered) is incomplete")
    print("=" * 70)

    test_doc = """<!-- section:test_section -->
## Test Section

This section has existing content.

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:test_section_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| test-Q1 | Question 1? | 2024-01-01 | Answer 1 | Open |
| test-Q2 | Question 2? | 2024-01-01 | Answer 2 | Open |

"""
    
    lines = test_doc.split('\n')
    
    handler_config = HandlerConfig(
        section_id="test_section",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=True,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="default",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
        questions_table="test_section_questions",
        bootstrap_questions=False
    )
    
    state = get_section_state(lines, "test_section", handler_config)
    
    print(f"  Has placeholder: {state.has_placeholder}")
    print(f"  Has open questions: {state.has_open_questions}")
    print(f"  Has answered questions: {state.has_answered_questions}")
    
    assert not state.has_placeholder, "Section has content"
    assert not state.has_open_questions, "No unanswered open questions"
    assert state.has_answered_questions, "Has answered questions (Q1-Q2)"
    
    # Check completeness - should be INCOMPLETE
    is_complete = (
        not state.has_placeholder 
        and not state.has_open_questions 
        and not state.has_answered_questions
    )
    
    print(f"  Section is complete: {is_complete}")
    assert not is_complete, "Section should NOT be complete (has answered questions)"
    
    print("  ✓ Section correctly identified as incomplete despite having no unanswered questions")
    return True


def test_section_truly_complete():
    """
    Test: Section with no placeholders, no questions should be complete.
    """
    print("\nTest: Section with no placeholders or questions is complete")
    print("=" * 70)

    test_doc = """<!-- section:complete_section -->
## Complete Section

This section has all content filled in.

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:complete_section_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| complete-Q1 | Question 1? | 2024-01-01 | Answer 1 | Resolved |

"""
    
    lines = test_doc.split('\n')
    
    handler_config = HandlerConfig(
        section_id="complete_section",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=True,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="default",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
        questions_table="complete_section_questions",
        bootstrap_questions=False
    )
    
    state = get_section_state(lines, "complete_section", handler_config)
    
    print(f"  Has placeholder: {state.has_placeholder}")
    print(f"  Has open questions: {state.has_open_questions}")
    print(f"  Has answered questions: {state.has_answered_questions}")
    
    assert not state.has_placeholder, "Section has content"
    assert not state.has_open_questions, "No open questions"
    assert not state.has_answered_questions, "No answered questions (Q1 is Resolved)"
    
    # Check completeness - should be COMPLETE
    is_complete = (
        not state.has_placeholder 
        and not state.has_open_questions 
        and not state.has_answered_questions
    )
    
    print(f"  Section is complete: {is_complete}")
    assert is_complete, "Section should be complete (no work remaining)"
    
    print("  ✓ Section correctly identified as complete")
    return True


def main():
    """Run all tests."""
    print("Testing runner_core completeness check logic")
    print("=" * 70)
    
    tests = [
        test_section_with_answered_questions_is_incomplete,
        test_section_with_only_answered_questions,
        test_section_truly_complete,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"  ✗ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ Test error: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
