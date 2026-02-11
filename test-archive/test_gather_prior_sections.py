#!/usr/bin/env python3
"""
Test script for _gather_prior_sections() method in WorkflowRunner.

This verifies that prior completed sections are correctly gathered and incomplete
sections are excluded.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.runner_v2 import WorkflowRunner
from requirements_automation.config import PLACEHOLDER_TOKEN


def test_gather_prior_sections_basic():
    """Test gathering prior sections with a simple workflow."""
    print("Test 1: Basic prior sections gathering...")
    
    # Create a simple document with 3 sections
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "section_a",
        "section_b",
        "section_c",
        "-->",
        "",
        "<!-- section:section_a -->",
        "## Section A",
        "This is section A content.",
        "",
        "<!-- section:section_b -->",
        "## Section B",
        "This is section B content.",
        "",
        "<!-- section:section_c -->",
        "## Section C",
        f"{PLACEHOLDER_TOKEN}",
        "",
    ]
    
    # Mock LLM (won't be used in this test)
    class MockLLM:
        pass
    
    runner = WorkflowRunner(
        lines=lines,
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=["section_a", "section_b", "section_c"]
    )
    
    # Gather prior sections for section_c
    prior = runner._gather_prior_sections("section_c")
    
    # Should include section_a and section_b (both complete)
    if len(prior) != 2:
        print(f"  ✗ Expected 2 prior sections, got {len(prior)}")
        return False
    
    if "section_a" not in prior:
        print("  ✗ section_a not in prior sections")
        return False
    
    if "section_b" not in prior:
        print("  ✗ section_b not in prior sections")
        return False
    
    if "This is section A content." not in prior["section_a"]:
        print("  ✗ section_a content incorrect")
        return False
    
    if "This is section B content." not in prior["section_b"]:
        print("  ✗ section_b content incorrect")
        return False
    
    print("  ✓ Basic prior sections gathering works")
    return True


def test_gather_prior_sections_skips_incomplete():
    """Test that incomplete sections are excluded."""
    print("\nTest 2: Skipping incomplete sections...")
    
    # Create document where section_b has a placeholder
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "section_a",
        "section_b",
        "section_c",
        "-->",
        "",
        "<!-- section:section_a -->",
        "## Section A",
        "This is section A content.",
        "",
        "<!-- section:section_b -->",
        "## Section B",
        f"{PLACEHOLDER_TOKEN}",
        "",
        "<!-- section:section_c -->",
        "## Section C",
        f"{PLACEHOLDER_TOKEN}",
        "",
    ]
    
    class MockLLM:
        pass
    
    runner = WorkflowRunner(
        lines=lines,
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=["section_a", "section_b", "section_c"]
    )
    
    # Gather prior sections for section_c
    prior = runner._gather_prior_sections("section_c")
    
    # Should only include section_a (section_b has placeholder)
    if len(prior) != 1:
        print(f"  ✗ Expected 1 prior section, got {len(prior)}")
        return False
    
    if "section_a" not in prior:
        print("  ✗ section_a not in prior sections")
        return False
    
    if "section_b" in prior:
        print("  ✗ section_b should not be in prior sections (has placeholder)")
        return False
    
    print("  ✓ Incomplete sections correctly excluded")
    return True


def test_gather_prior_sections_skips_review_gates():
    """Test that review gates are skipped."""
    print("\nTest 3: Skipping review gates...")
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "section_a",
        "review_gate:phase1",
        "section_b",
        "-->",
        "",
        "<!-- section:section_a -->",
        "## Section A",
        "This is section A content.",
        "",
        "<!-- section:section_b -->",
        "## Section B",
        f"{PLACEHOLDER_TOKEN}",
        "",
    ]
    
    class MockLLM:
        pass
    
    runner = WorkflowRunner(
        lines=lines,
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=["section_a", "review_gate:phase1", "section_b"]
    )
    
    # Gather prior sections for section_b
    prior = runner._gather_prior_sections("section_b")
    
    # Should only include section_a (review_gate:phase1 is skipped)
    if len(prior) != 1:
        print(f"  ✗ Expected 1 prior section, got {len(prior)}")
        return False
    
    if "section_a" not in prior:
        print("  ✗ section_a not in prior sections")
        return False
    
    if "review_gate:phase1" in prior:
        print("  ✗ review gate should not be in prior sections")
        return False
    
    print("  ✓ Review gates correctly excluded")
    return True


def test_gather_prior_sections_empty_for_first():
    """Test that first section has no prior sections."""
    print("\nTest 4: Empty prior sections for first target...")
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "section_a",
        "section_b",
        "-->",
        "",
        "<!-- section:section_a -->",
        "## Section A",
        f"{PLACEHOLDER_TOKEN}",
        "",
        "<!-- section:section_b -->",
        "## Section B",
        f"{PLACEHOLDER_TOKEN}",
        "",
    ]
    
    class MockLLM:
        pass
    
    runner = WorkflowRunner(
        lines=lines,
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=["section_a", "section_b"]
    )
    
    # Gather prior sections for section_a (first in workflow)
    prior = runner._gather_prior_sections("section_a")
    
    # Should be empty dict
    if len(prior) != 0:
        print(f"  ✗ Expected empty dict, got {len(prior)} sections")
        return False
    
    print("  ✓ First section has empty prior sections")
    return True


def test_gather_prior_sections_with_open_questions():
    """Test that sections with open questions are excluded."""
    print("\nTest 5: Excluding sections with open questions...")
    
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- workflow:order",
        "section_a",
        "section_b",
        "section_c",
        "-->",
        "",
        "<!-- section:section_a -->",
        "## Section A",
        "This is section A content.",
        "",
        "<!-- section:section_b -->",
        "## Section B",
        "This is section B content.",
        "",
        "<!-- table:open_questions -->",
        "| Question ID | Question | Date | Answer | Section Target | Resolution Status |",
        "| --- | --- | --- | --- | --- | --- |",
        "| Q1 | Test question? | 2024-01-01 | - | section_b | Open |",
        "",
        "<!-- section:section_c -->",
        "## Section C",
        f"{PLACEHOLDER_TOKEN}",
        "",
    ]
    
    class MockLLM:
        pass
    
    runner = WorkflowRunner(
        lines=lines,
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=["section_a", "section_b", "section_c"]
    )
    
    # Gather prior sections for section_c
    prior = runner._gather_prior_sections("section_c")
    
    # Should only include section_a (section_b has open questions)
    if len(prior) != 1:
        print(f"  ✗ Expected 1 prior section, got {len(prior)}")
        return False
    
    if "section_a" not in prior:
        print("  ✗ section_a not in prior sections")
        return False
    
    if "section_b" in prior:
        print("  ✗ section_b should not be in prior sections (has open questions)")
        return False
    
    print("  ✓ Sections with open questions correctly excluded")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Gather Prior Sections Test Suite")
    print("=" * 70)
    
    tests = [
        test_gather_prior_sections_basic,
        test_gather_prior_sections_skips_incomplete,
        test_gather_prior_sections_skips_review_gates,
        test_gather_prior_sections_empty_for_first,
        test_gather_prior_sections_with_open_questions,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
