#!/usr/bin/env python3
"""
Test for goals_objectives subsection preservation during LLM drafting.

This test validates Issue 3a acceptance criteria:
- After LLM drafting, all four subsections exist with content
- No subsection markers are lost
- Questions & Issues table is preserved

The four required subsections are:
1. objective_statement
2. primary_goals
3. secondary_goals
4. non_goals
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.editing import replace_block_body_preserving_markers
from requirements_automation.parsing import (
    find_sections,
    find_subsections_within,
    get_section_span,
)
from requirements_automation.utils_io import split_lines


def test_goals_objectives_all_four_subsections():
    """Test that all four required subsections are preserved in goals_objectives."""
    print("\nTest 1: All four subsections preserved in goals_objectives")
    print("=" * 70)

    # Create a document with goals_objectives section matching template structure
    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

<!-- PLACEHOLDER -->

<!-- subsection:objective_statement -->
### Objective Statement
<!-- PLACEHOLDER -->
[Clear, concise statement of the project objective]

<!-- subsection:primary_goals -->
### Primary Goals
<!-- PLACEHOLDER -->
1. [Primary goal 1]
2. [Primary goal 2]

<!-- subsection:secondary_goals -->
### Secondary Goals
<!-- PLACEHOLDER -->
1. [Secondary goal 1]
2. [Secondary goal 2]

<!-- subsection:non_goals -->
### Non-Goals
<!-- PLACEHOLDER -->
1. [Non-goal 1]
2. [Non-goal 2]

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:goals_objectives_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| goals_objectives-Q1 | What are the measurable success indicators for each goal? | 2024-01-01 | | Open |
| goals_objectives-Q2 | How do these goals align with organizational priorities? | 2024-01-01 | | Open |
| goals_objectives-Q3 | What are the dependencies between primary and secondary goals? | 2024-01-01 | | Open |

<!-- section_lock:goals_objectives lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Get the section span
    spans = find_sections(lines)
    span = get_section_span(spans, "goals_objectives")
    
    if not span:
        print("  ✗ FAILED: Could not find goals_objectives section!")
        return False
    
    # Verify initial subsection count
    initial_subs = find_subsections_within(lines, span)
    print(f"  Initial subsections found: {len(initial_subs)}")
    for sub in initial_subs:
        print(f"    - {sub.subsection_id}")
    
    # Simulate LLM drafting by replacing section preamble
    new_body = """This project aims to modernize our data processing infrastructure.

The following goals and objectives guide the project scope and deliverables."""
    
    result_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="goals_objectives",
        new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    print("\n  Verification:")
    
    # Verify all four required subsections are preserved
    required_subsections = [
        "objective_statement",
        "primary_goals", 
        "secondary_goals",
        "non_goals"
    ]
    
    for sub_id in required_subsections:
        marker = f"<!-- subsection:{sub_id} -->"
        if marker not in result_doc:
            print(f"  ✗ FAILED: {sub_id} subsection marker was removed!")
            return False
        print(f"  ✓ {sub_id} subsection marker preserved")
    
    # Verify questions_issues subsection is also preserved
    if "<!-- subsection:questions_issues -->" not in result_doc:
        print("  ✗ FAILED: questions_issues subsection marker was removed!")
        return False
    print("  ✓ questions_issues subsection marker preserved")
    
    # Verify section headers are preserved
    section_headers = [
        "### Objective Statement",
        "### Primary Goals",
        "### Secondary Goals",
        "### Non-Goals",
        "### Questions & Issues"
    ]
    
    for header in section_headers:
        if header not in result_doc:
            print(f"  ✗ FAILED: Header '{header}' was removed!")
            return False
    print("  ✓ All subsection headers preserved")
    
    # Verify table marker is preserved
    if "<!-- table:goals_objectives_questions -->" not in result_doc:
        print("  ✗ FAILED: Questions table marker was removed!")
        return False
    print("  ✓ Questions table marker preserved")
    
    # Verify table content is preserved
    if "goals_objectives-Q1" not in result_doc:
        print("  ✗ FAILED: Questions table content was removed!")
        return False
    print("  ✓ Questions table content preserved")
    
    # Verify new preamble was added
    if "modernize our data processing infrastructure" not in result_doc:
        print("  ✗ FAILED: New preamble was not added!")
        return False
    print("  ✓ New preamble content was added")
    
    # Verify PLACEHOLDER in preamble was removed
    lines_before_first_subsection = []
    for line in result_lines:
        if "<!-- subsection:" in line:
            break
        lines_before_first_subsection.append(line)
    
    preamble = "\n".join(lines_before_first_subsection)
    if "<!-- PLACEHOLDER -->" in preamble:
        print("  ✗ FAILED: PLACEHOLDER in preamble was not removed!")
        return False
    print("  ✓ PLACEHOLDER in preamble was removed")
    
    # Verify structure is still valid by parsing again
    result_spans = find_sections(result_lines)
    result_span = get_section_span(result_spans, "goals_objectives")
    
    if not result_span:
        print("  ✗ FAILED: Section structure corrupted!")
        return False
    
    final_subs = find_subsections_within(result_lines, result_span)
    print(f"\n  Final subsections found: {len(final_subs)}")
    for sub in final_subs:
        print(f"    - {sub.subsection_id}")
    
    if len(final_subs) != 5:  # 4 content subsections + questions_issues
        print(f"  ✗ FAILED: Expected 5 subsections, found {len(final_subs)}")
        return False
    
    print("  ✓ All 5 subsections preserved (4 content + questions_issues)")
    print("\n  ✓ Test PASSED")
    return True


def test_goals_objectives_with_content_replacement():
    """Test subsection preservation when preamble has substantial content."""
    print("\nTest 2: Subsection preservation with content in preamble")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

This is the old preamble content that should be replaced.

It has multiple paragraphs of text here.

And even more content that needs to be updated.

<!-- subsection:objective_statement -->
### Objective Statement
Deliver a scalable data platform

<!-- subsection:primary_goals -->
### Primary Goals
1. Improve data processing speed by 50%
2. Reduce infrastructure costs

<!-- subsection:secondary_goals -->
### Secondary Goals
1. Enhance data quality monitoring
2. Implement automated testing

<!-- subsection:non_goals -->
### Non-Goals
1. Not replacing existing databases
2. Not building custom hardware

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:goals_objectives_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| goals_objectives-Q1 | What are the measurable success indicators for each goal? | 2024-01-01 | We'll track latency metrics | Resolved |

<!-- section_lock:goals_objectives lock=false -->
---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "goals_objectives")
    
    # Replace with new preamble content
    new_body = """**Project Mission:** Transform our analytics capabilities.

This initiative focuses on delivering real-time insights and predictive analytics."""
    
    result_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="goals_objectives",
        new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    print("\n  Verification:")
    
    # Verify all subsections still present
    subsections = [
        "objective_statement",
        "primary_goals",
        "secondary_goals", 
        "non_goals",
        "questions_issues"
    ]
    
    for sub_id in subsections:
        if f"<!-- subsection:{sub_id} -->" not in result_doc:
            print(f"  ✗ FAILED: {sub_id} was removed!")
            return False
    print("  ✓ All subsections preserved")
    
    # Verify subsection content is intact
    checks = [
        ("Deliver a scalable data platform", "objective_statement"),
        ("Improve data processing speed by 50%", "primary_goals"),
        ("Enhance data quality monitoring", "secondary_goals"),
        ("Not replacing existing databases", "non_goals"),
        ("We'll track latency metrics", "questions_issues table"),
    ]
    
    for content, location in checks:
        if content not in result_doc:
            print(f"  ✗ FAILED: {location} content was removed!")
            print(f"    Missing: {content}")
            return False
    print("  ✓ All subsection content preserved")
    
    # Verify new preamble
    if "Transform our analytics capabilities" not in result_doc:
        print("  ✗ FAILED: New preamble not added!")
        return False
    print("  ✓ New preamble added")
    
    # Verify old preamble removed
    if "old preamble content that should be replaced" in result_doc:
        print("  ✗ FAILED: Old preamble not removed!")
        return False
    print("  ✓ Old preamble removed")
    
    print("\n  ✓ Test PASSED")
    return True


def test_goals_objectives_empty_preamble():
    """Test when preamble is just PLACEHOLDER and subsections have content."""
    print("\nTest 3: Empty preamble with subsections containing content")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

<!-- PLACEHOLDER -->

<!-- subsection:objective_statement -->
### Objective Statement
Build a next-generation analytics platform

<!-- subsection:primary_goals -->
### Primary Goals
- Goal 1: Achieve real-time processing
- Goal 2: Support 10M+ events/sec

<!-- subsection:secondary_goals -->
### Secondary Goals
- Goal A: Improve developer experience
- Goal B: Enhance monitoring

<!-- subsection:non_goals -->
### Non-Goals
- Not supporting legacy formats
- Not building mobile apps

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:goals_objectives_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:goals_objectives lock=false -->
---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "goals_objectives")
    
    new_body = "This project delivers cutting-edge analytics infrastructure."
    
    result_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="goals_objectives",
        new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    print("\n  Verification:")
    
    # Check all subsections exist
    required = ["objective_statement", "primary_goals", "secondary_goals", "non_goals"]
    for sub in required:
        if f"<!-- subsection:{sub} -->" not in result_doc:
            print(f"  ✗ FAILED: {sub} missing!")
            return False
    print("  ✓ All 4 required subsections present")
    
    # Check content preservation
    content_checks = [
        "Build a next-generation analytics platform",
        "Achieve real-time processing",
        "Improve developer experience",
        "Not supporting legacy formats",
    ]
    
    for content in content_checks:
        if content not in result_doc:
            print(f"  ✗ FAILED: Content missing: {content}")
            return False
    print("  ✓ All subsection content preserved")
    
    # Check new preamble
    if "cutting-edge analytics infrastructure" not in result_doc:
        print("  ✗ FAILED: New preamble missing!")
        return False
    print("  ✓ New preamble added")
    
    print("\n  ✓ Test PASSED")
    return True


def main():
    """Run all tests."""
    print("Goals & Objectives Subsection Preservation Tests")
    print("=" * 70)
    print("\nValidating Issue 3a Acceptance Criteria:")
    print("- After LLM drafting, all four subsections exist with content")
    print("- No subsection markers are lost")
    print("- Questions & Issues table is preserved")
    print("=" * 70)

    results = []

    try:
        results.append(test_goals_objectives_all_four_subsections())
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_goals_objectives_with_content_replacement())
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_goals_objectives_empty_preamble())
    except Exception as e:
        print(f"✗ Test 3 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)
    
    if all(results):
        print("\n✓ All acceptance criteria validated!")
        print("  - All four subsections preserved ✓")
        print("  - No subsection markers lost ✓")
        print("  - Questions & Issues table preserved ✓")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
