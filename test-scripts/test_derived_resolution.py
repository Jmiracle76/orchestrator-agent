#!/usr/bin/env python3
"""
Test script to validate derived resolution behavior.

This script tests that:
1. Questions are NOT marked as "Resolved" by agents directly
2. Resolution is derived mechanically based on successful integration
3. Failed integration prevents resolution
"""

import sys
import re
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import _parse_open_questions_section, apply_patches


def test_parse_questions():
    """Test that we can parse questions and their integration targets."""
    sample_doc = """
### Open Questions

#### Q-001: Test Question

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is a test question.

**Answer:**  
This is a test answer.

**Integration Targets:**  
- Section 8: Functional Requirements
- Section 9: Non-Functional Requirements

---
"""
    
    questions = _parse_open_questions_section(sample_doc)
    assert len(questions) == 1, f"Expected 1 question, got {len(questions)}"
    
    q = questions[0]
    assert q['id'] == 'Q-001', f"Expected Q-001, got {q['id']}"
    assert q['status'] == 'Open', f"Expected Open status, got {q['status']}"
    assert len(q['targets']) == 2, f"Expected 2 targets, got {len(q['targets'])}"
    assert 'Section 8: Functional Requirements' in q['targets']
    assert 'Section 9: Non-Functional Requirements' in q['targets']
    
    print("✓ Parse questions test passed")


def test_resolution_when_all_targets_integrated():
    """Test that questions are marked Resolved when all targets are successfully integrated."""
    
    requirements_doc = """
## 8. Functional Requirements

Existing content.

## 9. Non-Functional Requirements

Existing content.

## 12. Risks and Open Issues

### Open Questions

#### Q-001: Test Question

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is a test question.

**Answer:**  
This is a test answer.

**Integration Targets:**  
- Section 8: Functional Requirements
- Section 9: Non-Functional Requirements

---
"""
    
    # Agent output with both targets integrated
    agent_output = """
## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Question ID: Q-001
- Section: ## 8. Functional Requirements
New content from answer (Source: Test Answer Q-001)

- Question ID: Q-001
- Section: ## 9. Non-Functional Requirements
More content from answer (Source: Test Answer Q-001)

### RISKS
No risk changes

### STATUS_UPDATE
Ready for approval
"""
    
    updated_doc, integration_info = apply_patches(requirements_doc, agent_output, "integrate")
    
    # Verify question was marked as Resolved
    assert '**Status:** Resolved' in updated_doc, "Question should be marked as Resolved when all targets are integrated"
    assert '**Status:** Open' not in updated_doc, "Question should not have Open status after integration"
    
    # Verify integration info
    assert 'Q-001' in integration_info['resolved'], f"Q-001 should be in resolved list: {integration_info}"
    assert 'Q-001' not in integration_info['unresolved'], f"Q-001 should not be in unresolved: {integration_info}"
    
    print("✓ Resolution when all targets integrated test passed")


def test_no_resolution_when_targets_missing():
    """Test that questions remain Open when not all targets are integrated."""
    
    requirements_doc = """
## 8. Functional Requirements

Existing content.

## 9. Non-Functional Requirements

Existing content.

## 12. Risks and Open Issues

### Open Questions

#### Q-001: Test Question

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is a test question.

**Answer:**  
This is a test answer.

**Integration Targets:**  
- Section 8: Functional Requirements
- Section 9: Non-Functional Requirements

---
"""
    
    # Agent output with only ONE target integrated (missing Section 9)
    agent_output = """
## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Question ID: Q-001
- Section: ## 8. Functional Requirements
New content from answer (Source: Test Answer Q-001)

### RISKS
No risk changes

### STATUS_UPDATE
Pending - missing integration targets
"""
    
    updated_doc, integration_info = apply_patches(requirements_doc, agent_output, "integrate")
    
    # Verify question was NOT marked as Resolved
    assert '**Status:** Open' in updated_doc, "Question should remain Open when not all targets are integrated"
    assert updated_doc.count('**Status:** Resolved') == 0, "Question should not be marked as Resolved when targets are missing"
    
    # Verify integration info
    assert 'Q-001' not in integration_info['resolved'], f"Q-001 should not be in resolved list: {integration_info}"
    assert 'Q-001' in integration_info['unresolved'], f"Q-001 should be in unresolved: {integration_info}"
    
    failed_targets = integration_info['unresolved']['Q-001']
    assert 'Section 9: Non-Functional Requirements' in failed_targets, f"Missing target should be tracked: {failed_targets}"
    
    print("✓ No resolution when targets missing test passed")


def test_multiple_questions_partial_integration():
    """Test that only questions with all targets integrated are resolved."""
    
    requirements_doc = """
## 8. Functional Requirements

Existing content.

## 9. Non-Functional Requirements

Existing content.

## 12. Risks and Open Issues

### Open Questions

#### Q-001: Test Question 1

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is test question 1.

**Answer:**  
This is answer 1.

**Integration Targets:**  
- Section 8: Functional Requirements

---

#### Q-002: Test Question 2

**Status:** Open  
**Asked by:** Test  
**Date:** 2026-02-08  

**Question:**  
This is test question 2.

**Answer:**  
This is answer 2.

**Integration Targets:**  
- Section 8: Functional Requirements
- Section 9: Non-Functional Requirements

---
"""
    
    # Agent output: Q-001 fully integrated, Q-002 partially integrated
    agent_output = """
## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Question ID: Q-001
- Section: ## 8. Functional Requirements
Content from answer 1 (Source: Test Answer Q-001)

- Question ID: Q-002
- Section: ## 8. Functional Requirements
Content from answer 2 (Source: Test Answer Q-002)

### RISKS
No risk changes

### STATUS_UPDATE
Partial integration completed
"""
    
    updated_doc, integration_info = apply_patches(requirements_doc, agent_output, "integrate")
    
    # Q-001 should be resolved (all targets integrated)
    # Q-002 should remain open (missing Section 9)
    
    # Count Resolved statuses - should be 1 (only Q-001)
    resolved_count = updated_doc.count('**Status:** Resolved')
    assert resolved_count == 1, f"Expected 1 resolved question, found {resolved_count}"
    
    # Verify integration info
    assert 'Q-001' in integration_info['resolved'], f"Q-001 should be resolved: {integration_info}"
    assert 'Q-002' in integration_info['unresolved'], f"Q-002 should be unresolved: {integration_info}"
    
    print("✓ Multiple questions partial integration test passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing Derived Resolution Behavior")
    print("=" * 60 + "\n")
    
    try:
        test_parse_questions()
        test_resolution_when_all_targets_integrated()
        test_no_resolution_when_targets_missing()
        test_multiple_questions_partial_integration()
        
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
