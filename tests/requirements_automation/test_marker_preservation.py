#!/usr/bin/env python3
"""
Test for Issue 4b: CI tests to verify no markers lost during simulated LLM drafting.

This test suite validates that all structural markers survive LLM drafting operations:
1. Tests replace_block_body_preserving_markers() on all section types from the template
2. Verifies all subsection markers (<!-- subsection:* -->) are preserved
3. Verifies all table markers (<!-- table:* -->) are preserved  
4. Tests edge cases: multiple subsections, nested tables, complex structures
5. Ensures CI fails if any marker is destroyed
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.editing import replace_block_body_preserving_markers
from requirements_automation.utils_io import read_text, split_lines


def test_document_control_with_version_history():
    """
    Test: Section with single subsection containing a table.
    Template section: document_control
    Contains: version_history subsection with table (not a table in preamble)
    
    Note: Tables in the preamble (before first subsection) are replaced along with
    other preamble content. This test focuses on subsection marker preservation.
    """
    print("\nTest 1: Document Control with Version History subsection")
    print("=" * 70)

    test_doc = """<!-- section:document_control -->
## 1. Document Control

Document control preamble content here.

<!-- subsection:version_history -->
### Version History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-01-01 | Alice | Initial version |
| 1.1 | 2024-02-01 | Bob | Updates |

---
"""

    lines = split_lines(test_doc)
    new_body = "Updated document control information.\n\nNew preamble content."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="document_control", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify version_history subsection marker preserved
    assert "<!-- subsection:version_history -->" in result_doc, \
        "version_history subsection marker was removed!"
    print("  ✓ version_history subsection marker preserved")
    
    # Verify version history table content preserved (it's inside the subsection)
    assert "1.0" in result_doc and "Alice" in result_doc and "Initial version" in result_doc, \
        "Version history table content was removed!"
    print("  ✓ Version history table content preserved")
    
    # Verify version history header preserved
    assert "### Version History" in result_doc, \
        "Version history heading was removed!"
    print("  ✓ Version history heading preserved")
    
    # Verify new body was inserted
    assert "Updated document control information" in result_doc, \
        "New body content was not inserted!"
    print("  ✓ New body content inserted")
    
    # Verify old preamble was replaced
    assert "Document control preamble content here" not in result_doc, \
        "Old preamble was not replaced!"
    print("  ✓ Old preamble replaced")
    
    print("  ✓ Test passed")
    return True


def test_goals_objectives_multiple_subsections():
    """
    Test: Section with multiple subsections.
    Template section: goals_objectives
    Contains: 4 content subsections + questions_issues subsection with table
    """
    print("\nTest 2: Goals & Objectives with multiple subsections")
    print("=" * 70)

    test_doc = """<!-- section:goals_objectives -->
## 3. Goals and Objectives

Initial goals overview.

<!-- subsection:objective_statement -->
### Objective Statement
Clear project objective.

<!-- subsection:primary_goals -->
### Primary Goals
1. Primary goal 1
2. Primary goal 2

<!-- subsection:secondary_goals -->
### Secondary Goals
1. Secondary goal 1
2. Secondary goal 2

<!-- subsection:non_goals -->
### Non-Goals
1. Non-goal 1
2. Non-goal 2

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:goals_objectives_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| goals_objectives-Q1 | What are the measurable success indicators? | 2024-01-01 | - | Open |

<!-- section_lock:goals_objectives lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "Updated goals and objectives overview.\n\nThis replaces the preamble only."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="goals_objectives", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify all subsection markers preserved
    required_subsections = [
        "objective_statement",
        "primary_goals", 
        "secondary_goals",
        "non_goals",
        "questions_issues"
    ]
    
    for subsection in required_subsections:
        assert f"<!-- subsection:{subsection} -->" in result_doc, \
            f"{subsection} subsection marker was removed!"
        print(f"  ✓ {subsection} subsection marker preserved")
    
    # Verify table marker preserved
    assert "<!-- table:goals_objectives_questions -->" in result_doc, \
        "goals_objectives_questions table marker was removed!"
    print("  ✓ goals_objectives_questions table marker preserved")
    
    # Verify subsection content preserved
    assert "Primary goal 1" in result_doc, "Primary goals content was removed!"
    assert "Secondary goal 1" in result_doc, "Secondary goals content was removed!"
    assert "Non-goal 1" in result_doc, "Non-goals content was removed!"
    print("  ✓ All subsection content preserved")
    
    # Verify table content preserved
    assert "goals_objectives-Q1" in result_doc and "measurable success indicators" in result_doc, \
        "Questions table content was removed!"
    print("  ✓ Questions table content preserved")
    
    # Verify new body inserted and old preamble replaced
    assert "Updated goals and objectives overview" in result_doc, \
        "New body was not inserted!"
    assert "Initial goals overview" not in result_doc, \
        "Old preamble was not replaced!"
    print("  ✓ New body inserted, old preamble replaced")
    
    print("  ✓ Test passed")
    return True


def test_stakeholders_users_nested_tables():
    """
    Test: Section with multiple subsections each containing tables.
    Template section: stakeholders_users
    Contains: primary_stakeholders (table), end_users (table), questions_issues (table)
    """
    print("\nTest 3: Stakeholders & Users with nested tables in subsections")
    print("=" * 70)

    test_doc = """<!-- section:stakeholders_users -->
## 4. Stakeholders and Users

Initial stakeholder analysis.

<!-- subsection:primary_stakeholders -->
### Primary Stakeholders

<!-- table:primary_stakeholders -->
| Stakeholder | Role | Interest/Need | Contact |
|-------------|------|---------------|---------|
| Alice | PM | Project success | alice@example.com |
| Bob | Tech Lead | Technical direction | bob@example.com |

<!-- subsection:end_users -->
### End Users

<!-- table:end_users -->
| User Type | Characteristics | Needs | Use Cases |
|-----------|----------------|-------|-----------|
| Admin | Technical user | Full control | System management |
| Regular | Non-technical | Ease of use | Daily tasks |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:stakeholders_users_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| stakeholders_users-Q1 | Have all key stakeholders been identified? | 2024-01-01 | - | Open |

<!-- section_lock:stakeholders_users lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "Comprehensive stakeholder and user analysis.\n\nUpdated preamble."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="stakeholders_users", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify all subsection markers preserved
    assert "<!-- subsection:primary_stakeholders -->" in result_doc, \
        "primary_stakeholders subsection marker was removed!"
    assert "<!-- subsection:end_users -->" in result_doc, \
        "end_users subsection marker was removed!"
    assert "<!-- subsection:questions_issues -->" in result_doc, \
        "questions_issues subsection marker was removed!"
    print("  ✓ All subsection markers preserved")
    
    # Verify all table markers preserved
    assert "<!-- table:primary_stakeholders -->" in result_doc, \
        "primary_stakeholders table marker was removed!"
    assert "<!-- table:end_users -->" in result_doc, \
        "end_users table marker was removed!"
    assert "<!-- table:stakeholders_users_questions -->" in result_doc, \
        "stakeholders_users_questions table marker was removed!"
    print("  ✓ All table markers preserved")
    
    # Verify table content preserved
    assert "Alice" in result_doc and "alice@example.com" in result_doc, \
        "Primary stakeholders table content was removed!"
    assert "Admin" in result_doc and "Regular" in result_doc, \
        "End users table content was removed!"
    assert "stakeholders_users-Q1" in result_doc, \
        "Questions table content was removed!"
    print("  ✓ All table content preserved")
    
    # Verify table headers preserved
    assert "| Stakeholder | Role | Interest/Need | Contact |" in result_doc, \
        "Primary stakeholders table header was removed!"
    assert "| User Type | Characteristics | Needs | Use Cases |" in result_doc, \
        "End users table header was removed!"
    print("  ✓ All table headers preserved")
    
    print("  ✓ Test passed")
    return True


def test_constraints_multiple_levels():
    """
    Test: Section with subsections at different levels.
    Template section: constraints
    Contains: technical_constraints, operational_constraints, resource_constraints, questions_issues
    """
    print("\nTest 4: Constraints with subsections at different levels")
    print("=" * 70)

    test_doc = """<!-- section:constraints -->
## 6. Constraints

Overview of project constraints.

<!-- subsection:technical_constraints -->
### Technical Constraints
- Must use Python 3.8+
- Must support Linux and Windows

<!-- subsection:operational_constraints -->
### Operational Constraints
- 24/7 availability required
- Response time < 200ms

<!-- subsection:resource_constraints -->
### Resource Constraints
- Budget: $100k
- Team: 3 developers

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:constraints_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| constraints-Q1 | Are there workarounds for identified constraints? | 2024-01-01 | - | Open |

<!-- section_lock:constraints lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "Updated constraints overview.\n\nDetailed constraint analysis."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="constraints", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify all subsection markers preserved
    subsections = [
        "technical_constraints",
        "operational_constraints", 
        "resource_constraints",
        "questions_issues"
    ]
    for subsection in subsections:
        assert f"<!-- subsection:{subsection} -->" in result_doc, \
            f"{subsection} subsection marker was removed!"
        print(f"  ✓ {subsection} subsection marker preserved")
    
    # Verify table marker preserved
    assert "<!-- table:constraints_questions -->" in result_doc, \
        "constraints_questions table marker was removed!"
    print("  ✓ constraints_questions table marker preserved")
    
    # Verify subsection content preserved
    assert "Python 3.8+" in result_doc, "Technical constraints content was removed!"
    assert "24/7 availability" in result_doc, "Operational constraints content was removed!"
    assert "$100k" in result_doc, "Resource constraints content was removed!"
    print("  ✓ All subsection content preserved")
    
    print("  ✓ Test passed")
    return True


def test_interfaces_integrations_tables_only():
    """
    Test: Section with subsections containing only tables (no preamble text).
    Template section: interfaces_integrations
    Contains: external_systems (table), data_exchange (table), questions_issues (table)
    """
    print("\nTest 5: Interfaces & Integrations with table-only subsections")
    print("=" * 70)

    test_doc = """<!-- section:interfaces_integrations -->
## 8. Interfaces and Integrations

<!-- subsection:external_systems -->
### External Systems

<!-- table:external_systems -->
| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|
| PaymentAPI | Process payments | REST API | Auth service |
| EmailService | Send emails | SMTP | None |

<!-- subsection:data_exchange -->
### Data Exchange

<!-- table:data_exchange -->
| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|
| UserSync | Bidirectional | JSON | Hourly |
| ReportExport | Outbound | CSV | Daily |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:interfaces_integrations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|

<!-- section_lock:interfaces_integrations lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "Overview of system interfaces and integrations."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="interfaces_integrations", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify all subsection markers preserved
    assert "<!-- subsection:external_systems -->" in result_doc, \
        "external_systems subsection marker was removed!"
    assert "<!-- subsection:data_exchange -->" in result_doc, \
        "data_exchange subsection marker was removed!"
    assert "<!-- subsection:questions_issues -->" in result_doc, \
        "questions_issues subsection marker was removed!"
    print("  ✓ All subsection markers preserved")
    
    # Verify all table markers preserved
    assert "<!-- table:external_systems -->" in result_doc, \
        "external_systems table marker was removed!"
    assert "<!-- table:data_exchange -->" in result_doc, \
        "data_exchange table marker was removed!"
    assert "<!-- table:interfaces_integrations_questions -->" in result_doc, \
        "interfaces_integrations_questions table marker was removed!"
    print("  ✓ All table markers preserved")
    
    # Verify table content and headers preserved
    assert "PaymentAPI" in result_doc and "REST API" in result_doc, \
        "External systems table content was removed!"
    assert "UserSync" in result_doc and "JSON" in result_doc, \
        "Data exchange table content was removed!"
    print("  ✓ All table content preserved")
    
    # Verify table headers preserved
    assert "| System | Purpose | Interface Type | Dependencies |" in result_doc, \
        "External systems table header was removed!"
    assert "| Integration Point | Data Flow | Format | Frequency |" in result_doc, \
        "Data exchange table header was removed!"
    print("  ✓ All table headers preserved")
    
    print("  ✓ Test passed")
    return True


def test_data_considerations_mixed_subsections():
    """
    Test: Section with mix of content subsections and table subsections.
    Template section: data_considerations
    Contains: data_requirements (text), privacy_security (text), data_retention (text), questions_issues (table)
    """
    print("\nTest 6: Data Considerations with mixed subsection types")
    print("=" * 70)

    test_doc = """<!-- section:data_considerations -->
## 9. Data Considerations

<!-- subsection:data_requirements -->
### Data Requirements
- User profiles and authentication data
- Transaction history
- Audit logs

<!-- subsection:privacy_security -->
### Privacy & Security
- GDPR compliance required
- Encryption at rest and in transit
- Access control and authentication

<!-- subsection:data_retention -->
### Data Retention
- User data: 7 years
- Transaction logs: 5 years
- Audit logs: 10 years

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:data_considerations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| data_considerations-Q1 | What are the data residency requirements? | 2024-01-01 | - | Open |

<!-- section_lock:data_considerations lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "Comprehensive data management strategy."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="data_considerations", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify all subsection markers preserved
    subsections = [
        "data_requirements",
        "privacy_security",
        "data_retention", 
        "questions_issues"
    ]
    for subsection in subsections:
        assert f"<!-- subsection:{subsection} -->" in result_doc, \
            f"{subsection} subsection marker was removed!"
        print(f"  ✓ {subsection} subsection marker preserved")
    
    # Verify table marker preserved
    assert "<!-- table:data_considerations_questions -->" in result_doc, \
        "data_considerations_questions table marker was removed!"
    print("  ✓ Table marker preserved")
    
    # Verify subsection content preserved
    assert "User profiles" in result_doc, "Data requirements content was removed!"
    assert "GDPR compliance" in result_doc, "Privacy & security content was removed!"
    assert "7 years" in result_doc, "Data retention content was removed!"
    assert "data_considerations-Q1" in result_doc, "Questions table content was removed!"
    print("  ✓ All subsection content preserved")
    
    print("  ✓ Test passed")
    return True


def test_problem_statement_no_subsections():
    """
    Test: Section without subsections - entire body should be replaced.
    Template section: problem_statement (simplified, without questions subsection)
    """
    print("\nTest 7: Problem Statement without subsections")
    print("=" * 70)

    test_doc = """<!-- section:problem_statement -->
## 2. Problem Statement

Old problem description.
This is the existing content.

Multiple paragraphs here.

<!-- section_lock:problem_statement lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "New problem statement.\n\nCompletely different content.\n\nMultiple new paragraphs."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="problem_statement", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify section marker preserved
    assert "<!-- section:problem_statement -->" in result_doc, \
        "Section marker was removed!"
    print("  ✓ Section marker preserved")
    
    # Verify lock marker preserved
    assert "<!-- section_lock:problem_statement lock=false -->" in result_doc, \
        "Lock marker was removed!"
    print("  ✓ Lock marker preserved")
    
    # Verify new content inserted
    assert "New problem statement" in result_doc and "Completely different content" in result_doc, \
        "New content was not inserted!"
    print("  ✓ New content inserted")
    
    # Verify old content replaced
    assert "Old problem description" not in result_doc, \
        "Old content was not replaced!"
    print("  ✓ Old content replaced")
    
    print("  ✓ Test passed")
    return True


def test_subsection_immediately_after_heading():
    """
    Test: Edge case where subsection appears immediately after section heading.
    No preamble content between heading and first subsection.
    """
    print("\nTest 8: Subsection immediately after section heading (edge case)")
    print("=" * 70)

    test_doc = """<!-- section:requirements -->
## 7. Requirements

<!-- subsection:functional_requirements -->
### Functional Requirements

<!-- table:functional_requirements -->
| Req ID | Description | Priority | Source | Acceptance Criteria |
|--------|-------------|----------|--------|---------------------|
| REQ-001 | User login | High | Stakeholder | Login within 2s |
| REQ-002 | Data export | Medium | User request | Export to CSV/JSON |

<!-- subsection:non_functional_requirements -->
### Non-Functional Requirements

<!-- table:non_functional_requirements -->
| Req ID | Category | Description | Priority | Measurement Criteria | Acceptance Criteria |
|--------|----------|-------------|----------|---------------------|---------------------|
| NFR-001 | Performance | Response time | High | < 200ms | 95th percentile |

<!-- section_lock:requirements lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "Requirements overview and context."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="requirements", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify both subsection markers preserved
    assert "<!-- subsection:functional_requirements -->" in result_doc, \
        "functional_requirements subsection marker was removed!"
    assert "<!-- subsection:non_functional_requirements -->" in result_doc, \
        "non_functional_requirements subsection marker was removed!"
    print("  ✓ All subsection markers preserved")
    
    # Verify both table markers preserved
    assert "<!-- table:functional_requirements -->" in result_doc, \
        "functional_requirements table marker was removed!"
    assert "<!-- table:non_functional_requirements -->" in result_doc, \
        "non_functional_requirements table marker was removed!"
    print("  ✓ All table markers preserved")
    
    # Verify table content preserved
    assert "REQ-001" in result_doc and "User login" in result_doc, \
        "Functional requirements table content was removed!"
    assert "NFR-001" in result_doc and "Performance" in result_doc, \
        "Non-functional requirements table content was removed!"
    print("  ✓ All table content preserved")
    
    # Verify new preamble added
    assert "Requirements overview and context" in result_doc, \
        "New preamble was not added!"
    print("  ✓ New preamble added before subsections")
    
    print("  ✓ Test passed")
    return True


def test_multiple_replacements_preserve_all_markers():
    """
    Test: Simulate multiple LLM drafting passes on same document.
    Verify all markers survive repeated replacements.
    """
    print("\nTest 9: Multiple replacements preserve all markers")
    print("=" * 70)

    # Create a document with multiple sections
    test_doc = """<!-- section:section_a -->
## Section A

Original content A.

<!-- subsection:sub_a1 -->
### Subsection A1
Content A1.

<!-- table:table_a1 -->
| ID | Name |
|----|------|
| 1  | Item A |

<!-- section_lock:section_a lock=false -->
---

<!-- section:section_b -->
## Section B

Original content B.

<!-- subsection:sub_b1 -->
### Subsection B1
Content B1.

<!-- subsection:sub_b2 -->
### Subsection B2
Content B2.

<!-- section_lock:section_b lock=false -->
---
"""

    lines = split_lines(test_doc)
    
    # First replacement: section_a
    lines = replace_block_body_preserving_markers(
        lines, 0, 15, section_id="section_a", new_body="Updated content A - pass 1"
    )
    
    # Second replacement: section_b  
    lines = replace_block_body_preserving_markers(
        lines, 15, len(lines), section_id="section_b", new_body="Updated content B - pass 1"
    )
    
    # Third replacement: section_a again
    lines = replace_block_body_preserving_markers(
        lines, 0, 15, section_id="section_a", new_body="Updated content A - pass 2"
    )
    
    result_doc = "\n".join(lines)
    
    # Verify all markers still present after multiple replacements
    assert "<!-- section:section_a -->" in result_doc, "section_a marker was removed!"
    assert "<!-- section:section_b -->" in result_doc, "section_b marker was removed!"
    assert "<!-- subsection:sub_a1 -->" in result_doc, "sub_a1 marker was removed!"
    assert "<!-- subsection:sub_b1 -->" in result_doc, "sub_b1 marker was removed!"
    assert "<!-- subsection:sub_b2 -->" in result_doc, "sub_b2 marker was removed!"
    assert "<!-- table:table_a1 -->" in result_doc, "table_a1 marker was removed!"
    print("  ✓ All markers preserved after multiple replacements")
    
    # Verify content was actually replaced
    assert "Updated content A - pass 2" in result_doc, "Section A was not updated!"
    assert "Updated content B - pass 1" in result_doc, "Section B was not updated!"
    assert "Original content A" not in result_doc, "Original content A not replaced!"
    assert "Original content B" not in result_doc, "Original content B not replaced!"
    print("  ✓ Content was properly replaced")
    
    # Verify subsection content preserved
    assert "Content A1" in result_doc, "Subsection A1 content was removed!"
    assert "Content B1" in result_doc, "Subsection B1 content was removed!"
    assert "Content B2" in result_doc, "Subsection B2 content was removed!"
    assert "Item A" in result_doc, "Table content was removed!"
    print("  ✓ All subsection content preserved")
    
    print("  ✓ Test passed")
    return True


def test_table_headers_preserved():
    """
    Test: Verify that table headers are preserved during body replacement.
    This is critical for maintaining table structure integrity.
    """
    print("\nTest 10: Table headers preserved during replacement")
    print("=" * 70)

    test_doc = """<!-- section:test_section -->
## Test Section

Original preamble.

<!-- subsection:test_subsection -->
### Test Subsection

<!-- table:test_table -->
| Column A | Column B | Column C | Column D |
|----------|----------|----------|----------|
| Value 1A | Value 1B | Value 1C | Value 1D |
| Value 2A | Value 2B | Value 2C | Value 2D |
| Value 3A | Value 3B | Value 3C | Value 3D |

<!-- section_lock:test_section lock=false -->
---
"""

    lines = split_lines(test_doc)
    new_body = "New preamble content."
    
    result_lines = replace_block_body_preserving_markers(
        lines, 0, len(lines), section_id="test_section", new_body=new_body
    )
    result_doc = "\n".join(result_lines)
    
    # Verify exact table header line is preserved
    assert "| Column A | Column B | Column C | Column D |" in result_doc, \
        "Table header was modified or removed!"
    print("  ✓ Table header preserved exactly")
    
    # Verify table separator line is preserved
    assert "|----------|----------|----------|----------|" in result_doc, \
        "Table separator was removed!"
    print("  ✓ Table separator preserved")
    
    # Verify all table rows preserved
    assert "| Value 1A | Value 1B | Value 1C | Value 1D |" in result_doc, \
        "Table row 1 was removed!"
    assert "| Value 2A | Value 2B | Value 2C | Value 2D |" in result_doc, \
        "Table row 2 was removed!"
    assert "| Value 3A | Value 3B | Value 3C | Value 3D |" in result_doc, \
        "Table row 3 was removed!"
    print("  ✓ All table rows preserved")
    
    # Verify table marker preserved
    assert "<!-- table:test_table -->" in result_doc, \
        "Table marker was removed!"
    print("  ✓ Table marker preserved")
    
    print("  ✓ Test passed")
    return True


def main():
    """Run all marker preservation tests."""
    print("\n" + "=" * 70)
    print("MARKER PRESERVATION TEST SUITE - Issue 4b")
    print("Testing: replace_block_body_preserving_markers()")
    print("=" * 70)

    results = []
    
    # Test 1: Document control with version history
    try:
        results.append(test_document_control_with_version_history())
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 2: Goals & objectives with multiple subsections
    try:
        results.append(test_goals_objectives_multiple_subsections())
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 3: Stakeholders & users with nested tables
    try:
        results.append(test_stakeholders_users_nested_tables())
    except Exception as e:
        print(f"✗ Test 3 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 4: Constraints with multiple levels
    try:
        results.append(test_constraints_multiple_levels())
    except Exception as e:
        print(f"✗ Test 4 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 5: Interfaces & integrations with table-only subsections
    try:
        results.append(test_interfaces_integrations_tables_only())
    except Exception as e:
        print(f"✗ Test 5 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 6: Data considerations with mixed subsections
    try:
        results.append(test_data_considerations_mixed_subsections())
    except Exception as e:
        print(f"✗ Test 6 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 7: Problem statement without subsections
    try:
        results.append(test_problem_statement_no_subsections())
    except Exception as e:
        print(f"✗ Test 7 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 8: Subsection immediately after heading (edge case)
    try:
        results.append(test_subsection_immediately_after_heading())
    except Exception as e:
        print(f"✗ Test 8 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 9: Multiple replacements preserve all markers
    try:
        results.append(test_multiple_replacements_preserve_all_markers())
    except Exception as e:
        print(f"✗ Test 9 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Test 10: Table headers preserved
    try:
        results.append(test_table_headers_preserved())
    except Exception as e:
        print(f"✗ Test 10 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    # Print summary
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 70)
    
    if not all(results):
        print("\n❌ FAILURE: Some markers were lost during simulated LLM drafting!")
        print("This means the editing function does not properly preserve structural markers.")
        return 1
    else:
        print("\n✅ SUCCESS: All structural markers preserved during simulated LLM drafting!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
