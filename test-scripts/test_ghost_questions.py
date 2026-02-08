#!/usr/bin/env python3
"""
Test script to validate ghost question detection and repair.

This script tests that:
1. Ghost question references are detected
2. Ghost questions can be repaired by creating canonical entries
3. Duplicate question IDs are prevented during agent output processing
4. Integration validates that referenced Question IDs exist
"""

import sys
import re
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import (
    _get_canonical_question_ids,
    _find_question_id_references,
    _validate_question_references,
    repair_ghost_questions,
    _parse_open_questions_section
)


def test_get_canonical_question_ids():
    """Test extraction of canonical Question IDs."""
    sample_doc = """
## 12. Risks and Open Issues

### Open Questions

#### Q-001: Test Question One

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is question 1.

**Answer:**  
[Awaiting response]

**Integration Targets:**  
- Section 8: Functional Requirements

---

#### Q-003: Test Question Three

**Status:** Resolved  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is question 3.

**Answer:**  
Answer provided.

**Integration Targets:**  
- Section 9: Non-Functional Requirements

---
"""
    
    q_ids = _get_canonical_question_ids(sample_doc)
    assert q_ids == {'Q-001', 'Q-003'}, f"Expected Q-001 and Q-003, got {q_ids}"
    
    print("✓ Get canonical Question IDs test passed")


def test_find_question_id_references():
    """Test finding Question ID references outside Open Questions section."""
    sample_doc = """
## 8. Functional Requirements

Some content here.

*Source: Product Owner (Answer to Q-001)*

More content referencing Q-002.

## 12. Risks and Open Issues

### Identified Risks

| R-001 | Some risk | Low | Low | **MITIGATED by Q-001, Q-003 answers** | Product Owner |

### Open Questions

#### Q-001: Test Question One

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is question 1.

**Answer:**  
[Awaiting response]

**Integration Targets:**  
- Section 8: Functional Requirements

---
"""
    
    refs = _find_question_id_references(sample_doc)
    
    # Should find Q-001, Q-002, and Q-003 in the content
    # But Q-001 in the Open Questions section itself should not be counted
    assert 'Q-001' in refs, f"Q-001 should be referenced, got {refs.keys()}"
    assert 'Q-002' in refs, f"Q-002 should be referenced, got {refs.keys()}"
    assert 'Q-003' in refs, f"Q-003 should be referenced, got {refs.keys()}"
    
    print("✓ Find Question ID references test passed")


def test_detect_ghost_questions():
    """Test detection of ghost question references."""
    sample_doc = """
## 8. Functional Requirements

*Source: Product Owner (Answer to Q-005)*

Some content mentioning Q-010 and Q-011.

## 12. Risks and Open Issues

### Identified Risks

| R-001 | Risk | Low | Low | **MITIGATED by Q-007 answer** | Owner |

### Open Questions

#### Q-001: Only This Exists

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
    
    is_valid, ghost_questions, all_refs = _validate_question_references(sample_doc)
    
    assert not is_valid, "Document should be invalid due to ghost questions"
    assert 'Q-005' in ghost_questions, f"Q-005 should be ghost, got {ghost_questions}"
    assert 'Q-007' in ghost_questions, f"Q-007 should be ghost, got {ghost_questions}"
    assert 'Q-010' in ghost_questions, f"Q-010 should be ghost, got {ghost_questions}"
    assert 'Q-011' in ghost_questions, f"Q-011 should be ghost, got {ghost_questions}"
    assert 'Q-001' not in ghost_questions, f"Q-001 should not be ghost (it exists), got {ghost_questions}"
    
    print("✓ Detect ghost questions test passed")


def test_no_ghost_questions():
    """Test that valid documents pass validation."""
    sample_doc = """
## 8. Functional Requirements

*Source: Product Owner (Answer to Q-001)*

Some content mentioning Q-002.

## 12. Risks and Open Issues

### Identified Risks

| R-001 | Risk | Low | Low | **MITIGATED by Q-001, Q-002 answers** | Owner |

### Open Questions

#### Q-001: First Question

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
Question 1.

**Answer:**  
[Awaiting response]

**Integration Targets:**  
- Section 8: Functional Requirements

---

#### Q-002: Second Question

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
Question 2.

**Answer:**  
[Awaiting response]

**Integration Targets:**  
- Section 9: Non-Functional Requirements

---
"""
    
    is_valid, ghost_questions, all_refs = _validate_question_references(sample_doc)
    
    assert is_valid, "Document should be valid - all references exist"
    assert len(ghost_questions) == 0, f"No ghost questions expected, got {ghost_questions}"
    
    print("✓ No ghost questions test passed")


def test_repair_ghost_questions():
    """Test repair of ghost questions by creating canonical entries."""
    sample_doc = """
## 8. Functional Requirements

*Source: Product Owner (Answer to Q-999)*

## 12. Risks and Open Issues

### Open Questions

#### Q-001: Existing Question

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

### Intake

Some intake content.

---
"""
    
    # Repair ghost question Q-999
    repaired_doc = repair_ghost_questions(sample_doc, ['Q-999'])
    
    # Verify Q-999 was added
    assert '#### Q-999:' in repaired_doc, "Q-999 should be added to Open Questions"
    assert '**Status:** Open' in repaired_doc, "New question should have Open status"
    assert 'Auto-generated from reference' in repaired_doc, "Should indicate auto-generation"
    
    # Verify original Q-001 still exists
    assert '#### Q-001:' in repaired_doc, "Q-001 should still exist"
    
    # Verify Q-999 comes before Intake section
    q999_pos = repaired_doc.find('#### Q-999:')
    intake_pos = repaired_doc.find('### Intake')
    assert q999_pos < intake_pos, "Q-999 should be inserted before Intake section"
    
    # Verify after repair, no ghost questions remain
    is_valid, ghost_questions, _ = _validate_question_references(repaired_doc)
    assert is_valid, f"After repair, document should be valid, but got ghosts: {ghost_questions}"
    
    print("✓ Repair ghost questions test passed")


def test_repair_multiple_ghost_questions():
    """Test repair of multiple ghost questions."""
    sample_doc = """
## 12. Risks and Open Issues

### Open Questions

---

### Intake

Content.

---
"""
    
    # Repair multiple ghost questions
    repaired_doc = repair_ghost_questions(sample_doc, ['Q-005', 'Q-003', 'Q-010'])
    
    # Verify all questions were added in sorted order
    assert '#### Q-003:' in repaired_doc, "Q-003 should be added"
    assert '#### Q-005:' in repaired_doc, "Q-005 should be added"
    assert '#### Q-010:' in repaired_doc, "Q-010 should be added"
    
    # Verify they appear in order
    q003_pos = repaired_doc.find('#### Q-003:')
    q005_pos = repaired_doc.find('#### Q-005:')
    q010_pos = repaired_doc.find('#### Q-010:')
    
    assert q003_pos < q005_pos < q010_pos, "Questions should be in numeric order"
    
    print("✓ Repair multiple ghost questions test passed")


def test_validate_in_context():
    """Test validation in a more realistic context with risks and source attributions."""
    sample_doc = """
## 8. Functional Requirements

**FR-001: Some Requirement**

*Source: Product Owner (Answer to Q-001)*

**FR-002: Another Requirement**

*Source: Product Owner (Answer to Q-002)*

## 12. Risks and Open Issues

### Identified Risks

| R-001 | Risk 1 | Low | Low | **MITIGATED by Q-001 answer** | Owner |
| R-002 | Risk 2 | Medium | High | **Active - Q-003 pending** | Owner |

### Open Questions

#### Q-001: First Question

**Status:** Resolved  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
Question 1.

**Answer:**  
Answered.

**Integration Targets:**  
- Section 8: Functional Requirements

---

#### Q-002: Second Question

**Status:** Resolved  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
Question 2.

**Answer:**  
Answered.

**Integration Targets:**  
- Section 8: Functional Requirements

---
"""
    
    # Q-003 is referenced in risks but doesn't exist
    is_valid, ghost_questions, all_refs = _validate_question_references(sample_doc)
    
    assert not is_valid, "Should detect Q-003 as ghost"
    assert 'Q-003' in ghost_questions, f"Q-003 should be ghost, got {ghost_questions}"
    assert len(ghost_questions) == 1, f"Only Q-003 should be ghost, got {ghost_questions}"
    
    print("✓ Validate in context test passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing Ghost Question Detection and Repair")
    print("=" * 60 + "\n")
    
    try:
        test_get_canonical_question_ids()
        test_find_question_id_references()
        test_detect_ghost_questions()
        test_no_ghost_questions()
        test_repair_ghost_questions()
        test_repair_multiple_ghost_questions()
        test_validate_in_context()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
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
