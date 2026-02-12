#!/usr/bin/env python3
"""
Test for interfaces_integrations subsection preservation during LLM drafting.

This test validates Issue 3f acceptance criteria:
- After LLM drafting, external_systems and data_exchange table subsections exist with content
- No subsection markers are lost
- Tables are preserved (not replaced with prose)
- Questions & Issues table is preserved

The required subsections are:
1. external_systems (table format)
2. data_exchange (table format)
3. questions_issues (metadata, should be preserved)
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


def test_interfaces_integrations_table_subsections():
    """Test that external_systems and data_exchange table subsections are preserved."""
    print("\nTest 1: Table subsections preserved in interfaces_integrations")
    print("=" * 70)

    # Create a document with interfaces_integrations section matching template structure
    test_doc = """<!-- section:interfaces_integrations -->
## 8. Interfaces and Integrations

<!-- subsection:external_systems -->
### External Systems

<!-- table:external_systems -->

| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|
| <!-- PLACEHOLDER --> | - | - | - |

<!-- subsection:data_exchange -->
### Data Exchange

<!-- table:data_exchange -->

| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|
| <!-- PLACEHOLDER --> | - | - | - |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:interfaces_integrations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:interfaces_integrations lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Get the section span
    spans = find_sections(lines)
    span = get_section_span(spans, "interfaces_integrations")
    
    if not span:
        print("  ✗ FAILED: Could not find interfaces_integrations section!")
        return False
    
    # Verify initial subsection count
    initial_subs = find_subsections_within(lines, span)
    print(f"  Initial subsections found: {len(initial_subs)}")
    for sub in initial_subs:
        print(f"    - {sub.subsection_id}")
    
    # Simulate LLM drafting by replacing section preamble
    new_body = """This section describes the external systems and data exchange requirements."""

    # Replace the section body (preamble only)
    updated_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="interfaces_integrations",
        new_body=new_body,
    )
    
    # Update spans after replacement
    updated_spans = find_sections(updated_lines)
    updated_span = get_section_span(updated_spans, "interfaces_integrations")
    
    if not updated_span:
        print("  ✗ FAILED: Section disappeared after replacement!")
        return False
    
    # Verify all subsections are still present
    updated_subs = find_subsections_within(updated_lines, updated_span)
    print(f"  After replacement subsections found: {len(updated_subs)}")
    for sub in updated_subs:
        print(f"    - {sub.subsection_id}")
    
    # Check for required subsections
    required_subsections = {"external_systems", "data_exchange", "questions_issues"}
    found_subsections = {sub.subsection_id for sub in updated_subs}
    
    if required_subsections <= found_subsections:
        print(f"  ✓ All required subsections preserved: {required_subsections}")
    else:
        missing = required_subsections - found_subsections
        print(f"  ✗ FAILED: Missing subsections: {missing}")
        return False
    
    # Verify table markers are preserved
    updated_text = "\n".join(updated_lines)
    if "<!-- table:external_systems -->" in updated_text:
        print("  ✓ external_systems table marker preserved")
    else:
        print("  ✗ FAILED: external_systems table marker missing!")
        return False
    
    if "<!-- table:data_exchange -->" in updated_text:
        print("  ✓ data_exchange table marker preserved")
    else:
        print("  ✗ FAILED: data_exchange table marker missing!")
        return False
    
    if "<!-- table:interfaces_integrations_questions -->" in updated_text:
        print("  ✓ Questions & Issues table marker preserved")
    else:
        print("  ✗ FAILED: Questions & Issues table marker missing!")
        return False
    
    # Verify table content is preserved
    if "| System | Purpose | Interface Type | Dependencies |" in updated_text:
        print("  ✓ external_systems table header preserved")
    else:
        print("  ✗ FAILED: external_systems table header missing!")
        return False
    
    if "| Integration Point | Data Flow | Format | Frequency |" in updated_text:
        print("  ✓ data_exchange table header preserved")
    else:
        print("  ✗ FAILED: data_exchange table header missing!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


def test_interfaces_integrations_with_content():
    """Test preservation when subsections already have content."""
    print("\nTest 2: Subsection preservation with existing table content")
    print("=" * 70)

    test_doc = """<!-- section:interfaces_integrations -->
## 8. Interfaces and Integrations

This section is partially complete.

<!-- subsection:external_systems -->
### External Systems

<!-- table:external_systems -->

| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|
| GitHub API | Repository management | REST API | Valid API token |
| LLM Provider | Content generation | REST API | API key, rate limits |

<!-- subsection:data_exchange -->
### Data Exchange

<!-- table:data_exchange -->

| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|
| LLM API | Bidirectional | JSON | Per request |
| File System | Read/Write | Markdown | Continuous |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:interfaces_integrations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:interfaces_integrations lock=false -->
---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "interfaces_integrations")
    
    if not span:
        print("  ✗ FAILED: Could not find section!")
        return False
    
    # Replace preamble
    new_body = "The system integrates with multiple external systems for various functionalities."
    
    updated_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="interfaces_integrations",
        new_body=new_body,
    )
    
    # Verify tables with content are preserved
    updated_text = "\n".join(updated_lines)
    
    if "GitHub API" in updated_text and "LLM Provider" in updated_text:
        print("  ✓ external_systems table content preserved")
    else:
        print("  ✗ FAILED: external_systems table content lost!")
        return False
    
    if "LLM API" in updated_text and "File System" in updated_text:
        print("  ✓ data_exchange table content preserved")
    else:
        print("  ✗ FAILED: data_exchange table content lost!")
        return False
    
    # Verify preamble was replaced
    if "The system integrates with multiple external systems" in updated_text:
        print("  ✓ Preamble successfully replaced")
    else:
        print("  ✗ FAILED: Preamble not replaced!")
        return False
    
    if "This section is partially complete" not in updated_text:
        print("  ✓ Old preamble removed")
    else:
        print("  ✗ FAILED: Old preamble still present!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


def test_interfaces_integrations_empty_preamble():
    """Test when preamble is empty but subsections have content."""
    print("\nTest 3: Empty preamble with subsections containing table content")
    print("=" * 70)

    test_doc = """<!-- section:interfaces_integrations -->
## 8. Interfaces and Integrations

<!-- subsection:external_systems -->
### External Systems

<!-- table:external_systems -->

| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|
| Database | Data storage | SQL | Connection string |

<!-- subsection:data_exchange -->
### Data Exchange

<!-- table:data_exchange -->

| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|
| API Gateway | Inbound | JSON | Real-time |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:interfaces_integrations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:interfaces_integrations lock=false -->
---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "interfaces_integrations")
    
    if not span:
        print("  ✗ FAILED: Could not find section!")
        return False
    
    # Add content to empty preamble
    new_body = "Integration architecture overview."
    
    updated_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="interfaces_integrations",
        new_body=new_body,
    )
    
    updated_text = "\n".join(updated_lines)
    
    # Verify new preamble is present
    if "Integration architecture overview" in updated_text:
        print("  ✓ New preamble added")
    else:
        print("  ✗ FAILED: New preamble not added!")
        return False
    
    # Verify subsection content preserved
    if "Database" in updated_text and "API Gateway" in updated_text:
        print("  ✓ All subsection table content preserved")
    else:
        print("  ✗ FAILED: Subsection content lost!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("INTERFACES_INTEGRATIONS SUBSECTION PRESERVATION TESTS")
    print("=" * 70)
    
    results = []
    results.append(test_interfaces_integrations_table_subsections())
    results.append(test_interfaces_integrations_with_content())
    results.append(test_interfaces_integrations_empty_preamble())
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
