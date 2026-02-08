#!/usr/bin/env python3
"""
Integration test for deterministic Open Questions patching.

This test validates that:
1. Open Questions content is replaced deterministically
2. Patch application does not attempt to deduplicate entries
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import apply_patches


def test_open_questions_replacement():
    """Test that Open Questions content is replaced deterministically."""
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
    
    # Agent output replacing the Open Questions section
    agent_output = """
## REVIEW_OUTPUT

### STATUS_UPDATE
Pending - Revisions Required

### RISKS
No new risks identified

### OPEN_QUESTIONS
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
    updated_doc = apply_patches(requirements_doc, agent_output, "review")

    # Q-001 should be removed since the section is replaced
    assert '#### Q-001:' not in updated_doc, "Q-001 should be replaced by new content"

    # Q-002 should be present
    assert '#### Q-002:' in updated_doc, "Q-002 should be present after replacement"

    print("✓ Open Questions replacement test passed")


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Integration Tests: Canonical Question Enforcement")
    print("=" * 60 + "\n")
    
    try:
        test_open_questions_replacement()
        
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
