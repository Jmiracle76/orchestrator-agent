#!/usr/bin/env python3
"""
Integration test for requirements section drafting with table routing.

This test simulates the full flow of drafting a requirements section where
LLM output contains table content that needs to be routed to subsections.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.table_routing import route_table_content_to_subsections
from requirements_automation.editing import replace_block_body_preserving_markers
from requirements_automation.parsing import find_sections, get_section_span
from requirements_automation.utils_io import split_lines


def _extract_section_between_markers(doc: str, start_marker: str, end_marker: str) -> str:
    """Extract content between two markers in a document.
    
    Args:
        doc: Full document text
        start_marker: Starting marker (e.g., "<!-- subsection:functional_requirements -->")
        end_marker: Ending marker (e.g., "<!-- subsection:non_functional_requirements -->")
        
    Returns:
        Content between the two markers
    """
    start_idx = doc.find(start_marker)
    end_idx = doc.find(end_marker)
    
    if start_idx == -1:
        return ""
    if end_idx == -1:
        return doc[start_idx:]
    
    return doc[start_idx:end_idx]


def test_full_requirements_section_draft():
    """Test full flow of drafting requirements section with table routing."""
    print("\nTest: Full Requirements Section Draft with Table Routing")
    print("=" * 70)
    
    # Simulate a requirements section from the template
    template_doc = """<!-- section:requirements -->
## 7. Requirements
<!-- PLACEHOLDER -->

<!-- subsection:functional_requirements -->
### Functional Requirements

<!-- table:functional_requirements -->
| Req ID | Description | Priority | Source | Acceptance Criteria |
|--------|-------------|----------|--------|---------------------|
| <!-- PLACEHOLDER --> | - | - | - | - |

<!-- subsection:non_functional_requirements -->
### Non-Functional Requirements

<!-- table:non_functional_requirements -->
| Req ID | Category | Description | Priority | Measurement Criteria | Acceptance Criteria |
|--------|----------|-------------|----------|---------------------|---------------------|
| <!-- PLACEHOLDER --> | - | - | - | - | - |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:requirements_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:requirements lock=false -->
---
"""
    
    # Simulate LLM output with table content
    llm_output = """
The system requirements are categorized into functional and non-functional requirements.

### Functional Requirements

| REQ-F001 | User Authentication | High | Stakeholder Interviews | User can log in with username and password |
| REQ-F002 | Data Export | Medium | Business Analysis | System exports data to CSV format |
| REQ-F003 | Search Functionality | High | User Research | Users can search records by keyword |

### Non Functional Requirements

| REQ-NF001 | Performance | Response time under 200ms | High | Load testing at peak usage | 95th percentile < 200ms |
| REQ-NF002 | Security | All data encrypted at rest | Critical | Security audit | AES-256 encryption verified |
| REQ-NF003 | Availability | 99.9% uptime | High | System monitoring | < 8.76 hours downtime per year |
"""
    
    # Parse document
    lines = split_lines(template_doc)
    spans = find_sections(lines)
    section_span = get_section_span(spans, "requirements")
    
    assert section_span is not None, "Requirements section should be found"
    
    # Simulate subsection structure (what LLM would receive in prompt)
    subsection_structure = [
        {"id": "functional_requirements", "type": "table"},
        {"id": "non_functional_requirements", "type": "table"},
        {"id": "questions_issues", "type": "table"},
    ]
    
    # Step 1: Route table content to subsections
    lines_after_routing, preamble = route_table_content_to_subsections(
        lines, section_span, llm_output, subsection_structure
    )
    
    # Step 2: Update preamble with non-table content
    # Find the preamble end (before first subsection)
    from requirements_automation.parsing import find_subsections_within
    subs = find_subsections_within(lines_after_routing, section_span)
    preamble_end = subs[0].start_line if subs else section_span.end_line
    
    lines_final = replace_block_body_preserving_markers(
        lines_after_routing,
        section_span.start_line,
        preamble_end,
        section_id="requirements",
        new_body=preamble,
    )
    
    result_doc = "\n".join(lines_final)
    
    # Verify functional requirements were inserted
    print("\n  Checking functional requirements...")
    assert "REQ-F001" in result_doc, "Should contain REQ-F001"
    assert "REQ-F002" in result_doc, "Should contain REQ-F002"
    assert "REQ-F003" in result_doc, "Should contain REQ-F003"
    assert "User Authentication" in result_doc, "Should contain functional req description"
    print("    ✓ All 3 functional requirements present")
    
    # Verify non-functional requirements were inserted
    print("  Checking non-functional requirements...")
    assert "REQ-NF001" in result_doc, "Should contain REQ-NF001"
    assert "REQ-NF002" in result_doc, "Should contain REQ-NF002"
    assert "REQ-NF003" in result_doc, "Should contain REQ-NF003"
    assert "Performance" in result_doc, "Should contain non-functional req category"
    assert "Security" in result_doc, "Should contain Security category"
    assert "Availability" in result_doc, "Should contain Availability category"
    print("    ✓ All 3 non-functional requirements present")
    
    # Verify preamble contains only prose
    print("  Checking preamble...")
    assert "categorized into functional" in result_doc.lower(), "Preamble prose should be present"
    print("    ✓ Preamble prose present")
    
    # Verify placeholders are gone or replaced
    print("  Checking placeholders...")
    # There might still be placeholders in the questions table, but not in the requirements tables
    functional_section = _extract_section_between_markers(
        result_doc, 
        "<!-- subsection:functional_requirements -->", 
        "<!-- subsection:non_functional_requirements -->"
    )
    non_functional_section = _extract_section_between_markers(
        result_doc,
        "<!-- subsection:non_functional_requirements -->",
        "<!-- subsection:questions_issues -->"
    )
    
    # Check that functional requirements section has real data
    assert "REQ-F001" in functional_section, "Functional requirements section should have real data"
    assert "REQ-NF001" in non_functional_section, "Non-functional requirements section should have real data"
    print("    ✓ Real data present in both table subsections")
    
    # Verify structure is preserved
    print("  Checking structure preservation...")
    assert "<!-- subsection:functional_requirements -->" in result_doc, "Subsection marker preserved"
    assert "<!-- subsection:non_functional_requirements -->" in result_doc, "Subsection marker preserved"
    assert "<!-- subsection:questions_issues -->" in result_doc, "Subsection marker preserved"
    assert "<!-- table:functional_requirements -->" in result_doc, "Table marker preserved"
    assert "<!-- table:non_functional_requirements -->" in result_doc, "Table marker preserved"
    assert "<!-- section_lock:requirements lock=false -->" in result_doc, "Lock marker preserved"
    print("    ✓ All markers preserved")
    
    print("\n  ✓ Full integration test passed!")
    return True


def test_draft_with_only_prose():
    """Test drafting when LLM returns only prose (no tables)."""
    print("\nTest: Draft with Only Prose (No Tables)")
    print("=" * 70)
    
    template_doc = """<!-- section:requirements -->
## 7. Requirements
<!-- PLACEHOLDER -->

<!-- subsection:functional_requirements -->
### Functional Requirements

<!-- table:functional_requirements -->
| Req ID | Description | Priority | Source | Acceptance Criteria |
|--------|-------------|----------|--------|---------------------|
| <!-- PLACEHOLDER --> | - | - | - | - |

---
"""
    
    llm_output = """
The requirements will be gathered through stakeholder interviews.
A detailed analysis is needed before specific requirements can be defined.
"""
    
    lines = split_lines(template_doc)
    spans = find_sections(lines)
    section_span = get_section_span(spans, "requirements")
    
    subsection_structure = [
        {"id": "functional_requirements", "type": "table"},
    ]
    
    lines_after_routing, preamble = route_table_content_to_subsections(
        lines, section_span, llm_output, subsection_structure
    )
    
    # When no tables, all content should go to preamble
    assert "stakeholder interviews" in preamble.lower(), "Preamble should contain all prose"
    assert "detailed analysis" in preamble.lower(), "Preamble should contain all prose"
    
    print("  ✓ All prose content routed to preamble")
    print("  ✓ Test passed!")
    return True


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 70)
    print("REQUIREMENTS SECTION INTEGRATION TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_full_requirements_section_draft,
        test_draft_with_only_prose,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"  ✗ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ Test error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
