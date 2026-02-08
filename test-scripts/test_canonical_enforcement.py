#!/usr/bin/env python3
"""
Integration test for canonical question enforcement.

This test validates that:
1. Agent cannot create duplicate Question IDs
2. Patch application correctly handles question deduplication
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import apply_patches


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


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Integration Tests: Canonical Question Enforcement")
    print("=" * 60 + "\n")
    
    try:
        test_agent_duplicate_prevention()
        
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
