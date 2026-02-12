#!/usr/bin/env python3
"""
Test for placeholder detection logic.

This test suite validates that placeholder detection correctly distinguishes
between main section preambles and subsections:
1. Tests has_placeholder() only checks preamble, not subsections
2. Tests section_is_blank() only checks preamble, not subsections
3. Verifies sections with filled preambles but empty subsections are not flagged
4. Tests edge cases: multiple subsections, no subsections, all empty, all filled
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.models import SectionSpan
from requirements_automation.parsing import (
    has_placeholder,
    section_is_blank,
    get_section_preamble_end_line,
    section_preamble_text,
)
from requirements_automation.utils_io import split_lines


def test_preamble_filled_subsection_empty():
    """
    Test: Section with filled preamble but empty subsection should NOT be flagged.
    
    This is the primary use case from the issue - sections like goals_objectives
    that have populated main content but placeholder subsections.
    """
    print("\nTest 1: Filled preamble, empty subsection")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

This section describes the high-level goals and objectives.
We want to achieve X, Y, and Z outcomes.

<!-- subsection:business_goals -->
### Business Goals
<!-- PLACEHOLDER -->

<!-- subsection:technical_objectives -->
### Technical Objectives
<!-- PLACEHOLDER -->

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="goals_objectives", start_line=0, end_line=len(lines))
    
    # Should NOT have placeholder in preamble
    assert not has_placeholder(span, lines), \
        "has_placeholder should return False for filled preamble with empty subsections"
    print("  ✓ has_placeholder correctly returns False")
    
    # Should NOT be blank
    assert not section_is_blank(lines, span), \
        "section_is_blank should return False for filled preamble with empty subsections"
    print("  ✓ section_is_blank correctly returns False")
    
    # Verify preamble extraction
    preamble = section_preamble_text(lines, span)
    assert "high-level goals" in preamble, \
        "Preamble should contain main content"
    assert "<!-- subsection:business_goals -->" not in preamble, \
        "Preamble should not contain subsection markers"
    print("  ✓ Preamble extraction correct")
    
    print("  ✓ Test passed")
    return True


def test_preamble_empty_subsection_filled():
    """
    Test: Section with empty preamble but filled subsections SHOULD be flagged.
    
    This validates that we're not over-correcting - if the main section
    body is empty, it should still be considered incomplete.
    """
    print("\nTest 2: Empty preamble, filled subsections")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

<!-- PLACEHOLDER -->

<!-- subsection:business_goals -->
### Business Goals
We want to increase revenue by 50%.

<!-- subsection:technical_objectives -->
### Technical Objectives
Reduce latency to under 100ms.

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="goals_objectives", start_line=0, end_line=len(lines))
    
    # SHOULD have placeholder in preamble
    assert has_placeholder(span, lines), \
        "has_placeholder should return True for empty preamble"
    print("  ✓ has_placeholder correctly returns True")
    
    # SHOULD be blank
    assert section_is_blank(lines, span), \
        "section_is_blank should return True for empty preamble"
    print("  ✓ section_is_blank correctly returns True")
    
    print("  ✓ Test passed")
    return True


def test_no_subsections_with_placeholder():
    """
    Test: Section with no subsections and placeholder SHOULD be flagged.
    """
    print("\nTest 3: No subsections, has placeholder")
    print("=" * 70)

    test_doc = """<!-- section:problem_statement -->
## 2. Problem Statement

<!-- PLACEHOLDER -->

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="problem_statement", start_line=0, end_line=len(lines))
    
    # SHOULD have placeholder
    assert has_placeholder(span, lines), \
        "has_placeholder should return True for section with placeholder and no subsections"
    print("  ✓ has_placeholder correctly returns True")
    
    assert section_is_blank(lines, span), \
        "section_is_blank should return True"
    print("  ✓ section_is_blank correctly returns True")
    
    print("  ✓ Test passed")
    return True


def test_no_subsections_filled():
    """
    Test: Section with no subsections and content should NOT be flagged.
    """
    print("\nTest 4: No subsections, has content")
    print("=" * 70)

    test_doc = """<!-- section:problem_statement -->
## 2. Problem Statement

The current system has performance issues that need to be addressed.
Users are experiencing slow response times.

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="problem_statement", start_line=0, end_line=len(lines))
    
    # Should NOT have placeholder
    assert not has_placeholder(span, lines), \
        "has_placeholder should return False for filled section without subsections"
    print("  ✓ has_placeholder correctly returns False")
    
    assert not section_is_blank(lines, span), \
        "section_is_blank should return False"
    print("  ✓ section_is_blank correctly returns False")
    
    print("  ✓ Test passed")
    return True


def test_all_filled():
    """
    Test: Section with filled preamble and filled subsections should NOT be flagged.
    """
    print("\nTest 5: All filled (preamble + subsections)")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

This section describes our strategic goals.

<!-- subsection:business_goals -->
### Business Goals
Increase market share.

<!-- subsection:technical_objectives -->
### Technical Objectives
Improve system reliability.

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="goals_objectives", start_line=0, end_line=len(lines))
    
    # Should NOT have placeholder
    assert not has_placeholder(span, lines), \
        "has_placeholder should return False when everything is filled"
    print("  ✓ has_placeholder correctly returns False")
    
    assert not section_is_blank(lines, span), \
        "section_is_blank should return False"
    print("  ✓ section_is_blank correctly returns False")
    
    print("  ✓ Test passed")
    return True


def test_multiple_subsections_mixed():
    """
    Test: Section with filled preamble and mix of filled/empty subsections.
    """
    print("\nTest 6: Multiple subsections with mixed states")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

Main section content is complete.

<!-- subsection:business_goals -->
### Business Goals
Business objectives are defined here.

<!-- subsection:technical_objectives -->
### Technical Objectives
<!-- PLACEHOLDER -->

<!-- subsection:success_metrics -->
### Success Metrics
Metrics are defined.

<!-- subsection:timeline -->
### Timeline
<!-- PLACEHOLDER -->

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="goals_objectives", start_line=0, end_line=len(lines))
    
    # Should NOT have placeholder (preamble is filled)
    assert not has_placeholder(span, lines), \
        "has_placeholder should return False when preamble is filled (regardless of subsections)"
    print("  ✓ has_placeholder correctly returns False")
    
    assert not section_is_blank(lines, span), \
        "section_is_blank should return False"
    print("  ✓ section_is_blank correctly returns False")
    
    print("  ✓ Test passed")
    return True


def test_preamble_end_line_calculation():
    """
    Test: Verify preamble end line calculation is correct.
    """
    print("\nTest 7: Preamble end line calculation")
    print("=" * 70)

    test_doc = """<!-- section:test_section -->
## Test Section

Line 0
Line 1
Line 2

<!-- subsection:sub1 -->
### Subsection 1
Content here

---
"""

    lines = split_lines(test_doc)
    span = SectionSpan(section_id="test_section", start_line=0, end_line=len(lines))
    
    # Get preamble end line
    preamble_end = get_section_preamble_end_line(lines, span)
    
    # Find the actual subsection line
    subsection_line = None
    for i, line in enumerate(lines):
        if "<!-- subsection:sub1 -->" in line:
            subsection_line = i
            break
    
    assert subsection_line is not None, "Subsection marker should exist"
    assert preamble_end == subsection_line, \
        f"Preamble end line should be {subsection_line}, got {preamble_end}"
    print(f"  ✓ Preamble end line correctly calculated as {preamble_end}")
    
    # Test with no subsections
    test_doc_no_subs = """<!-- section:test_section -->
## Test Section

Content without subsections

---
"""
    lines_no_subs = split_lines(test_doc_no_subs)
    span_no_subs = SectionSpan(section_id="test_section", start_line=0, end_line=len(lines_no_subs))
    preamble_end_no_subs = get_section_preamble_end_line(lines_no_subs, span_no_subs)
    
    assert preamble_end_no_subs == len(lines_no_subs), \
        "Preamble end line should equal span end when no subsections"
    print(f"  ✓ Preamble end line for section without subsections: {preamble_end_no_subs}")
    
    print("  ✓ Test passed")
    return True


def run_all_tests():
    """Run all placeholder detection tests."""
    print("\n" + "=" * 70)
    print("PLACEHOLDER DETECTION TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_preamble_filled_subsection_empty,
        test_preamble_empty_subsection_filled,
        test_no_subsections_with_placeholder,
        test_no_subsections_filled,
        test_all_filled,
        test_multiple_subsections_mixed,
        test_preamble_end_line_calculation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
