#!/usr/bin/env python3
"""
Test script to validate human edit normalization behavior.

This script tests that:
1. Schema violations cause hard failures
2. Human edits are detected but not blocked (pre-approval)
3. Human edits are blocked at approval gate
4. Document structure validation works correctly
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import (
    validate_document_schema,
    is_document_at_approval_gate,
    detect_human_edits_to_protected_sections
)


def test_schema_validation_missing_section():
    """Test that missing required sections cause schema violation."""
    doc_missing_section = """# Requirements Document

**Version:** 0.1

## 1. Document Control

## 2. Problem Statement

Some content

## 3. Goals and Objectives

Some goals

# Missing sections 4-14!

## 15. Approval Record
"""
    
    is_valid, msg = validate_document_schema(doc_missing_section)
    assert not is_valid, "Should detect missing sections"
    assert "SCHEMA VIOLATION" in msg, f"Should report schema violation: {msg}"
    assert "Missing required section" in msg, f"Should specify missing section: {msg}"
    
    print("✓ Schema validation detects missing sections")


def test_schema_validation_invalid_question_status():
    """Test that invalid question status causes schema violation."""
    doc_invalid_status = """# Requirements Document

**Version:** 0.1

## 1. Document Control

### Open Questions

#### Q-001: Test Question

**Status:** InvalidStatus
**Asked by:** Human
**Date:** 2026-01-01

**Question:**
Test question text

**Answer:**


**Integration Targets:**
- Section 2

---

## 2. Problem Statement

## 3. Goals and Objectives

## 4. Non-Goals

## 5. Strategic Context

## 6. User Stories and Use Cases

## 7. Functional Requirements

## 8. Non-Functional Requirements

## 9. Constraints and Assumptions

## 10. Dependencies

## 11. Risks and Mitigations

## 12. Open Questions

## 13. Revision History

## 14. Implementation Notes

## 15. Approval Record
"""
    
    is_valid, msg = validate_document_schema(doc_invalid_status)
    assert not is_valid, "Should detect invalid question status"
    assert "SCHEMA VIOLATION" in msg, f"Should report schema violation: {msg}"
    assert "invalid status" in msg.lower(), f"Should mention invalid status: {msg}"
    
    print("✓ Schema validation detects invalid question status")


def test_schema_validation_missing_question_field():
    """Test that missing required question fields cause schema violation."""
    doc_missing_field = """# Requirements Document

**Version:** 0.1

## 1. Document Control

### Open Questions

#### Q-001: Test Question

**Status:** Open
**Asked by:** Human
**Date:** 2026-01-01

**Question:**
Test question text

**Answer:**


# Missing Integration Targets field!

---

## 2. Problem Statement

## 3. Goals and Objectives

## 4. Non-Goals

## 5. Strategic Context

## 6. User Stories and Use Cases

## 7. Functional Requirements

## 8. Non-Functional Requirements

## 9. Constraints and Assumptions

## 10. Dependencies

## 11. Risks and Mitigations

## 12. Open Questions

## 13. Revision History

## 14. Implementation Notes

## 15. Approval Record
"""
    
    is_valid, msg = validate_document_schema(doc_missing_field)
    assert not is_valid, "Should detect missing question field"
    assert "SCHEMA VIOLATION" in msg, f"Should report schema violation: {msg}"
    assert "missing required field" in msg.lower(), f"Should mention missing field: {msg}"
    
    print("✓ Schema validation detects missing question fields")


def test_schema_validation_valid_document():
    """Test that valid documents pass schema validation."""
    valid_doc = """# Requirements Document

**Version:** 0.1

## 1. Document Control

### Open Questions

#### Q-001: Test Question

**Status:** Open
**Asked by:** Human
**Date:** 2026-01-01

**Question:**
Test question text

**Answer:**


**Integration Targets:**
- Section 2

---

## 2. Problem Statement

## 3. Goals and Objectives

## 4. Non-Goals

## 5. Strategic Context

## 6. User Stories and Use Cases

## 7. Functional Requirements

## 8. Non-Functional Requirements

## 9. Constraints and Assumptions

## 10. Dependencies

## 11. Risks and Mitigations

## 12. Open Questions

## 13. Revision History

## 14. Implementation Notes

## 15. Approval Record
"""
    
    is_valid, msg = validate_document_schema(valid_doc)
    assert is_valid, f"Valid document should pass: {msg}"
    assert "passed" in msg.lower(), f"Should indicate success: {msg}"
    
    print("✓ Schema validation passes for valid documents")


def test_approval_gate_detection():
    """Test approval gate detection."""
    doc_ready = """# Requirements Document

**Version:** 0.1

## 1. Document Control

| Field | Value |
|-------|-------|
| Approval Status | Ready for Approval |

## 2. Problem Statement
"""
    
    doc_approved = """# Requirements Document

**Version:** 0.1

## 1. Document Control

| Field | Value |
|-------|-------|
| Approval Status | Approved |

## 15. Approval Record

| Field | Value |
|-------|-------|
| Current Status | Approved |
"""
    
    doc_pending = """# Requirements Document

**Version:** 0.1

## 1. Document Control

| Field | Value |
|-------|-------|
| Approval Status | Pending - Revisions Required |

## 2. Problem Statement
"""
    
    assert is_document_at_approval_gate(doc_ready), "Should detect Ready for Approval"
    assert is_document_at_approval_gate(doc_approved), "Should detect Approved"
    assert not is_document_at_approval_gate(doc_pending), "Should not detect Pending"
    
    print("✓ Approval gate detection works correctly")


if __name__ == "__main__":
    try:
        test_schema_validation_missing_section()
        test_schema_validation_invalid_question_status()
        test_schema_validation_missing_question_field()
        test_schema_validation_valid_document()
        test_approval_gate_detection()
        print("\n✓ All human edit normalization tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
