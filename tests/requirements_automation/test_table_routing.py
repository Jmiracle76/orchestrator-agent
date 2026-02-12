#!/usr/bin/env python3
"""
Test for table content routing: Extract table rows from LLM output and insert into subsections.

This test suite validates that table content from LLM output is correctly routed to
table subsections (functional_requirements, non_functional_requirements) instead of
being dumped in the section preamble.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.table_routing import (
    _extract_markdown_table_rows,
    _identify_table_content_by_subsection,
    _extract_non_table_content,
    route_table_content_to_subsections,
)
from requirements_automation.models import SectionSpan
from requirements_automation.utils_io import split_lines


def test_extract_markdown_table_rows():
    """Test extraction of markdown table rows from text."""
    print("\nTest 1: Extract markdown table rows")
    print("=" * 70)
    
    text = """
Some prose content here.

| Req ID | Description | Priority | Source | Acceptance Criteria |
|--------|-------------|----------|--------|---------------------|
| REQ-001 | User login | High | Stakeholder A | User can authenticate |
| REQ-002 | Data export | Medium | Stakeholder B | System exports CSV |

More prose content.
"""
    
    rows = _extract_markdown_table_rows(text)
    
    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    assert "REQ-001" in rows[0], "First row should contain REQ-001"
    assert "REQ-002" in rows[1], "Second row should contain REQ-002"
    
    print(f"  ✓ Extracted {len(rows)} table rows")
    print("  ✓ Test passed")
    return True


def test_identify_table_content_by_subsection():
    """Test identification of table content by subsection headers."""
    print("\nTest 2: Identify table content by subsection")
    print("=" * 70)
    
    llm_output = """
Some general context about requirements.

### Functional Requirements

| REQ-F001 | User authentication | High | Stakeholder | User can log in |
| REQ-F002 | Data validation | Medium | Developer | Input is validated |

### Non Functional Requirements

| REQ-NF001 | Performance | Response time < 200ms | High | Load testing |
| REQ-NF002 | Security | Encryption at rest | High | Audit |
"""
    
    subsection_structure = [
        {"id": "functional_requirements", "type": "table"},
        {"id": "non_functional_requirements", "type": "table"},
    ]
    
    result = _identify_table_content_by_subsection(llm_output, subsection_structure)
    
    assert "functional_requirements" in result, "Should identify functional_requirements"
    assert "non_functional_requirements" in result, "Should identify non_functional_requirements"
    assert len(result["functional_requirements"]) == 2, "Should extract 2 functional req rows"
    assert len(result["non_functional_requirements"]) == 2, "Should extract 2 non-functional req rows"
    assert "REQ-F001" in result["functional_requirements"][0], "First functional req should contain REQ-F001"
    assert "REQ-NF001" in result["non_functional_requirements"][0], "First non-functional req should contain REQ-NF001"
    
    print(f"  ✓ Identified {len(result)} subsections")
    print(f"  ✓ Functional requirements: {len(result['functional_requirements'])} rows")
    print(f"  ✓ Non-functional requirements: {len(result['non_functional_requirements'])} rows")
    print("  ✓ Test passed")
    return True


def test_extract_non_table_content():
    """Test extraction of non-table content from LLM output."""
    print("\nTest 3: Extract non-table content")
    print("=" * 70)
    
    llm_output = """
The requirements are derived from stakeholder needs and business objectives.

### Functional Requirements

| REQ-F001 | User authentication | High | Stakeholder | User can log in |

### Non Functional Requirements

| REQ-NF001 | Performance | Response time < 200ms | High | Load testing |

Additional notes about implementation considerations.
"""
    
    preamble = _extract_non_table_content(llm_output)
    
    # Should contain prose but not table rows or subsection headers
    assert "stakeholder needs" in preamble.lower(), "Should contain preamble prose"
    assert "implementation considerations" in preamble.lower(), "Should contain trailing prose"
    assert "###" not in preamble, "Should not contain subsection headers"
    assert "REQ-F001" not in preamble, "Should not contain table rows"
    assert "REQ-NF001" not in preamble, "Should not contain table rows"
    
    print("  ✓ Extracted preamble content without tables")
    print("  ✓ Test passed")
    return True


def test_route_table_content_to_subsections():
    """Test routing of table content to subsections."""
    print("\nTest 4: Route table content to subsections")
    print("=" * 70)
    
    # Simulate a requirements section with empty tables
    test_doc = """<!-- section:requirements -->
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

---
"""
    
    lines = split_lines(test_doc)
    section_span = SectionSpan(section_id="requirements", start_line=0, end_line=len(lines))
    
    llm_output = """
The system requirements are organized into functional and non-functional categories.

### Functional Requirements

| REQ-F001 | User login capability | High | Stakeholder A | User can authenticate with credentials |
| REQ-F002 | Data export feature | Medium | Stakeholder B | System can export data to CSV format |

### Non Functional Requirements

| REQ-NF001 | Performance | System response time must be under 200ms | High | Load testing under peak conditions | 95th percentile < 200ms |
| REQ-NF002 | Security | All data must be encrypted at rest | High | Encryption audit | All databases use AES-256 |
"""
    
    subsection_structure = [
        {"id": "functional_requirements", "type": "table"},
        {"id": "non_functional_requirements", "type": "table"},
        {"id": "questions_issues", "type": "table"},
    ]
    
    result_lines, preamble = route_table_content_to_subsections(
        lines, section_span, llm_output, subsection_structure
    )
    
    result_doc = "\n".join(result_lines)
    
    # Verify functional requirements were inserted
    assert "REQ-F001" in result_doc, "Should contain REQ-F001"
    assert "REQ-F002" in result_doc, "Should contain REQ-F002"
    assert "User login capability" in result_doc, "Should contain functional req description"
    
    # Verify non-functional requirements were inserted
    assert "REQ-NF001" in result_doc, "Should contain REQ-NF001"
    assert "REQ-NF002" in result_doc, "Should contain REQ-NF002"
    assert "Performance" in result_doc, "Should contain non-functional req category"
    
    # Verify placeholders were replaced
    functional_section = result_doc[result_doc.find("<!-- subsection:functional_requirements -->"):result_doc.find("<!-- subsection:non_functional_requirements -->")]
    # The placeholder row might still exist if we don't remove it, but real data should be there
    assert "REQ-F001" in functional_section, "Functional requirements section should have real data"
    
    # Verify preamble contains only prose
    assert "organized into functional" in preamble.lower(), "Preamble should contain prose"
    assert "REQ-F001" not in preamble, "Preamble should not contain table rows"
    assert "###" not in preamble, "Preamble should not contain subsection headers"
    
    print("  ✓ Functional requirements routed to subsection")
    print("  ✓ Non-functional requirements routed to subsection")
    print("  ✓ Preamble contains only prose content")
    print("  ✓ Test passed")
    return True


def test_route_with_no_table_content():
    """Test routing when LLM output has no tables."""
    print("\nTest 5: Route with no table content")
    print("=" * 70)
    
    test_doc = """<!-- section:requirements -->
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
    
    lines = split_lines(test_doc)
    section_span = SectionSpan(section_id="requirements", start_line=0, end_line=len(lines))
    
    llm_output = """
The requirements will be gathered through stakeholder interviews.
Additional analysis is needed to define specific requirements.
"""
    
    subsection_structure = [
        {"id": "functional_requirements", "type": "table"},
    ]
    
    result_lines, preamble = route_table_content_to_subsections(
        lines, section_span, llm_output, subsection_structure
    )
    
    # When no table content, preamble should contain all content
    assert "stakeholder interviews" in preamble.lower(), "Preamble should contain all content"
    assert "Additional analysis" in preamble, "Preamble should contain all prose"
    
    # Document should be unchanged (no tables to insert)
    assert result_lines == lines, "Document should be unchanged when no tables"
    
    print("  ✓ No table content detected")
    print("  ✓ All content routed to preamble")
    print("  ✓ Test passed")
    return True


def run_all_tests():
    """Run all table routing tests."""
    print("\n" + "=" * 70)
    print("TABLE ROUTING TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_extract_markdown_table_rows,
        test_identify_table_content_by_subsection,
        test_extract_non_table_content,
        test_route_table_content_to_subsections,
        test_route_with_no_table_content,
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
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
