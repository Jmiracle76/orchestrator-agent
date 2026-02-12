#!/usr/bin/env python3
"""
Test script for coherence_check review gate functionality.

This script validates that the coherence_check gate:
1. Blocks if any prior section has open questions
2. Blocks if any risk is not low/low
3. On pass, locks all prior sections
4. On pass, updates the approval record
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.parsing import (
    check_risks_table_for_non_low_risks,
    check_section_table_for_open_questions,
    set_section_lock,
    section_is_locked,
    find_sections,
    get_section_span,
    update_approval_record_table,
)


def create_test_document_with_open_questions() -> list:
    """Create a test document with open questions in a section table."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- workflow:order',
        'problem_statement',
        'assumptions',
        'review_gate:coherence_check',
        'requirements',
        '-->',
        '',
        '# Test Document',
        '',
        '<!-- section:problem_statement -->',
        '## Problem Statement',
        'This is a test.',
        '',
        '### Questions & Issues',
        '<!-- table:problem_statement_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q1 | Test question? | 2024-01-01 | Test answer | Resolved |',
        '| Q2 | Another question? | 2024-01-02 | | Open |',
        '',
        '<!-- section_lock:problem_statement lock=false -->',
        '---',
        '',
        '<!-- section:assumptions -->',
        '## Assumptions',
        '- Assumption 1',
        '',
        '<!-- section_lock:assumptions lock=false -->',
        '---',
    ]


def create_test_document_with_high_risks() -> list:
    """Create a test document with high-risk entries."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- workflow:order',
        'problem_statement',
        'assumptions',
        'identified_risks',
        'review_gate:coherence_check',
        'requirements',
        '-->',
        '',
        '# Test Document',
        '',
        '<!-- section:problem_statement -->',
        '## Problem Statement',
        'Test content.',
        '',
        '### Questions & Issues',
        '<!-- table:problem_statement_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q1 | Test? | 2024-01-01 | Yes | Resolved |',
        '',
        '<!-- section_lock:problem_statement lock=false -->',
        '---',
        '',
        '<!-- section:identified_risks -->',
        '## Risks',
        '',
        '<!-- table:risks -->',
        '| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |',
        '|---------|-------------|-------------|--------|---------------------|-------|',
        '| R1 | Data loss risk | High | High | Backup strategy | Team |',
        '| R2 | Performance issue | Low | Low | Optimization | Team |',
        '',
        '<!-- section_lock:identified_risks lock=false -->',
        '---',
    ]


def create_test_document_passing() -> list:
    """Create a test document that should pass coherence checks."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- workflow:order',
        'problem_statement',
        'assumptions',
        'identified_risks',
        'review_gate:coherence_check',
        'requirements',
        '-->',
        '',
        '# Test Document',
        '',
        '<!-- section:problem_statement -->',
        '## Problem Statement',
        'Test content.',
        '',
        '### Questions & Issues',
        '<!-- table:problem_statement_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q1 | Test? | 2024-01-01 | Yes | Resolved |',
        '',
        '<!-- section_lock:problem_statement lock=false -->',
        '---',
        '',
        '<!-- section:assumptions -->',
        '## Assumptions',
        '- Assumption 1',
        '',
        '### Questions & Issues',
        '<!-- table:assumptions_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q2 | Assumption valid? | 2024-01-01 | Yes | Resolved |',
        '',
        '<!-- section_lock:assumptions lock=false -->',
        '---',
        '',
        '<!-- section:identified_risks -->',
        '## Risks',
        '',
        '<!-- table:risks -->',
        '| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |',
        '|---------|-------------|-------------|--------|---------------------|-------|',
        '| R1 | Minor risk | Low | Low | Monitor | Team |',
        '',
        '<!-- section_lock:identified_risks lock=false -->',
        '---',
        '',
        '<!-- section:approval_record -->',
        '## Approval Record',
        '',
        '<!-- table:approval_record -->',
        '| Field | Value |',
        '|-------|-------|',
        '| Current Status | Draft |',
        '| Recommended By | Pending |',
        '| Recommendation Date | Pending |',
        '',
        '---',
    ]


def test_check_section_table_for_open_questions():
    """Test checking section tables for open questions."""
    print("Test 1: Check section table for open questions...")
    
    # Test with open questions
    lines = create_test_document_with_open_questions()
    has_open, count = check_section_table_for_open_questions(lines, "problem_statement")
    
    if has_open and count == 1:
        print("  ✓ Correctly detected 1 open question")
    else:
        print(f"  ✗ Expected 1 open question, got {count}")
        return False
    
    # Test with no open questions (assumptions section has no table)
    has_open, count = check_section_table_for_open_questions(lines, "assumptions")
    
    if not has_open and count == 0:
        print("  ✓ Correctly detected no open questions (no table)")
    else:
        print(f"  ✗ Expected 0 open questions, got {count}")
        return False
    
    return True


def test_check_risks_table():
    """Test checking risks table for non-low risks."""
    print("\nTest 2: Check risks table for non-low risks...")
    
    # Test with high risks
    lines = create_test_document_with_high_risks()
    has_non_low, risks = check_risks_table_for_non_low_risks(lines)
    
    if has_non_low and len(risks) == 1:
        print(f"  ✓ Correctly detected 1 non-low risk: {risks[0][:50]}...")
    else:
        print(f"  ✗ Expected 1 non-low risk, got {len(risks)}")
        return False
    
    # Test with all low risks
    lines = create_test_document_passing()
    has_non_low, risks = check_risks_table_for_non_low_risks(lines)
    
    if not has_non_low and len(risks) == 0:
        print("  ✓ Correctly detected all risks are low/low")
    else:
        print(f"  ✗ Expected 0 non-low risks, got {len(risks)}")
        return False
    
    return True


def test_section_locking():
    """Test section locking functionality."""
    print("\nTest 3: Test section locking...")
    
    lines = create_test_document_passing()
    
    # Check initial lock status
    spans = find_sections(lines)
    problem_span = get_section_span(spans, "problem_statement")
    
    if not section_is_locked(lines, problem_span):
        print("  ✓ Section starts unlocked")
    else:
        print("  ✗ Section should start unlocked")
        return False
    
    # Lock the section
    lines = set_section_lock(lines, "problem_statement", lock=True)
    
    # Re-get the span (line numbers may have shifted)
    spans = find_sections(lines)
    problem_span = get_section_span(spans, "problem_statement")
    
    if section_is_locked(lines, problem_span):
        print("  ✓ Section successfully locked")
    else:
        print("  ✗ Section should be locked")
        return False
    
    # Unlock the section
    lines = set_section_lock(lines, "problem_statement", lock=False)
    
    # Re-get the span
    spans = find_sections(lines)
    problem_span = get_section_span(spans, "problem_statement")
    
    if not section_is_locked(lines, problem_span):
        print("  ✓ Section successfully unlocked")
    else:
        print("  ✗ Section should be unlocked")
        return False
    
    return True


def test_approval_record_update():
    """Test updating approval record table."""
    print("\nTest 4: Test approval record update...")
    
    lines = create_test_document_passing()
    
    # Update approval record
    updated_lines = update_approval_record_table(lines, reviewer="Test Reviewer", status="Approved")
    
    # Check if the table was updated
    found_reviewer = False
    found_status = False
    
    for line in updated_lines:
        if "| Recommended By |" in line and "Test Reviewer" in line:
            found_reviewer = True
        if "| Current Status |" in line and "Approved" in line:
            found_status = True
    
    if found_reviewer and found_status:
        print("  ✓ Approval record successfully updated")
        return True
    else:
        print(f"  ✗ Approval record not updated correctly (reviewer: {found_reviewer}, status: {found_status})")
        return False


def test_full_coherence_gate_integration():
    """Test full coherence gate workflow."""
    print("\nTest 5: Test full coherence gate integration...")
    
    from requirements_automation.review_gate_handler import ReviewGateHandler
    from requirements_automation.models import HandlerConfig
    
    # Mock LLM client
    class MockLLM:
        def perform_review(self, gate_id, doc_type, section_contents, llm_profile, validation_rules):
            # Return empty issues (LLM check passed)
            return {
                "issues": [],
                "patches": [],
                "summary": "Review passed"
            }
    
    # Test with passing document
    lines = create_test_document_passing()
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    config = HandlerConfig(
        section_id="review_gate:coherence_check",
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
    
    result = handler.execute_review("review_gate:coherence_check", config)
    
    if result.passed:
        print("  ✓ Gate passed for valid document")
        
        # Check if sections were locked
        spans = find_sections(handler.lines)
        problem_span = get_section_span(spans, "problem_statement")
        assumptions_span = get_section_span(spans, "assumptions")
        
        if section_is_locked(handler.lines, problem_span) and section_is_locked(handler.lines, assumptions_span):
            print("  ✓ Prior sections locked after gate pass")
        else:
            print("  ✗ Prior sections should be locked")
            return False
    else:
        print(f"  ✗ Gate should have passed, issues: {result.issues}")
        return False
    
    # Test with document that has open questions
    lines = create_test_document_with_open_questions()
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    result = handler.execute_review("review_gate:coherence_check", config)
    
    if not result.passed:
        print("  ✓ Gate blocked for document with open questions")
        if any("open question" in issue.description.lower() for issue in result.issues):
            print("  ✓ Correct blocker reason provided")
        else:
            print(f"  ✗ Expected blocker about open questions, got: {result.issues}")
            return False
    else:
        print("  ✗ Gate should have been blocked")
        return False
    
    # Test with document that has high risks
    lines = create_test_document_with_high_risks()
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    result = handler.execute_review("review_gate:coherence_check", config)
    
    if not result.passed:
        print("  ✓ Gate blocked for document with high risks")
        if any("risk" in issue.description.lower() for issue in result.issues):
            print("  ✓ Correct blocker reason provided")
        else:
            print(f"  ✗ Expected blocker about risks, got: {result.issues}")
            return False
    else:
        print("  ✗ Gate should have been blocked")
        return False
    
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Coherence Check Gate Tests")
    print("=" * 70)
    
    tests = [
        test_check_section_table_for_open_questions,
        test_check_risks_table,
        test_section_locking,
        test_approval_record_update,
        test_full_coherence_gate_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
