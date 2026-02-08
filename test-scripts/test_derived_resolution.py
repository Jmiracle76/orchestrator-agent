#!/usr/bin/env python3
"""
Test script to validate integration patch behavior.

This script tests that:
1. Integration patches append content to target sections
2. Open Questions status is not auto-modified without explicit patches
3. Open Questions replacement works in integrate mode when provided
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import apply_patches


def test_integration_appends_without_auto_resolution():
    """Test that integrated sections append content without auto-resolving questions."""
    
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
    
    updated_doc = apply_patches(requirements_doc, agent_output, "integrate")

    # Question should remain Open (no auto-resolution)
    assert '**Status:** Open' in updated_doc, "Question status should remain unchanged without explicit patch"
    assert '**Status:** Resolved' not in updated_doc, "No auto-resolution should be applied"

    # Integrated content should be appended
    assert "New content from answer" in updated_doc, "Integrated content should be appended"
    assert "More content from answer" in updated_doc, "Integrated content should be appended"

    print("✓ Integration append without auto-resolution test passed")


def test_open_questions_replaced_in_integrate_mode():
    """Test that Open Questions can be replaced in integrate mode when provided."""
    
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
    
    agent_output = """
## INTEGRATION_OUTPUT

### INTEGRATED_SECTIONS
- Question ID: Q-001
- Section: ## 8. Functional Requirements
New content from answer (Source: Test Answer Q-001)

### RISKS
No risk changes

### OPEN_QUESTIONS
#### Q-001: Test Question

**Status:** Resolved  
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

### STATUS_UPDATE
Pending - missing integration targets
"""
    
    updated_doc = apply_patches(requirements_doc, agent_output, "integrate")

    # Verify replacement applied
    assert '**Status:** Resolved' in updated_doc, "Open Questions replacement should be applied in integrate mode"
    assert updated_doc.count('#### Q-001:') == 1, "Open Questions should be replaced with updated content"

    print("✓ Open Questions replacement in integrate mode test passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing Derived Resolution Behavior")
    print("=" * 60 + "\n")
    
    try:
        test_integration_appends_without_auto_resolution()
        test_open_questions_replaced_in_integrate_mode()
        
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
