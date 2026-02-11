#!/usr/bin/env python3
"""Test suite for per-section question management functionality."""

import sys
from pathlib import Path

# Add tools directory to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.section_questions import (
    get_section_questions_table_name,
    insert_section_question,
    insert_section_questions_batch,
    parse_section_questions,
    resolve_section_question,
    resolve_section_questions_batch,
    section_questions_next_id,
    has_open_section_questions,
    section_has_answered_questions,
)


def test_table_name_generation():
    """Test that table names are generated correctly."""
    print("Testing table name generation...")
    
    assert get_section_questions_table_name("problem_statement") == "problem_statement_questions"
    assert get_section_questions_table_name("goals_objectives") == "goals_objectives_questions"
    
    print("✓ Table name generation works correctly")


def test_parse_section_questions():
    """Test parsing section questions table."""
    print("\nTesting section questions parsing...")
    
    # Create a test document with section questions
    lines = [
        "<!-- section:problem_statement -->",
        "## 2. Problem Statement",
        "Some content here.",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:problem_statement_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| problem_statement-Q1 | What is the pain point? | 2024-01-01 | | Open |",
        "| problem_statement-Q2 | Who are the users? | 2024-01-01 | Team leads | Open |",
        "",
        "<!-- section_lock:problem_statement lock=false -->",
    ]
    
    questions, span = parse_section_questions(lines, "problem_statement")
    
    assert len(questions) == 2
    assert questions[0].question_id == "problem_statement-Q1"
    assert questions[0].question == "What is the pain point?"
    assert questions[0].status == "Open"
    assert questions[0].answer == ""
    
    assert questions[1].question_id == "problem_statement-Q2"
    assert questions[1].answer == "Team leads"
    
    print(f"✓ Parsed {len(questions)} questions correctly")


def test_next_id_generation():
    """Test generating next sequential question ID."""
    print("\nTesting next ID generation...")
    
    from requirements_automation.models import OpenQuestion
    
    existing = [
        OpenQuestion("problem_statement-Q1", "Q1", "date", "", "problem_statement", "Open"),
        OpenQuestion("problem_statement-Q2", "Q2", "date", "", "problem_statement", "Open"),
    ]
    
    next_id = section_questions_next_id("problem_statement", existing)
    assert next_id == "problem_statement-Q3"
    
    # Test with empty list
    next_id = section_questions_next_id("goals_objectives", [])
    assert next_id == "goals_objectives-Q1"
    
    print("✓ Next ID generation works correctly")


def test_insert_question():
    """Test inserting a single question."""
    print("\nTesting question insertion...")
    
    lines = [
        "<!-- section:assumptions -->",
        "## 5. Assumptions",
        "1. Assumption 1",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:assumptions_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| assumptions-Q1 | Have assumptions been validated? | 2024-01-01 | | Open |",
        "",
    ]
    
    updated_lines, qid = insert_section_question(
        lines, "assumptions", "What if assumption 1 is wrong?", "2024-01-02"
    )
    
    assert qid == "assumptions-Q2"
    # Verify the new row was inserted
    table_content = "\n".join(updated_lines)
    assert "assumptions-Q2" in table_content
    assert "What if assumption 1 is wrong?" in table_content
    
    print(f"✓ Question inserted with ID {qid}")


def test_insert_batch():
    """Test batch insertion of questions."""
    print("\nTesting batch question insertion...")
    
    lines = [
        "<!-- section:constraints -->",
        "## 6. Constraints",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:constraints_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "",
    ]
    
    questions = [
        ("Are there workarounds?", "2024-01-01"),
        ("What is the priority ranking?", "2024-01-01"),
        ("Can we negotiate constraints?", "2024-01-01"),
    ]
    
    updated_lines, count = insert_section_questions_batch(lines, "constraints", questions)
    
    assert count == 3
    table_content = "\n".join(updated_lines)
    assert "constraints-Q1" in table_content
    assert "constraints-Q2" in table_content
    assert "constraints-Q3" in table_content
    
    print(f"✓ Batch inserted {count} questions")


def test_resolve_question():
    """Test resolving a single question."""
    print("\nTesting question resolution...")
    
    lines = [
        "<!-- section:success_criteria -->",
        "## Success Criteria",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:success_criteria_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| success_criteria-Q1 | How will success be measured? | 2024-01-01 | Using metrics | Open |",
        "| success_criteria-Q2 | Who verifies criteria? | 2024-01-01 | | Open |",
        "",
    ]
    
    updated_lines, resolved = resolve_section_question(
        lines, "success_criteria", "success_criteria-Q1"
    )
    
    assert resolved is True
    table_content = "\n".join(updated_lines)
    # Find the row and verify status changed
    assert "success_criteria-Q1" in table_content
    # The status should be Resolved now
    lines_after = updated_lines
    for line in lines_after:
        if "success_criteria-Q1" in line:
            assert "Resolved" in line
            break
    
    print("✓ Question resolved successfully")


def test_resolve_batch():
    """Test batch resolution of questions."""
    print("\nTesting batch question resolution...")
    
    lines = [
        "<!-- section:goals_objectives -->",
        "## 3. Goals",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:goals_objectives_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| goals_objectives-Q1 | What are success indicators? | 2024-01-01 | KPIs defined | Open |",
        "| goals_objectives-Q2 | How do goals align? | 2024-01-01 | Aligned | Open |",
        "| goals_objectives-Q3 | What are dependencies? | 2024-01-01 | | Open |",
        "",
    ]
    
    updated_lines, count = resolve_section_questions_batch(
        lines, "goals_objectives", ["goals_objectives-Q1", "goals_objectives-Q2"]
    )
    
    assert count == 2
    table_content = "\n".join(updated_lines)
    
    # Verify both questions are resolved
    resolved_count = table_content.count("| Resolved |")
    assert resolved_count >= 2
    
    print(f"✓ Batch resolved {count} questions")


def test_duplicate_prevention():
    """Test that duplicate questions are not inserted."""
    print("\nTesting duplicate prevention...")
    
    lines = [
        "<!-- section:stakeholders_users -->",
        "## 4. Stakeholders",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:stakeholders_users_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| stakeholders_users-Q1 | Have all stakeholders been identified? | 2024-01-01 | | Open |",
        "",
    ]
    
    # Try to insert the same question (normalized)
    updated_lines, qid = insert_section_question(
        lines,
        "stakeholders_users",
        "Have all stakeholders been identified?",
        "2024-01-02",
    )
    
    # Should return existing ID
    assert qid == "stakeholders_users-Q1"
    # Lines should be unchanged
    assert len(updated_lines) == len(lines)
    
    print("✓ Duplicate prevention works correctly")


def test_has_open_questions():
    """Test checking for open questions."""
    print("\nTesting open questions check...")
    
    lines = [
        "<!-- section:assumptions -->",
        "## 5. Assumptions",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:assumptions_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| assumptions-Q1 | Question 1 | 2024-01-01 | | Open |",
        "| assumptions-Q2 | Question 2 | 2024-01-01 | Answer | Resolved |",
        "",
    ]
    
    assert has_open_section_questions(lines, "assumptions") is True
    
    # Now resolve all questions
    lines, _ = resolve_section_question(lines, "assumptions", "assumptions-Q1")
    assert has_open_section_questions(lines, "assumptions") is False
    
    print("✓ Open questions check works correctly")


def test_has_answered_questions():
    """Test checking for answered but not resolved questions."""
    print("\nTesting answered questions check...")
    
    lines = [
        "<!-- section:constraints -->",
        "## 6. Constraints",
        "",
        "<!-- subsection:questions_issues -->",
        "### Questions & Issues",
        "",
        "<!-- table:constraints_questions -->",
        "| Question ID | Question | Date | Answer | Status |",
        "|-------------|----------|------|--------|--------|",
        "| constraints-Q1 | Question 1 | 2024-01-01 | | Open |",
        "| constraints-Q2 | Question 2 | 2024-01-01 | Some answer | Open |",
        "",
    ]
    
    assert section_has_answered_questions(lines, "constraints") is True
    
    print("✓ Answered questions check works correctly")


def run_all_tests():
    """Run all section questions tests."""
    print("=" * 60)
    print("SECTION QUESTIONS TEST SUITE")
    print("=" * 60)
    
    try:
        test_table_name_generation()
        test_parse_section_questions()
        test_next_id_generation()
        test_insert_question()
        test_insert_batch()
        test_resolve_question()
        test_resolve_batch()
        test_duplicate_prevention()
        test_has_open_questions()
        test_has_answered_questions()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
