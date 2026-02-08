#!/usr/bin/env python3
"""
Test script to validate required section enforcement helpers.

Ghost question detection and repair is now the agent's responsibility.
This test validates the minimal helpers that remain in the invocation script.
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import missing_required_sections, has_answered_questions


def test_missing_required_sections():
    """Test that missing required sections are detected."""
    sample_doc = "## 1. Document Control\n"
    missing = missing_required_sections(sample_doc)
    assert "## 1. Document Control" not in missing, "Existing section should not be missing"
    assert "## 2. Problem Statement" in missing, "Missing section should be reported"
    print("✓ Required section detection test passed")


def test_has_answered_questions():
    """Test detection of answered questions for mode selection."""
    placeholders = ["[Awaiting response]", "[awaiting answer]", "[pending]", "[tbd]"]
    for placeholder in placeholders:
        unanswered_doc = f"""
### Open Questions

#### Q-001: Test Question

**Answer:**
{placeholder}

**Integration Targets:**
- Section 8: Functional Requirements
"""
        assert not has_answered_questions(unanswered_doc), (
            f"Placeholder answer '{placeholder}' should not trigger integrate mode"
        )

    answered_doc = """
### Open Questions

#### Q-002: Test Question

**Answer:**
Provide a concrete answer.

**Integration Targets:**
- Section 8: Functional Requirements
"""

    assert has_answered_questions(answered_doc), "Concrete answers should trigger integrate mode"
    print("✓ Answered question detection test passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing Open Questions Parsing")
    print("=" * 60 + "\n")
    
    try:
        test_missing_required_sections()
        test_has_answered_questions()
        
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
