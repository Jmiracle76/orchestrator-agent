#!/usr/bin/env python3
"""
Unit tests for subsection preservation in replace_block_body_preserving_markers().

This test validates that the function never overwrites subsection markers,
their headers, or their table content when replacing section body content.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.editing import replace_block_body_preserving_markers
from requirements_automation.utils_io import split_lines


def test_preserve_single_subsection():
    """Test that a single subsection is preserved during replacement."""
    print("\nTest 1: Preserve single subsection")
    print("=" * 70)

    # Create a test document with a section containing one subsection
    test_doc = """<!-- section:requirements -->
## Requirements

Some preamble content here.

<!-- subsection:open_questions -->
### Open Questions

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | Test question? | 2024-01-01 | - | requirements | Open |

<!-- section_lock:requirements lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Replace the section body with new content
    new_body = "Updated requirements content.\n\nThis is the new preamble."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="requirements", new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify subsection marker is preserved
    if "<!-- subsection:open_questions -->" not in result_doc:
        print("  ✗ FAILED: subsection marker was removed!")
        return False
    print("  ✓ Subsection marker preserved")
    
    # Verify table marker is preserved
    if "<!-- table:open_questions -->" not in result_doc:
        print("  ✗ FAILED: table marker was removed!")
        return False
    print("  ✓ Table marker preserved")
    
    # Verify table content is preserved
    if "Q-001" not in result_doc or "Test question?" not in result_doc:
        print("  ✗ FAILED: table content was removed!")
        return False
    print("  ✓ Table content preserved")
    
    # Verify new content was added
    if "Updated requirements content" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added")
    
    # Verify old preamble was replaced
    if "Some preamble content here" in result_doc:
        print("  ✗ FAILED: old preamble was not replaced!")
        return False
    print("  ✓ Old preamble was replaced")
    
    print("  ✓ Test passed")
    return True


def test_preserve_multiple_subsections():
    """Test that multiple subsections are all preserved during replacement."""
    print("\nTest 2: Preserve multiple subsections")
    print("=" * 70)

    # Create a test document with multiple subsections
    test_doc = """<!-- section:risks_open_issues -->
## 10. Risks and Open Issues

Initial risk content here.

<!-- subsection:identified_risks -->
### Identified Risks

Risk 1: Something bad
Risk 2: Another thing

<!-- subsection:open_questions -->
### Open Questions

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | What about this? | 2024-01-01 | - | risks_open_issues | Open |

<!-- section_lock:risks_open_issues lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Replace the section body with new content
    new_body = "Updated risks and issues overview."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="risks_open_issues", new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify both subsections are preserved
    if "<!-- subsection:identified_risks -->" not in result_doc:
        print("  ✗ FAILED: identified_risks subsection marker was removed!")
        return False
    print("  ✓ identified_risks subsection marker preserved")
    
    if "<!-- subsection:open_questions -->" not in result_doc:
        print("  ✗ FAILED: open_questions subsection marker was removed!")
        return False
    print("  ✓ open_questions subsection marker preserved")
    
    # Verify subsection content is preserved
    if "Risk 1: Something bad" not in result_doc:
        print("  ✗ FAILED: identified_risks content was removed!")
        return False
    print("  ✓ identified_risks content preserved")
    
    if "Q-001" not in result_doc:
        print("  ✗ FAILED: open_questions table was removed!")
        return False
    print("  ✓ open_questions table preserved")
    
    # Verify new preamble was added
    if "Updated risks and issues overview" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added")
    
    # Verify old preamble was replaced
    if "Initial risk content here" in result_doc:
        print("  ✗ FAILED: old preamble was not replaced!")
        return False
    print("  ✓ Old preamble was replaced")
    
    print("  ✓ Test passed")
    return True


def test_no_subsections():
    """Test that sections without subsections work normally."""
    print("\nTest 3: Section without subsections")
    print("=" * 70)

    # Create a test document without subsections
    test_doc = """<!-- section:problem_statement -->
## 2. Problem Statement

Old problem statement content goes here.

Multiple paragraphs of old content.

<!-- section_lock:problem_statement lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # Replace the section body with new content
    new_body = "New problem statement.\n\nThis is completely different."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="problem_statement", new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify new content was added
    if "New problem statement" not in result_doc or "completely different" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added")
    
    # Verify old content was replaced
    if "Old problem statement content" in result_doc:
        print("  ✗ FAILED: old content was not replaced!")
        return False
    print("  ✓ Old content was replaced")
    
    # Verify structure markers are preserved
    if "<!-- section:problem_statement -->" not in result_doc:
        print("  ✗ FAILED: section marker was removed!")
        return False
    print("  ✓ Section marker preserved")
    
    if "<!-- section_lock:problem_statement lock=false -->" not in result_doc:
        print("  ✗ FAILED: lock marker was removed!")
        return False
    print("  ✓ Lock marker preserved")
    
    print("  ✓ Test passed")
    return True


def test_preserve_version_history_subsection():
    """Test that version_history subsection with table is preserved."""
    print("\nTest 4: Preserve version_history subsection with table")
    print("=" * 70)

    # Create a test document with version_history subsection
    test_doc = """<!-- section:metadata -->
## 1. Document Metadata

Document preamble here.

<!-- subsection:version_history -->
### Version History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-01-01 | Alice | Initial version |
| 1.1 | 2024-02-01 | Bob | Updates |

---
"""

    lines = split_lines(test_doc)
    
    # Replace the section body with new content
    new_body = "Updated metadata preamble."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="metadata", new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify subsection is preserved
    if "<!-- subsection:version_history -->" not in result_doc:
        print("  ✗ FAILED: version_history subsection marker was removed!")
        return False
    print("  ✓ version_history subsection marker preserved")
    
    # Verify table header is preserved
    if "### Version History" not in result_doc:
        print("  ✗ FAILED: version_history heading was removed!")
        return False
    print("  ✓ version_history heading preserved")
    
    # Verify table content is preserved
    if "Alice" not in result_doc or "Bob" not in result_doc:
        print("  ✗ FAILED: version_history table content was removed!")
        return False
    print("  ✓ version_history table content preserved")
    
    # Verify new preamble was added
    if "Updated metadata preamble" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added")
    
    print("  ✓ Test passed")
    return True


def test_subsection_at_start():
    """Test that subsection immediately after heading is preserved."""
    print("\nTest 5: Subsection immediately after section heading")
    print("=" * 70)

    # Create a test document where subsection comes right after heading
    test_doc = """<!-- section:approval_record -->
## 13. Approval Record

<!-- subsection:approvals -->
### Approvals

<!-- table:approvals -->
| Field | Value |
|-------|-------|
| Status | Draft |

---
"""

    lines = split_lines(test_doc)
    
    # Replace the section body with new content (should not replace anything since subsection is immediate)
    new_body = "This should go before the subsection."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="approval_record", new_body=new_body
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify subsection is preserved
    if "<!-- subsection:approvals -->" not in result_doc:
        print("  ✗ FAILED: subsection marker was removed!")
        return False
    print("  ✓ Subsection marker preserved")
    
    # Verify table is preserved
    if "| Field | Value |" not in result_doc or "| Status | Draft |" not in result_doc:
        print("  ✗ FAILED: table content was removed!")
        return False
    print("  ✓ Table content preserved")
    
    # Verify new content was added before the subsection
    if "This should go before the subsection" not in result_doc:
        print("  ✗ FAILED: new content was not added!")
        return False
    print("  ✓ New content was added")
    
    # Verify order is correct: new content should come before subsection
    new_content_pos = result_doc.find("This should go before")
    subsection_pos = result_doc.find("<!-- subsection:approvals -->")
    if new_content_pos >= subsection_pos:
        print("  ✗ FAILED: new content is not before subsection!")
        return False
    print("  ✓ Content order is correct")
    
    print("  ✓ Test passed")
    return True


def main():
    """Run all tests."""
    print("Subsection Preservation Test Suite")
    print("=" * 70)

    results = []

    try:
        results.append(test_preserve_single_subsection())
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_preserve_multiple_subsections())
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_no_subsections())
    except Exception as e:
        print(f"✗ Test 3 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_preserve_version_history_subsection())
    except Exception as e:
        print(f"✗ Test 4 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_subsection_at_start())
    except Exception as e:
        print(f"✗ Test 5 failed with exception: {e}")
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
