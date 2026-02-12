#!/usr/bin/env python3
"""
Test for data_considerations subsection preservation during LLM drafting.

This test validates Issue 3f acceptance criteria:
- After LLM drafting, data_requirements, privacy_security, and data_retention subsections exist
- No subsection markers are lost
- Bullet list structure is preserved within subsections
- Questions & Issues table is preserved

The required subsections are:
1. data_requirements (bullet list format)
2. privacy_security (bullet list format)
3. data_retention (bullet list format)
4. questions_issues (metadata, should be preserved)
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


def test_data_considerations_all_subsections():
    """Test that all three required subsections are preserved in data_considerations."""
    print("\nTest 1: All subsections preserved in data_considerations")
    print("=" * 70)

    # Create a document with data_considerations section matching template structure
    test_doc = """<!-- section:data_considerations -->
## 9. Data Considerations

<!-- subsection:data_requirements -->
### Data Requirements
<!-- PLACEHOLDER -->
- [Data entity 1] 
- [Data entity 2] 

<!-- subsection:privacy_security -->
### Privacy & Security
<!-- PLACEHOLDER -->
- [Privacy consideration] 
- [Security consideration] 

<!-- subsection:data_retention -->
### Data Retention
<!-- PLACEHOLDER -->
- [Retention policy 1] 
- [Retention policy 2] 

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:data_considerations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:data_considerations lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Get the section span
    spans = find_sections(lines)
    span = get_section_span(spans, "data_considerations")
    
    if not span:
        print("  ✗ FAILED: Could not find data_considerations section!")
        return False
    
    # Verify initial subsection count
    initial_subs = find_subsections_within(lines, span)
    print(f"  Initial subsections found: {len(initial_subs)}")
    for sub in initial_subs:
        print(f"    - {sub.subsection_id}")
    
    # Simulate LLM drafting by replacing section preamble
    new_body = """This section outlines data handling requirements, privacy and security considerations, and retention policies."""

    # Replace the section body (preamble only)
    updated_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="data_considerations",
        new_body=new_body,
    )
    
    # Update spans after replacement
    updated_spans = find_sections(updated_lines)
    updated_span = get_section_span(updated_spans, "data_considerations")
    
    if not updated_span:
        print("  ✗ FAILED: Section disappeared after replacement!")
        return False
    
    # Verify all subsections are still present
    updated_subs = find_subsections_within(updated_lines, updated_span)
    print(f"  After replacement subsections found: {len(updated_subs)}")
    for sub in updated_subs:
        print(f"    - {sub.subsection_id}")
    
    # Check for required subsections
    required_subsections = {"data_requirements", "privacy_security", "data_retention", "questions_issues"}
    found_subsections = {sub.subsection_id for sub in updated_subs}
    
    if required_subsections <= found_subsections:
        print(f"  ✓ All required subsections preserved: {required_subsections}")
    else:
        missing = required_subsections - found_subsections
        print(f"  ✗ FAILED: Missing subsections: {missing}")
        return False
    
    # Verify subsection markers are preserved
    updated_text = "\n".join(updated_lines)
    if "<!-- subsection:data_requirements -->" in updated_text:
        print("  ✓ data_requirements subsection marker preserved")
    else:
        print("  ✗ FAILED: data_requirements subsection marker missing!")
        return False
    
    if "<!-- subsection:privacy_security -->" in updated_text:
        print("  ✓ privacy_security subsection marker preserved")
    else:
        print("  ✗ FAILED: privacy_security subsection marker missing!")
        return False
    
    if "<!-- subsection:data_retention -->" in updated_text:
        print("  ✓ data_retention subsection marker preserved")
    else:
        print("  ✗ FAILED: data_retention subsection marker missing!")
        return False
    
    if "<!-- table:data_considerations_questions -->" in updated_text:
        print("  ✓ Questions & Issues table marker preserved")
    else:
        print("  ✗ FAILED: Questions & Issues table marker missing!")
        return False
    
    # Verify placeholder bullet lists are preserved
    if "- [Data entity 1]" in updated_text:
        print("  ✓ data_requirements bullet list preserved")
    else:
        print("  ✗ FAILED: data_requirements bullet list missing!")
        return False
    
    if "- [Privacy consideration]" in updated_text:
        print("  ✓ privacy_security bullet list preserved")
    else:
        print("  ✗ FAILED: privacy_security bullet list missing!")
        return False
    
    if "- [Retention policy 1]" in updated_text:
        print("  ✓ data_retention bullet list preserved")
    else:
        print("  ✗ FAILED: data_retention bullet list missing!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


def test_data_considerations_with_content():
    """Test preservation when subsections already have content."""
    print("\nTest 2: Subsection preservation with existing bullet list content")
    print("=" * 70)

    test_doc = """<!-- section:data_considerations -->
## 9. Data Considerations

This section is partially complete.

<!-- subsection:data_requirements -->
### Data Requirements
- User profile data (name, email, preferences)
- Transaction history logs
- System configuration metadata

<!-- subsection:privacy_security -->
### Privacy & Security
- All personal data must be encrypted at rest using AES-256
- Access control via role-based permissions
- Audit logs for all data access events

<!-- subsection:data_retention -->
### Data Retention
- User data retained for 7 years per regulatory requirements
- System logs retained for 90 days
- Deleted data purged within 30 days

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:data_considerations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:data_considerations lock=false -->
---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "data_considerations")
    
    if not span:
        print("  ✗ FAILED: Could not find section!")
        return False
    
    # Replace preamble
    new_body = "The following subsections define data handling requirements and policies."
    
    updated_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="data_considerations",
        new_body=new_body,
    )
    
    # Verify bullet list content is preserved
    updated_text = "\n".join(updated_lines)
    
    if "User profile data" in updated_text and "Transaction history logs" in updated_text:
        print("  ✓ data_requirements content preserved")
    else:
        print("  ✗ FAILED: data_requirements content lost!")
        return False
    
    if "encrypted at rest" in updated_text and "role-based permissions" in updated_text:
        print("  ✓ privacy_security content preserved")
    else:
        print("  ✗ FAILED: privacy_security content lost!")
        return False
    
    if "7 years per regulatory" in updated_text and "System logs retained" in updated_text:
        print("  ✓ data_retention content preserved")
    else:
        print("  ✗ FAILED: data_retention content lost!")
        return False
    
    # Verify preamble was replaced
    if "The following subsections define data handling" in updated_text:
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


def test_data_considerations_empty_preamble():
    """Test when preamble is empty but subsections have content."""
    print("\nTest 3: Empty preamble with subsections containing bullet lists")
    print("=" * 70)

    test_doc = """<!-- section:data_considerations -->
## 9. Data Considerations

<!-- subsection:data_requirements -->
### Data Requirements
- Customer contact information
- Order history

<!-- subsection:privacy_security -->
### Privacy & Security
- GDPR compliance required
- Data encryption in transit and at rest

<!-- subsection:data_retention -->
### Data Retention
- Active data retained indefinitely
- Archived data purged after 5 years

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:data_considerations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:data_considerations lock=false -->
---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "data_considerations")
    
    if not span:
        print("  ✗ FAILED: Could not find section!")
        return False
    
    # Add content to empty preamble
    new_body = "Data management policies and requirements."
    
    updated_lines = replace_block_body_preserving_markers(
        lines,
        span.start_line,
        span.end_line,
        section_id="data_considerations",
        new_body=new_body,
    )
    
    updated_text = "\n".join(updated_lines)
    
    # Verify new preamble is present
    if "Data management policies and requirements" in updated_text:
        print("  ✓ New preamble added")
    else:
        print("  ✗ FAILED: New preamble not added!")
        return False
    
    # Verify subsection content preserved
    if "Customer contact information" in updated_text and "GDPR compliance" in updated_text and "Active data retained" in updated_text:
        print("  ✓ All subsection bullet list content preserved")
    else:
        print("  ✗ FAILED: Subsection content lost!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("DATA_CONSIDERATIONS SUBSECTION PRESERVATION TESTS")
    print("=" * 70)
    
    results = []
    results.append(test_data_considerations_all_subsections())
    results.append(test_data_considerations_with_content())
    results.append(test_data_considerations_empty_preamble())
    
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
