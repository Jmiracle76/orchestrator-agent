#!/usr/bin/env python3
"""
Integration test for canonical question enforcement.

This test validates that:
1. Ghost questions are detected during schema validation
2. Ghost questions are repaired automatically
3. Agent cannot create duplicate Question IDs
4. Agent cannot reference non-existent Question IDs during integration
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import (
    validate_document_schema,
    repair_ghost_questions,
    apply_patches,
    _get_canonical_question_ids,
    _validate_question_references
)


def get_minimal_valid_doc_structure():
    """Generate minimal document structure with all required sections."""
    return """
## 2. Problem Statement

Content.

## 3. Goals and Objectives

Content.

## 4. Non-Goals

Content.

## 5. Stakeholders and Users

Content.

## 6. Assumptions

Content.

## 7. Constraints

Content.

## 8. Functional Requirements

Content.

## 9. Non-Functional Requirements

Content.

## 10. Interfaces and Integrations

Content.

## 11. Data Considerations

Content.

## 12. Risks and Open Issues

### Identified Risks

| R-001 | Risk | Low | Low | Description | Owner |

### Open Questions

{questions}

---

## 13. Success Criteria and Acceptance

Content.

## 14. Out of Scope

Content.

## 15. Approval Record

**Current Status:** Draft
"""


def test_schema_validation_detects_ghosts():
    """Test that schema validation detects ghost question references."""
    questions = """#### Q-001: Only This Exists

**Status:** Open
**Asked by:** Test
**Date:** 2026-02-08

**Question:**
Only Q-001 is defined.

**Answer:**
[Awaiting response]

**Integration Targets:**
- Section 8: Functional Requirements

---
"""
    
    doc_base = get_minimal_valid_doc_structure().format(questions=questions)
    
    # Add ghost question references
    doc_with_ghost = doc_base.replace(
        "## 8. Functional Requirements\n\nContent.",
        "## 8. Functional Requirements\n\nSome requirement referencing Q-999."
    ).replace(
        "| R-001 | Risk | Low | Low | Description | Owner |",
        "| R-001 | Risk | Low | Low | **Active - Q-888 pending** | Owner |"
    )
    
    is_valid, msg, repairable = validate_document_schema(doc_with_ghost)
    
    assert not is_valid, "Document with ghost questions should fail validation"
    assert "Ghost question references detected" in msg, f"Expected ghost detection message, got: {msg}"
    assert "Q-999" in msg or "Q-888" in msg, f"Ghost Q-IDs should be in message: {msg}"
    
    print("✓ Schema validation detects ghost questions")


def test_full_repair_workflow():
    """Test complete repair workflow: detect -> repair -> validate."""
    questions = """#### Q-001: Existing Question

**Status:** Open
**Asked by:** Test
**Date:** 2026-02-08

**Question:**
Existing question.

**Answer:**
[Awaiting response]

**Integration Targets:**
- Section 8: Functional Requirements

---
"""
    
    doc_base = get_minimal_valid_doc_structure().format(questions=questions)
    
    # Add ghost question references
    doc_with_ghosts = doc_base.replace(
        "## 2. Problem Statement\n\nContent.",
        "## 2. Problem Statement\n\nThe problem involves Q-501 and Q-502."
    ).replace(
        "| R-001 | Risk | Low | Low | Description | Owner |",
        "| R-001 | Risk | Low | Low | **Q-503 needs resolution** | Owner |"
    )
    
    # Step 1: Validate (should fail)
    is_valid, ghosts, _ = _validate_question_references(doc_with_ghosts)
    assert not is_valid, "Should detect ghost questions"
    expected_ghosts = {'Q-501', 'Q-502', 'Q-503'}
    assert set(ghosts) == expected_ghosts, f"Expected {expected_ghosts}, got {set(ghosts)}"
    
    # Step 2: Repair
    repaired = repair_ghost_questions(doc_with_ghosts, ghosts)
    
    # Step 3: Validate after repair (should pass)
    is_valid_after, ghosts_after, _ = _validate_question_references(repaired)
    assert is_valid_after, f"After repair should be valid, but got ghosts: {ghosts_after}"
    assert len(ghosts_after) == 0, f"No ghosts should remain: {ghosts_after}"
    
    # Step 4: Verify all questions exist
    canonical_ids = _get_canonical_question_ids(repaired)
    assert 'Q-001' in canonical_ids, "Q-001 should exist (original)"
    assert 'Q-501' in canonical_ids, "Q-501 should exist (repaired)"
    assert 'Q-502' in canonical_ids, "Q-502 should exist (repaired)"
    assert 'Q-503' in canonical_ids, "Q-503 should exist (repaired)"
    
    print("✓ Full repair workflow test passed")


def test_agent_duplicate_prevention():
    """Test that agent cannot create duplicate Question IDs."""
    requirements_doc = """
## 12. Risks and Open Issues

### Open Questions

#### Q-001: Existing Question

**Status:** Open
**Asked by:** Test
**Date:** 2026-02-08

**Question:**
Existing.

**Answer:**
[Awaiting response]

**Integration Targets:**
- Section 8: Functional Requirements

---

<!--
ANSWER INTEGRATION WORKFLOW
-->

---
"""
    
    # Agent output attempting to create duplicate Q-001
    agent_output = """
## REVIEW_OUTPUT

### STATUS_UPDATE
Pending - Revisions Required

### RISKS
No new risks identified

### OPEN_QUESTIONS
#### Q-001: Duplicate Question Attempt

**Status:** Open
**Asked by:** Agent
**Date:** 2026-02-08

**Question:**
This is a duplicate.

**Answer:**
[Awaiting response]

**Integration Targets:**
- Section 9: Non-Functional Requirements

---

#### Q-002: New Valid Question

**Status:** Open
**Asked by:** Agent
**Date:** 2026-02-08

**Question:**
This is new.

**Answer:**
[Awaiting response]

**Integration Targets:**
- Section 9: Non-Functional Requirements

---
"""
    
    # Apply patches
    updated_doc, _ = apply_patches(requirements_doc, agent_output, "review")
    
    # Q-001 should still exist only once
    q001_count = updated_doc.count('#### Q-001:')
    assert q001_count == 1, f"Q-001 should appear exactly once, found {q001_count}"
    
    # Q-002 should be added
    assert '#### Q-002:' in updated_doc, "Q-002 should be added"
    
    print("✓ Agent duplicate prevention test passed")


def test_integration_ghost_prevention():
    """Test that integration validates Question IDs exist."""
    requirements_doc = """
## 8. Functional Requirements

Existing content.

## 12. Risks and Open Issues

### Open Questions

#### Q-001: Valid Question

**Status:** Open
**Asked by:** Test
**Date:** 2026-02-08

**Question:**
Valid question.

**Answer:**
Answer provided.

**Integration Targets:**
- Section 8: Functional Requirements

---
"""
    
    # Agent output attempting to integrate non-existent Q-999
    agent_output = """
## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Question ID: Q-999
- Section: ## 8. Functional Requirements
Content from non-existent question (Source: Ghost Q-999)

### RISKS
No risk changes

### STATUS_UPDATE
Ready for approval
"""
    
    # Apply patches - should detect ghost reference
    updated_doc, integration_info = apply_patches(requirements_doc, agent_output, "integrate")
    
    # Integration should be skipped due to ghost reference
    # The document should not contain the ghost content
    assert 'Source: Ghost Q-999' not in updated_doc, "Ghost question content should not be integrated"
    
    # Q-001 should not be marked as resolved (since it wasn't integrated)
    assert '**Status:** Open' in updated_doc, "Q-001 should remain Open"
    
    print("✓ Integration ghost prevention test passed")


def test_ranges_and_lists():
    """Test detection of Question IDs in ranges and lists."""
    questions = """#### Q-001: First

**Status:** Resolved
**Asked by:** Test
**Date:** 2026-02-08

**Question:**
First.

**Answer:**
Answered.

**Integration Targets:**
- Section 8: Functional Requirements

---

#### Q-002: Second

**Status:** Resolved
**Asked by:** Test
**Date:** 2026-02-08

**Question:**
Second.

**Answer:**
Answered.

**Integration Targets:**
- Section 8: Functional Requirements

---
"""
    
    doc_base = get_minimal_valid_doc_structure().format(questions=questions)
    
    # Add range references
    doc_with_ranges = doc_base.replace(
        "## 8. Functional Requirements\n\nContent.",
        "## 8. Functional Requirements\n\nQuestions Q-001 through Q-005 have been answered."
    ).replace(
        "| R-001 | Risk | Low | Low | Description | Owner |",
        "| R-001 | Risk | Low | Low | **MITIGATED by Q-001, Q-002, Q-003 answers** | Owner |"
    )
    
    is_valid, ghosts, _ = _validate_question_references(doc_with_ranges)
    
    # Should detect Q-003, Q-004, Q-005 as ghosts (only Q-001 and Q-002 exist)
    # Note: "Q-001 through Q-005" will only detect Q-001 and Q-005, not Q-002-Q-004
    # The Q-003 comes from the risks line
    assert not is_valid, "Should detect missing questions"
    # We expect at least Q-003 and Q-005 to be detected as ghosts
    assert 'Q-003' in ghosts, f"Should detect Q-003; got {ghosts}"
    assert 'Q-005' in ghosts, f"Should detect Q-005; got {ghosts}"
    
    print("✓ Ranges and lists detection test passed")


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Integration Tests: Canonical Question Enforcement")
    print("=" * 60 + "\n")
    
    try:
        test_schema_validation_detects_ghosts()
        test_full_repair_workflow()
        test_agent_duplicate_prevention()
        test_integration_ghost_prevention()
        test_ranges_and_lists()
        
        print("\n" + "=" * 60)
        print("All integration tests passed!")
        print("=" * 60 + "\n")
        
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
    sys.exit(main())
