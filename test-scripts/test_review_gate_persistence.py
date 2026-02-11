#!/usr/bin/env python3
"""
Test script for review gate persistence and skip logic fixes.

This script validates the two bug fixes:
1. Review gate results are persisted using write_review_gate_result()
2. Review gates with 'passed' status are skipped on subsequent runs
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.models import (
    HandlerConfig, 
    ReviewIssue, 
    ReviewResult,
    WorkflowResult
)
from requirements_automation.review_gate_handler import ReviewGateHandler
from requirements_automation.runner_v2 import WorkflowRunner
from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.config import REVIEW_GATE_RESULT_RE


def create_test_document_with_gate() -> list:
    """Create a test document with a review gate in workflow."""
    return [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- meta:doc_format version=\"1.0\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:test_gate",
        "requirements",
        "-->",
        "",
        "# Test Requirements Document",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "This is a complete test problem statement.",
        "",
        "<!-- section:requirements -->",
        "## Requirements",
        "<!-- PLACEHOLDER -->",
        "",
    ]


def create_test_document_with_passed_gate() -> list:
    """Create a test document with a review gate that already passed."""
    return [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- meta:doc_format version=\"1.0\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:test_gate",
        "requirements",
        "-->",
        "<!-- review_gate_result:review_gate:test_gate status=passed issues=0 warnings=0 -->",
        "",
        "# Test Requirements Document",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "This is a complete test problem statement.",
        "",
        "<!-- section:requirements -->",
        "## Requirements",
        "<!-- PLACEHOLDER -->",
        "",
    ]


class MockLLM:
    """Mock LLM client for testing."""
    def perform_review(self, gate_id, doc_type, section_contents, llm_profile=None, validation_rules=None):
        """Mock review that always passes with no issues."""
        return {
            "summary": "All sections look good",
            "issues": [],
            "patches": []
        }
    
    def generate_open_questions(self, section_id, context, llm_profile=None):
        """Mock question generation."""
        return []


def test_review_gate_result_persistence():
    """
    Test Fix 1: Verify that review gate results are persisted using write_review_gate_result().
    """
    print("\n" + "=" * 70)
    print("Test 1: Review Gate Result Persistence")
    print("=" * 70)
    
    lines = create_test_document_with_gate()
    
    # Create mock handler registry with review gate config
    class MockHandlerRegistry:
        def get_handler_config(self, doc_type, target_id):
            if target_id == "review_gate:test_gate":
                return HandlerConfig(
                    section_id=target_id,
                    mode="review_gate",
                    output_format="review_result",
                    subsections=False,
                    dedupe=False,
                    preserve_headers=[],
                    sanitize_remove=[],
                    llm_profile="default",
                    auto_apply_patches="never",
                    scope="all_prior_sections",
                    validation_rules=[]
                )
            return HandlerConfig(
                section_id=target_id,
                mode="placeholder",
                output_format="structured",
                subsections=False,
                dedupe=False,
                preserve_headers=[],
                sanitize_remove=[],
                llm_profile="default",
                auto_apply_patches="never",
                scope="",
                validation_rules=[]
            )
    
    # Create WorkflowRunner
    runner = WorkflowRunner(
        lines=lines.copy(),
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=["problem_statement", "review_gate:test_gate", "requirements"],
        handler_registry=MockHandlerRegistry()
    )
    
    # Run once - should execute the review gate
    result = runner.run_once()
    
    # Verify result
    print(f"\nResult from run_once():")
    print(f"  - target_id: {result.target_id}")
    print(f"  - action_taken: {result.action_taken}")
    print(f"  - changed: {result.changed}")
    print(f"  - blocked: {result.blocked}")
    
    if result.target_id != "review_gate:test_gate":
        print(f"  ✗ Expected target_id='review_gate:test_gate', got '{result.target_id}'")
        return False
    
    if result.action_taken != "review_gate":
        print(f"  ✗ Expected action_taken='review_gate', got '{result.action_taken}'")
        return False
    
    # Fix 1: Verify that changed=True (marker was written)
    if not result.changed:
        print(f"  ✗ Expected changed=True (marker should be written), got changed=False")
        return False
    
    print(f"  ✓ Review gate executed with changed=True")
    
    # Verify marker exists in document
    marker_found = False
    print(f"\n  Checking document for result marker...")
    print(f"  Document has {len(runner.lines)} lines")
    for i, line in enumerate(runner.lines):
        if "review_gate" in line.lower():
            print(f"  Line {i}: {line.strip()}")
        m = REVIEW_GATE_RESULT_RE.search(line)
        if m:
            gate_id = m.group("gate_id")
            status = m.group("status")
            print(f"  Found marker: gate_id={gate_id}, status={status}")
            if gate_id == "review_gate:test_gate":
                marker_found = True
                print(f"  ✓ Result marker found in document: status={status}")
                if status != "passed":
                    print(f"  ✗ Expected status='passed', got '{status}'")
                    return False
                break
    
    if not marker_found:
        print(f"  ✗ No result marker found in document")
        # Debug: print first 20 lines to see what's in the document
        print(f"\n  First 20 lines of document:")
        for i, line in enumerate(runner.lines[:20]):
            print(f"    {i}: {line.rstrip()}")
        return False
    
    print("\n✓ Test 1 PASSED: Review gate result is correctly persisted")
    return True


def test_review_gate_skip_logic():
    """
    Test Fix 2: Verify that review gates with 'passed' status are skipped on subsequent runs.
    """
    print("\n" + "=" * 70)
    print("Test 2: Review Gate Skip Logic")
    print("=" * 70)
    
    lines = create_test_document_with_passed_gate()
    
    # Verify marker exists at the start
    marker_found = False
    for line in lines:
        m = REVIEW_GATE_RESULT_RE.search(line)
        if m and m.group("gate_id") == "review_gate:test_gate" and m.group("status") == "passed":
            marker_found = True
            print(f"  ✓ Document has existing 'passed' marker")
            break
    
    if not marker_found:
        print(f"  ✗ Test setup error: No passed marker found in test document")
        return False
    
    # Create mock handler registry
    class MockHandlerRegistry:
        def __init__(self):
            self.review_called = False
        
        def get_handler_config(self, doc_type, target_id):
            if target_id == "review_gate:test_gate":
                return HandlerConfig(
                    section_id=target_id,
                    mode="review_gate",
                    output_format="review_result",
                    subsections=False,
                    dedupe=False,
                    preserve_headers=[],
                    sanitize_remove=[],
                    llm_profile="default",
                    auto_apply_patches="never",
                    scope="all_prior_sections",
                    validation_rules=[]
                )
            return HandlerConfig(
                section_id=target_id,
                mode="placeholder",
                output_format="structured",
                subsections=False,
                dedupe=False,
                preserve_headers=[],
                sanitize_remove=[],
                llm_profile="default",
                auto_apply_patches="never",
                scope="",
                validation_rules=[]
            )
    
    # Create MockLLM that tracks if perform_review is called
    class TrackingMockLLM:
        def __init__(self):
            self.review_called = False
        
        def perform_review(self, gate_id, doc_type, section_contents, llm_profile=None, validation_rules=None):
            self.review_called = True
            return {
                "summary": "All sections look good",
                "issues": [],
                "patches": []
            }
        
        def generate_open_questions(self, section_id, context, llm_profile=None):
            return []
    
    mock_llm = TrackingMockLLM()
    
    # Create WorkflowRunner
    runner = WorkflowRunner(
        lines=lines.copy(),
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["problem_statement", "review_gate:test_gate", "requirements"],
        handler_registry=MockHandlerRegistry()
    )
    
    # Run once - should skip the review gate and move to requirements
    result = runner.run_once()
    
    # Verify result
    print(f"\nResult from run_once():")
    print(f"  - target_id: {result.target_id}")
    print(f"  - action_taken: {result.action_taken}")
    
    # Fix 2: Verify that the gate was skipped (next target is 'requirements')
    if result.target_id == "review_gate:test_gate":
        print(f"  ✗ Review gate was NOT skipped (target_id is still the gate)")
        return False
    
    if result.target_id != "requirements":
        print(f"  ✗ Expected to skip gate and process 'requirements', got '{result.target_id}'")
        return False
    
    print(f"  ✓ Review gate was skipped, moved to next target: {result.target_id}")
    
    # Verify that perform_review was NOT called
    if mock_llm.review_called:
        print(f"  ✗ perform_review was called (gate should have been skipped)")
        return False
    
    print(f"  ✓ perform_review was NOT called (gate was properly skipped)")
    
    print("\n✓ Test 2 PASSED: Review gate with 'passed' status is correctly skipped")
    return True


def test_review_gate_skip_only_if_passed():
    """
    Test that review gates with 'failed' status are NOT skipped and re-executed.
    """
    print("\n" + "=" * 70)
    print("Test 3: Review Gate Re-execution When Failed")
    print("=" * 70)
    
    # Document with a failed gate marker
    lines = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- meta:doc_format version=\"1.0\" -->",
        "<!-- workflow:order",
        "problem_statement",
        "review_gate:test_gate",
        "requirements",
        "-->",
        "<!-- review_gate_result:review_gate:test_gate status=failed issues=1 warnings=0 -->",
        "",
        "# Test Requirements Document",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "This is a test problem statement.",
        "",
        "<!-- section:requirements -->",
        "## Requirements",
        "<!-- PLACEHOLDER -->",
        "",
    ]
    
    # Create mock handler registry
    class MockHandlerRegistry:
        def get_handler_config(self, doc_type, target_id):
            if target_id == "review_gate:test_gate":
                return HandlerConfig(
                    section_id=target_id,
                    mode="review_gate",
                    output_format="review_result",
                    subsections=False,
                    dedupe=False,
                    preserve_headers=[],
                    sanitize_remove=[],
                    llm_profile="default",
                    auto_apply_patches="never",
                    scope="all_prior_sections",
                    validation_rules=[]
                )
            return HandlerConfig(
                section_id=target_id,
                mode="placeholder",
                output_format="structured",
                subsections=False,
                dedupe=False,
                preserve_headers=[],
                sanitize_remove=[],
                llm_profile="default",
                auto_apply_patches="never",
                scope="",
                validation_rules=[]
            )
    
    # Create MockLLM that tracks if perform_review is called
    class TrackingMockLLM:
        def __init__(self):
            self.review_called = False
        
        def perform_review(self, gate_id, doc_type, section_contents, llm_profile=None, validation_rules=None):
            self.review_called = True
            # This time return a passing review
            return {
                "summary": "All sections look good now",
                "issues": [],
                "patches": []
            }
        
        def generate_open_questions(self, section_id, context, llm_profile=None):
            return []
    
    mock_llm = TrackingMockLLM()
    
    # Create WorkflowRunner
    runner = WorkflowRunner(
        lines=lines.copy(),
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["problem_statement", "review_gate:test_gate", "requirements"],
        handler_registry=MockHandlerRegistry()
    )
    
    # Run once - should re-execute the failed review gate
    result = runner.run_once()
    
    # Verify result
    print(f"\nResult from run_once():")
    print(f"  - target_id: {result.target_id}")
    print(f"  - action_taken: {result.action_taken}")
    
    # Verify that the gate was NOT skipped (target is still the gate)
    if result.target_id != "review_gate:test_gate":
        print(f"  ✗ Expected to re-execute 'review_gate:test_gate', got '{result.target_id}'")
        return False
    
    print(f"  ✓ Failed review gate was re-executed")
    
    # Verify that perform_review WAS called
    if not mock_llm.review_called:
        print(f"  ✗ perform_review was NOT called (gate should have been re-executed)")
        return False
    
    print(f"  ✓ perform_review was called (gate was properly re-executed)")
    
    print("\n✓ Test 3 PASSED: Review gate with 'failed' status is correctly re-executed")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("REVIEW GATE PERSISTENCE AND SKIP LOGIC TESTS")
    print("=" * 70)
    
    all_passed = True
    
    # Test 1: Result persistence
    try:
        if not test_review_gate_result_persistence():
            all_passed = False
    except Exception as e:
        print(f"\n✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 2: Skip logic for passed gates
    try:
        if not test_review_gate_skip_logic():
            all_passed = False
    except Exception as e:
        print(f"\n✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 3: Re-execution for failed gates
    try:
        if not test_review_gate_skip_only_if_passed():
            all_passed = False
    except Exception as e:
        print(f"\n✗ Test 3 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
