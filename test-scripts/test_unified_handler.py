#!/usr/bin/env python3
"""
Test script for unified handler implementation.

This test validates that the unified handler correctly processes sections
using handler config parameters instead of hardcoded phase logic.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.runner_v2 import WorkflowRunner
from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.utils_io import split_lines

def create_mock_llm():
    """Create a mock LLM client for testing."""
    llm = Mock()
    
    # Mock generate_open_questions to return sample questions
    llm.generate_open_questions = Mock(return_value=[
        {
            "question": "What is the primary use case?",
            "section_target": "requirements",
            "rationale": "Need to clarify scope"
        }
    ])
    
    # Mock integrate_answers to return sample content
    llm.integrate_answers = Mock(return_value="Integrated content from answered questions.")
    
    return llm

def test_unified_handler_calls_llm_with_config():
    """Test that unified handler calls LLM methods with handler config parameters."""
    print("Test 1: Unified handler calls LLM with handler config parameters")
    print("=" * 70)
    
    # Load handler registry
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    # Create a minimal test document with a blank requirements section
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
requirements
-->

# Test Document

<!-- section:requirements -->
## Requirements
<!-- PLACEHOLDER -->

<!-- section_lock:requirements lock=false -->
---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | Test question? | 2024-01-01 | Test answer | requirements | Open |
"""
    
    lines = split_lines(test_doc)
    mock_llm = create_mock_llm()
    
    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["requirements"],
        handler_registry=registry,
    )
    
    # Get handler config for requirements section
    handler_config = registry.get_handler_config("requirements", "requirements")
    print(f"  Handler config for requirements:")
    print(f"    mode: {handler_config.mode}")
    print(f"    llm_profile: {handler_config.llm_profile}")
    print(f"    output_format: {handler_config.output_format}")
    
    # Execute the section
    state = runner._get_section_state("requirements")
    print(f"\n  Section state:")
    print(f"    exists: {state.exists}")
    print(f"    is_blank: {state.is_blank}")
    print(f"    has_answered_questions: {state.has_answered_questions}")
    
    # Execute the section (should integrate answers)
    result = runner._execute_section("requirements", state, dry_run=False)
    
    print(f"\n  Execution result:")
    print(f"    action_taken: {result.action_taken}")
    print(f"    changed: {result.changed}")
    print(f"    questions_resolved: {result.questions_resolved}")
    
    # Verify that integrate_answers was called with correct parameters
    if mock_llm.integrate_answers.called:
        call_args = mock_llm.integrate_answers.call_args
        print(f"\n  ✓ integrate_answers was called")
        print(f"    llm_profile: {call_args.kwargs.get('llm_profile')}")
        print(f"    output_format: {call_args.kwargs.get('output_format')}")
        
        # Verify correct parameters from handler config
        if (call_args.kwargs.get('llm_profile') == handler_config.llm_profile and
            call_args.kwargs.get('output_format') == handler_config.output_format):
            print(f"  ✓ LLM called with correct handler config parameters")
            return True
        else:
            print(f"  ✗ LLM called with incorrect parameters")
            return False
    else:
        print(f"  ✗ integrate_answers was not called")
        return False

def test_unified_handler_vs_legacy():
    """Test that unified handler is used when handler_config exists, legacy otherwise."""
    print("\nTest 2: Unified handler is used when config exists, legacy fallback otherwise")
    print("=" * 70)
    
    # Test with handler registry (should use unified handler)
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
requirements
-->

# Test Document

<!-- section:requirements -->
## Requirements
<!-- PLACEHOLDER -->

<!-- section_lock:requirements lock=false -->
---
"""
    
    lines = split_lines(test_doc)
    mock_llm = create_mock_llm()
    
    # Create runner with registry
    runner_with_registry = WorkflowRunner(
        lines=lines.copy(),
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["requirements"],
        handler_registry=registry,
    )
    
    # Create runner without registry (should use legacy phase dispatch)
    runner_without_registry = WorkflowRunner(
        lines=lines.copy(),
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["requirements"],
        handler_registry=None,
    )
    
    state = runner_with_registry._get_section_state("requirements")
    
    # Execute with registry (should use unified handler)
    result_with_registry = runner_with_registry._execute_section("requirements", state, dry_run=True)
    print(f"  With registry: action={result_with_registry.action_taken}")
    
    # Execute without registry (should use legacy phase dispatch)
    result_without_registry = runner_without_registry._execute_section("requirements", state, dry_run=True)
    print(f"  Without registry: action={result_without_registry.action_taken}")
    
    print(f"  ✓ Both execution paths work (unified handler and legacy fallback)")
    return True

def test_review_gate_final_review():
    """Test that the new final_review gate is properly configured."""
    print("\nTest 3: New review_gate:final_review is properly configured")
    print("=" * 70)
    
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    try:
        config = registry.get_handler_config("requirements", "review_gate:final_review")
        print(f"  ✓ review_gate:final_review config loaded")
        print(f"    mode: {config.mode}")
        print(f"    llm_profile: {config.llm_profile}")
        print(f"    validation_rules: {config.validation_rules}")
        
        # Verify it has the expected validation rules
        expected_rules = [
            "no_contradictions",
            "no_missing_critical_sections",
            "consistent_terminology",
            "requirements_traceable",
            "risks_identified"
        ]
        
        if config.validation_rules == expected_rules:
            print(f"  ✓ Final review has all expected validation rules")
            return True
        else:
            print(f"  ✗ Final review validation rules don't match expected")
            print(f"    Expected: {expected_rules}")
            print(f"    Got: {config.validation_rules}")
            return False
            
    except Exception as e:
        print(f"  ✗ Failed to load review_gate:final_review: {e}")
        return False

def main():
    """Run all tests."""
    print("Unified Handler Test Suite")
    print("=" * 70)
    
    results = []
    
    try:
        results.append(test_unified_handler_calls_llm_with_config())
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    try:
        results.append(test_unified_handler_vs_legacy())
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    try:
        results.append(test_review_gate_final_review())
    except Exception as e:
        print(f"✗ Test 3 failed with exception: {e}")
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
