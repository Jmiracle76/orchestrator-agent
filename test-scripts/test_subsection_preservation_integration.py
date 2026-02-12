#!/usr/bin/env python3
"""
Integration test demonstrating subsection preservation during content replacement.

This test validates the real-world scenario where sections with subsections
are updated through the workflow, ensuring all subsection content is preserved.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.editing import replace_block_body_preserving_markers
from requirements_automation.parsing import find_sections, find_subsections_within, get_section_span
from requirements_automation.utils_io import split_lines


def test_real_world_section_with_multiple_subsections():
    """Test replacing content in a real-world section structure with multiple subsections."""
    print("\nIntegration Test: Real-world section with multiple subsections")
    print("=" * 70)

    # Create a realistic document structure (like risks_open_issues section)
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
risks_open_issues
-->

# Test Requirements Document

<!-- section:problem_statement -->
## 2. Problem Statement

The problem is well-defined here.

<!-- section_lock:problem_statement lock=false -->
---

<!-- section:risks_open_issues -->
## 10. Risks and Open Issues

<!-- PLACEHOLDER -->

<!-- subsection:identified_risks -->
### Identified Risks

1. Risk A: Description A
2. Risk B: Description B

<!-- subsection:questions_issues -->
### Questions and Issues

<!-- table:risks_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| risks-Q1 | What about security? | 2024-01-15 | We'll use TLS | risks_open_issues | Resolved |
| risks-Q2 | Performance concerns? | 2024-01-20 | - | risks_open_issues | Open |

<!-- section_lock:risks_open_issues lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    print("  Initial document structure:")
    spans = find_sections(lines)
    for sp in spans:
        print(f"    Section: {sp.section_id} (lines {sp.start_line}-{sp.end_line})")
        subs = find_subsections_within(lines, sp)
        for sub in subs:
            print(f"      Subsection: {sub.subsection_id} (lines {sub.start_line}-{sub.end_line})")
    
    # Get the risks_open_issues section
    risk_span = get_section_span(spans, "risks_open_issues")
    
    # Replace the section body (simulating LLM draft generation)
    new_body = """### Overview

The following risks and open issues have been identified for this project.

#### Critical Risks

- **Data Loss**: Risk of data corruption during migration
- **Performance Degradation**: System may slow under high load
- **Security Vulnerabilities**: Authentication needs review"""

    result_lines = replace_block_body_preserving_markers(
        lines,
        risk_span.start_line,
        risk_span.end_line,
        section_id="risks_open_issues",
        new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify all subsections are preserved
    print("\n  Verification:")
    
    # Check identified_risks subsection
    if "<!-- subsection:identified_risks -->" not in result_doc:
        print("  ✗ FAILED: identified_risks subsection marker was removed!")
        return False
    print("  ✓ identified_risks subsection marker preserved")
    
    if "Risk A: Description A" not in result_doc:
        print("  ✗ FAILED: identified_risks content was removed!")
        return False
    print("  ✓ identified_risks content preserved")
    
    # Check questions_issues subsection
    if "<!-- subsection:questions_issues -->" not in result_doc:
        print("  ✗ FAILED: questions_issues subsection marker was removed!")
        return False
    print("  ✓ questions_issues subsection marker preserved")
    
    # Check table marker
    if "<!-- table:risks_questions -->" not in result_doc:
        print("  ✗ FAILED: table marker was removed!")
        return False
    print("  ✓ Table marker preserved")
    
    # Check table content
    if "risks-Q1" not in result_doc or "What about security?" not in result_doc:
        print("  ✗ FAILED: table content was removed!")
        return False
    print("  ✓ Table content preserved (both resolved and open questions)")
    
    # Verify new content was added
    if "Data Loss" not in result_doc or "Performance Degradation" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added to preamble")
    
    # Verify PLACEHOLDER was removed
    if "<!-- PLACEHOLDER -->" in result_doc:
        print("  ✗ FAILED: PLACEHOLDER was not removed!")
        return False
    print("  ✓ PLACEHOLDER was removed")
    
    # Verify structure is valid by parsing again
    result_spans = find_sections(result_lines)
    risk_span_after = get_section_span(result_spans, "risks_open_issues")
    if not risk_span_after:
        print("  ✗ FAILED: section structure corrupted!")
        return False
    
    subs_after = find_subsections_within(result_lines, risk_span_after)
    if len(subs_after) != 2:
        print(f"  ✗ FAILED: expected 2 subsections, found {len(subs_after)}")
        return False
    print(f"  ✓ Section structure valid (2 subsections preserved)")
    
    print("\n  ✓ Integration test PASSED")
    return True


def test_workflow_simulation():
    """Simulate a workflow step that updates a section with subsections."""
    print("\nIntegration Test: Workflow simulation (constraints section)")
    print("=" * 70)

    # Create a constraints section with subsections (common pattern)
    test_doc = """<!-- section:constraints -->
## 5. Constraints

<!-- PLACEHOLDER -->

<!-- subsection:technical_constraints -->
### Technical Constraints

- Must use Python 3.9+
- Must integrate with existing PostgreSQL database

<!-- subsection:resource_constraints -->
### Resource Constraints

- Budget: $50,000
- Timeline: 6 months

<!-- subsection:operational_constraints -->
### Operational Constraints

- Must maintain 99.9% uptime
- Zero downtime deployments required

<!-- section_lock:constraints lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Get the constraints section
    spans = find_sections(lines)
    span = get_section_span(spans, "constraints")
    
    # Draft new preamble content (avoid headers that would be sanitized out)
    new_body = """The following constraints must be considered during design and implementation.

This project operates under several key constraints that shape feasible solution approaches and define acceptable implementation boundaries."""

    result_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="constraints",
        new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    print("\n  Verification:")
    
    # Verify all three subsections preserved
    subsection_ids = ["technical_constraints", "resource_constraints", "operational_constraints"]
    for sub_id in subsection_ids:
        if f"<!-- subsection:{sub_id} -->" not in result_doc:
            print(f"  ✗ FAILED: {sub_id} subsection was removed!")
            return False
        print(f"  ✓ {sub_id} subsection preserved")
    
    # Verify specific content from each subsection
    checks = [
        ("Python 3.9+", "technical_constraints"),
        ("$50,000", "resource_constraints"),
        ("99.9% uptime", "operational_constraints"),
    ]
    
    for content, sub in checks:
        if content not in result_doc:
            print(f"  ✗ FAILED: {sub} content was removed!")
            return False
    print("  ✓ All subsection content preserved")
    
    # Verify new preamble
    if "define acceptable implementation boundaries" not in result_doc:
        print("  ✗ FAILED: new preamble was not added!")
        return False
    print("  ✓ New preamble was added")
    
    # Verify PLACEHOLDER removed
    if "<!-- PLACEHOLDER -->" in result_doc:
        print("  ✗ FAILED: PLACEHOLDER still present!")
        return False
    print("  ✓ PLACEHOLDER was removed")
    
    print("\n  ✓ Integration test PASSED")
    return True


def main():
    """Run all integration tests."""
    print("Subsection Preservation Integration Tests")
    print("=" * 70)

    results = []

    try:
        results.append(test_real_world_section_with_multiple_subsections())
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_workflow_simulation())
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} integration tests passed")
    print("=" * 70)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
