#!/usr/bin/env python3
"""
Test script to validate Open Questions parsing.

Ghost question detection and repair is now the agent's responsibility.
This test validates the parsing functions that remain in the invocation script.
"""

import sys
import re
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import _parse_open_questions_section


def test_parse_open_questions():
    """Test extraction of Open Questions from a document."""
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
    
    questions = _parse_open_questions_section(sample_doc)
    q_ids = {q['id'] for q in questions}
    assert q_ids == {'Q-001', 'Q-003'}, f"Expected Q-001 and Q-003, got {q_ids}"
    
    print("✓ Parse Open Questions test passed")


def test_parse_empty_questions():
    """Test parsing when no questions exist."""
    sample_doc = """
## 12. Risks and Open Issues

### Open Questions

[No open questions at this time]

---
"""
    
    questions = _parse_open_questions_section(sample_doc)
    assert len(questions) == 0, f"Expected 0 questions, got {len(questions)}"
    
    print("✓ Parse empty questions test passed")


def test_parse_question_fields():
    """Test that all question fields are parsed correctly."""
    sample_doc = """
### Open Questions

#### Q-001: Detailed Question

**Status:** Open  
**Asked by:** Product Owner  
**Date:** 2026-02-08  

**Question:**  
What is the expected throughput?

**Answer:**  
1000 requests per second.

**Integration Targets:**  
- Section 9: Non-Functional Requirements

---
"""
    
    questions = _parse_open_questions_section(sample_doc)
    assert len(questions) == 1, f"Expected 1 question, got {len(questions)}"
    
    q = questions[0]
    assert q['id'] == 'Q-001', f"Expected Q-001, got {q['id']}"
    assert q['title'] == 'Detailed Question', f"Expected 'Detailed Question', got {q['title']}"
    assert q['status'] == 'Open', f"Expected Open, got {q['status']}"
    assert q['asked_by'] == 'Product Owner', f"Expected Product Owner, got {q['asked_by']}"
    assert '1000 requests per second' in q['answer'], f"Answer not parsed correctly: {q['answer']}"
    assert len(q['targets']) == 1, f"Expected 1 target, got {len(q['targets'])}"
    
    print("✓ Parse question fields test passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing Open Questions Parsing")
    print("=" * 60 + "\n")
    
    try:
        test_parse_open_questions()
        test_parse_empty_questions()
        test_parse_question_fields()
        
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
