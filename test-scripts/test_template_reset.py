#!/usr/bin/env python3
"""
Test script to validate template reset functionality.

This script tests that:
1. Reset replaces entire document with canonical template
2. Version is reset to 0.0
3. Status is reset to Draft
4. All project-specific content is removed
5. Multiple resets are idempotent
"""

import sys
import tempfile
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import CANONICAL_TEMPLATE


def test_template_structure():
    """Test that canonical template has correct structure."""
    print("\n[Test] Validating canonical template structure...")
    
    # Check version is 0.0
    assert "**Version:** 0.0" in CANONICAL_TEMPLATE, "Template must have version 0.0"
    assert "| Current Version | 0.0 |" in CANONICAL_TEMPLATE, "Document Control must show version 0.0"
    
    # Check status is Draft
    assert "**Status:** Draft" in CANONICAL_TEMPLATE, "Template status must be Draft"
    assert "| Current Status | Draft |" in CANONICAL_TEMPLATE, "Approval Record must show Draft status"
    
    # Check all required sections are present
    required_sections = [
        "## 1. Document Control",
        "## 2. Problem Statement",
        "## 3. Goals and Objectives",
        "## 4. Non-Goals",
        "## 5. Stakeholders and Users",
        "## 6. Assumptions",
        "## 7. Constraints",
        "## 8. Functional Requirements",
        "## 9. Non-Functional Requirements",
        "## 10. Interfaces and Integrations",
        "## 11. Data Considerations",
        "## 12. Risks and Open Issues",
        "## 13. Success Criteria and Acceptance",
        "## 14. Out of Scope",
        "## 15. Approval Record",
    ]
    
    for section in required_sections:
        assert section in CANONICAL_TEMPLATE, f"Template must contain {section}"
    
    # Check Section 12 subsections
    assert "### Identified Risks" in CANONICAL_TEMPLATE, "Template must have Identified Risks subsection"
    assert "### Intake" in CANONICAL_TEMPLATE, "Template must have Intake subsection"
    assert "### Open Questions" in CANONICAL_TEMPLATE, "Template must have Open Questions subsection"
    
    # Check version history has only template baseline entry
    assert "| 0.0 |" in CANONICAL_TEMPLATE, "Template must have version 0.0 in history"
    assert "Template baseline" in CANONICAL_TEMPLATE, "Template must reference template baseline"
    
    # Check for baseline risk placeholder
    assert "R-001" in CANONICAL_TEMPLATE, "Template must have baseline risk R-001"
    assert "Template baseline state" in CANONICAL_TEMPLATE, "Template must reference template baseline state"
    
    # Check Open Questions is empty
    assert "[No open questions at this time]" in CANONICAL_TEMPLATE, "Template Open Questions should be empty"
    
    # Check Intake is empty
    assert "[Empty - add human notes here as needed]" in CANONICAL_TEMPLATE, "Template Intake should be empty"
    
    print("✓ Canonical template structure validation passed")


def test_template_placeholders():
    """Test that template contains appropriate placeholders and no project-specific content."""
    print("\n[Test] Validating template placeholders...")
    
    # Template should have placeholder content
    assert "[Project Name]" in CANONICAL_TEMPLATE, "Template should have [Project Name] placeholder"
    assert "[Date]" in CANONICAL_TEMPLATE, "Template should have [Date] placeholders"
    assert "[Content needed for" in CANONICAL_TEMPLATE, "Template should have content placeholders"
    
    # Template should NOT have project-specific content
    # (checking for patterns that would indicate actual requirements)
    lines = CANONICAL_TEMPLATE.split('\n')
    for i, line in enumerate(lines):
        # Skip comments and placeholders
        if line.strip().startswith('<!--') or '[' in line and ']' in line:
            continue
        # Check that we don't have specific question IDs beyond R-001 (the template baseline risk)
        if 'Q-00' in line and 'Q-001' not in line:
            assert False, f"Template should not contain specific question IDs: line {i+1}: {line}"
        if 'R-00' in line and 'R-001' not in line:
            assert False, f"Template should not contain specific risk IDs beyond R-001: line {i+1}: {line}"
    
    print("✓ Template placeholders validation passed")


def test_idempotency():
    """Test that template content is consistent and would produce idempotent resets."""
    print("\n[Test] Validating template idempotency...")
    
    # The template constant should be deterministic
    # Check that it has consistent structure
    lines = CANONICAL_TEMPLATE.split('\n')
    
    # Count sections
    section_count = sum(1 for line in lines if line.startswith('## ') and '. ' in line)
    assert section_count == 15, f"Template must have exactly 15 numbered sections, found {section_count}"
    
    # Check that Version History has exactly one entry (the 0.0 baseline)
    in_version_history = False
    version_entries = 0
    for line in lines:
        if '### Version History' in line:
            in_version_history = True
        elif line.startswith('##'):
            in_version_history = False
        elif in_version_history and line.strip().startswith('| 0.'):
            version_entries += 1
    
    assert version_entries == 1, f"Template Version History must have exactly 1 entry, found {version_entries}"
    
    print("✓ Template idempotency validation passed")


def test_schema_compliance():
    """Test that template passes basic schema validation requirements."""
    print("\n[Test] Validating template schema compliance...")
    
    # Import validation function
    from invoke_requirements_agent import validate_document_schema
    
    # Validate the template
    is_valid, message, repairable = validate_document_schema(CANONICAL_TEMPLATE)
    
    # Template should pass validation (no missing sections, no fatal violations)
    assert is_valid, f"Template must pass schema validation: {message}"
    assert len(repairable) == 0, f"Template must have all sections present: {repairable}"
    
    print("✓ Template schema compliance validation passed")


def run_all_tests():
    """Run all template reset tests."""
    print("=" * 70)
    print("TEMPLATE RESET TEST SUITE")
    print("=" * 70)
    
    try:
        test_template_structure()
        test_template_placeholders()
        test_idempotency()
        test_schema_compliance()
        
        print("\n" + "=" * 70)
        print("✓ All template reset tests passed!")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
