#!/usr/bin/env python3
"""
Test for stakeholders_users table preservation during LLM drafting.

This test validates Issue 3b acceptance criteria:
- Primary stakeholders table preserved with data rows after drafting
- End users table preserved with data rows after drafting
- Questions & Issues table preserved

The two required subsections with tables are:
1. primary_stakeholders (table with: Stakeholder, Role, Interest/Need, Contact columns)
2. end_users (table with: User Type, Characteristics, Needs, Use Cases columns)
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


def test_stakeholders_users_tables_preserved():
    """Test that primary_stakeholders and end_users tables are preserved."""
    print("\nTest 1: stakeholders_users tables preserved during drafting")
    print("=" * 70)

    # Create a document with stakeholders_users section matching template structure
    test_doc = """<!-- section:stakeholders_users -->
## 4. Stakeholders and Users

<!-- PLACEHOLDER -->

<!-- subsection:primary_stakeholders -->
### Primary Stakeholders

<!-- table:primary_stakeholders -->
| Stakeholder | Role | Interest/Need | Contact |
|-------------|------|---------------|---------|
| John Smith | Product Owner | Delivery success | john@example.com |
| Jane Doe | Tech Lead | Technical quality | jane@example.com |

<!-- subsection:end_users -->
### End Users

<!-- table:end_users -->
| User Type | Characteristics | Needs | Use Cases |
|-----------|----------------|-------|-----------|
| Admin | Technical skills | System configuration | Setup and manage users |
| End User | Basic skills | Easy interface | Daily operations |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:stakeholders_users_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| stakeholders_users-Q1 | Have all key stakeholder groups been identified? | 2024-01-01 | | Open |
| stakeholders_users-Q2 | What are the communication preferences for each stakeholder? | 2024-01-01 | | Open |

<!-- section_lock:stakeholders_users lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Get the section span
    spans = find_sections(lines)
    span = get_section_span(spans, "stakeholders_users")
    
    if not span:
        print("  ✗ FAILED: Could not find stakeholders_users section!")
        return False
    
    # Verify initial subsection count
    initial_subs = find_subsections_within(lines, span)
    print(f"  Initial subsections found: {len(initial_subs)}")
    for sub in initial_subs:
        print(f"    - {sub.subsection_id}")
    
    # Simulate LLM drafting by replacing section preamble
    new_body = """The stakeholders and users for this project have been identified and their needs analyzed.
    
This section documents the primary stakeholders and end users who will be affected by or interact with the system."""
    
    result_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="stakeholders_users",
        new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    print("\n  Verification:")
    
    # Verify subsection markers are preserved
    required_subsections = [
        "primary_stakeholders",
        "end_users",
        "questions_issues"
    ]
    
    for sub_id in required_subsections:
        marker = f"<!-- subsection:{sub_id} -->"
        if marker not in result_doc:
            print(f"  ✗ FAILED: {sub_id} subsection marker was removed!")
            return False
        print(f"  ✓ {sub_id} subsection marker preserved")
    
    # Verify table markers are preserved
    table_markers = [
        "<!-- table:primary_stakeholders -->",
        "<!-- table:end_users -->",
        "<!-- table:stakeholders_users_questions -->"
    ]
    
    for marker in table_markers:
        if marker not in result_doc:
            print(f"  ✗ FAILED: Table marker '{marker}' was removed!")
            return False
        print(f"  ✓ Table marker preserved: {marker}")
    
    # Verify section headers are preserved
    section_headers = [
        "### Primary Stakeholders",
        "### End Users",
        "### Questions & Issues"
    ]
    
    for header in section_headers:
        if header not in result_doc:
            print(f"  ✗ FAILED: Header '{header}' was removed!")
            return False
    print("  ✓ All subsection headers preserved")
    
    # Verify table content (data rows) are preserved
    primary_stakeholders_data = ["John Smith", "Product Owner", "john@example.com"]
    end_users_data = ["Admin", "Technical skills", "Setup and manage users"]
    
    for data in primary_stakeholders_data:
        if data not in result_doc:
            print(f"  ✗ FAILED: primary_stakeholders data '{data}' was removed!")
            return False
    print("  ✓ primary_stakeholders table data preserved")
    
    for data in end_users_data:
        if data not in result_doc:
            print(f"  ✗ FAILED: end_users data '{data}' was removed!")
            return False
    print("  ✓ end_users table data preserved")
    
    # Verify new content was added
    if "stakeholders and users for this project have been identified" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added")
    
    # Verify PLACEHOLDER was removed from section preamble (but not from tables)
    # The section preamble PLACEHOLDER should be replaced by new_body
    lines_result = result_doc.split('\n')
    found_section = False
    found_subsection = False
    placeholder_in_preamble = False
    
    for line in lines_result:
        if '<!-- section:stakeholders_users -->' in line:
            found_section = True
            continue
        if found_section and not found_subsection:
            if '<!-- subsection:' in line:
                found_subsection = True
            elif '<!-- PLACEHOLDER -->' in line and 'table:' not in lines_result[max(0, lines_result.index(line)-2):lines_result.index(line)]:
                placeholder_in_preamble = True
    
    if placeholder_in_preamble:
        print("  ✗ FAILED: PLACEHOLDER in section preamble was not removed!")
        return False
    print("  ✓ PLACEHOLDER in section preamble was removed")
    
    print("\n  ✓ Test passed")
    return True


def test_stakeholders_users_llm_prompt_guidance():
    """Test that the subsection structure is correctly built for stakeholders_users."""
    print("\nTest 2: stakeholders_users subsection structure for LLM prompts")
    print("=" * 70)
    
    from requirements_automation.handler_registry import HandlerRegistry
    from requirements_automation.runner_integration import _build_subsection_structure
    
    # Load handler config
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    handler_config = registry.get_handler_config("requirements", "stakeholders_users")
    
    # Verify subsections flag is set
    if not handler_config.subsections:
        print("  ✗ FAILED: handler_config.subsections is False!")
        return False
    print("  ✓ handler_config.subsections is True")
    
    # Create a test document with stakeholders_users section
    test_doc = """<!-- section:stakeholders_users -->
## 4. Stakeholders and Users

<!-- subsection:primary_stakeholders -->
### Primary Stakeholders

<!-- table:primary_stakeholders -->
| Stakeholder | Role | Interest/Need | Contact |
|-------------|------|---------------|---------|

<!-- subsection:end_users -->
### End Users

<!-- table:end_users -->
| User Type | Characteristics | Needs | Use Cases |
|-----------|----------------|-------|-----------|

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- section_lock:stakeholders_users lock=false -->
"""
    
    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "stakeholders_users")
    
    # Build subsection structure
    structure = _build_subsection_structure(lines, span, handler_config)
    
    if not structure:
        print("  ✗ FAILED: subsection structure is None!")
        return False
    
    print(f"  ✓ subsection structure built: {len(structure)} subsections")
    
    # Verify primary_stakeholders is marked as table type
    primary_stakeholders = next((s for s in structure if s["id"] == "primary_stakeholders"), None)
    if not primary_stakeholders:
        print("  ✗ FAILED: primary_stakeholders not in structure!")
        return False
    
    if primary_stakeholders["type"] != "table":
        print(f"  ✗ FAILED: primary_stakeholders type is '{primary_stakeholders['type']}', expected 'table'!")
        return False
    print("  ✓ primary_stakeholders type is 'table'")
    
    # Verify end_users is marked as table type
    end_users = next((s for s in structure if s["id"] == "end_users"), None)
    if not end_users:
        print("  ✗ FAILED: end_users not in structure!")
        return False
    
    if end_users["type"] != "table":
        print(f"  ✗ FAILED: end_users type is '{end_users['type']}', expected 'table'!")
        return False
    print("  ✓ end_users type is 'table'")
    
    # Verify questions_issues is NOT in the structure (it's metadata, not content)
    questions_issues = next((s for s in structure if s["id"] == "questions_issues"), None)
    if questions_issues:
        print("  ✗ FAILED: questions_issues should not be in structure (it's metadata)!")
        return False
    print("  ✓ questions_issues correctly excluded from structure")
    
    print("\n  ✓ Test passed")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("STAKEHOLDERS_USERS TABLE PRESERVATION TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_stakeholders_users_tables_preserved,
        test_stakeholders_users_llm_prompt_guidance,
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
            print(f"  ✗ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"  {failed} test(s) failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
