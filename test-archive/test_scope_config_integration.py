#!/usr/bin/env python3
"""
Test script for scope config integration with prior_sections.

This verifies that handler config's scope setting correctly controls
whether prior_sections are passed to LLM methods.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.runner_v2 import WorkflowRunner
from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.models import HandlerConfig
from requirements_automation.utils_io import split_lines


def create_mock_llm():
    """Create a mock LLM client that captures prior_sections argument."""
    llm = Mock()
    
    # Track calls to LLM methods
    llm.generate_open_questions = Mock(return_value=[
        {
            "question": "Test question?",
            "section_target": "section_b",
            "rationale": "Testing"
        }
    ])
    
    llm.integrate_answers = Mock(return_value="Integrated content.")
    
    return llm


def test_scope_current_section_empty_prior():
    """Test that scope: current_section results in empty prior_sections dict."""
    print("Test 1: scope: current_section → prior_sections is empty dict")
    print("=" * 70)
    
    # Create a test document with completed section_a and blank section_b
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
This is completed content in section A.

<!-- section:section_b -->
## Section B
<!-- PLACEHOLDER -->

<!-- section_lock:section_b lock=false -->
---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
"""
    
    lines = split_lines(test_doc)
    mock_llm = create_mock_llm()
    
    # Create handler config with scope: current_section
    handler_config = HandlerConfig(
        section_id="section_b",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements",
        auto_apply_patches="never",
        scope="current_section",
        validation_rules=[],
    )
    
    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["section_a", "section_b"],
    )
    
    # Execute section_b with current_section scope
    state = runner._get_section_state("section_b")
    result = runner._execute_unified_handler("section_b", state, handler_config, dry_run=True)
    
    # Verify that generate_open_questions was called
    if mock_llm.generate_open_questions.called:
        call_kwargs = mock_llm.generate_open_questions.call_args.kwargs
        prior_sections = call_kwargs.get("prior_sections", None)
        
        print(f"  generate_open_questions called with prior_sections: {prior_sections}")
        
        # Verify prior_sections is empty dict
        if prior_sections == {}:
            print("  ✓ prior_sections is empty dict (correct)")
            return True
        else:
            print(f"  ✗ prior_sections should be empty dict, got: {prior_sections}")
            return False
    else:
        print("  ✗ generate_open_questions was not called")
        return False


def test_scope_all_prior_sections_has_content():
    """Test that scope: all_prior_sections results in populated prior_sections dict."""
    print("\nTest 2: scope: all_prior_sections → prior_sections contains prior content")
    print("=" * 70)
    
    # Create a test document with completed section_a and blank section_b
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
This is completed content in section A.

<!-- section:section_b -->
## Section B
<!-- PLACEHOLDER -->

<!-- section_lock:section_b lock=false -->
---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
"""
    
    lines = split_lines(test_doc)
    mock_llm = create_mock_llm()
    
    # Create handler config with scope: all_prior_sections
    handler_config = HandlerConfig(
        section_id="section_b",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
    )
    
    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["section_a", "section_b"],
    )
    
    # Execute section_b with all_prior_sections scope
    state = runner._get_section_state("section_b")
    result = runner._execute_unified_handler("section_b", state, handler_config, dry_run=True)
    
    # Verify that generate_open_questions was called
    if mock_llm.generate_open_questions.called:
        call_kwargs = mock_llm.generate_open_questions.call_args.kwargs
        prior_sections = call_kwargs.get("prior_sections", None)
        
        print(f"  generate_open_questions called with prior_sections: {list(prior_sections.keys()) if prior_sections else None}")
        
        # Verify prior_sections contains section_a
        if isinstance(prior_sections, dict) and "section_a" in prior_sections:
            if "This is completed content in section A." in prior_sections["section_a"]:
                print("  ✓ prior_sections contains section_a with correct content")
                return True
            else:
                print(f"  ✗ prior_sections['section_a'] has wrong content: {prior_sections['section_a']}")
                return False
        else:
            print(f"  ✗ prior_sections should contain section_a, got: {prior_sections}")
            return False
    else:
        print("  ✗ generate_open_questions was not called")
        return False


def test_scope_with_answered_questions():
    """Test that scope affects integrate_answers as well."""
    print("\nTest 3: scope affects integrate_answers when processing answered questions")
    print("=" * 70)
    
    # Create a test document with completed section_a and section_b with answered questions
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
This is completed content in section A.

<!-- section:section_b -->
## Section B
<!-- PLACEHOLDER -->

<!-- section_lock:section_b lock=false -->
---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | What is the requirement? | 2024-01-01 | Performance must be under 200ms | section_b | Open |
"""
    
    lines = split_lines(test_doc)
    mock_llm = create_mock_llm()
    
    # Test with scope: current_section
    handler_config_current = HandlerConfig(
        section_id="section_b",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements",
        auto_apply_patches="never",
        scope="current_section",
        validation_rules=[],
    )
    
    runner = WorkflowRunner(
        lines=lines.copy(),
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["section_a", "section_b"],
    )
    
    state = runner._get_section_state("section_b")
    result = runner._execute_unified_handler("section_b", state, handler_config_current, dry_run=True)
    
    # Check integrate_answers was called with empty prior_sections
    if mock_llm.integrate_answers.called:
        call_kwargs = mock_llm.integrate_answers.call_args.kwargs
        prior_sections = call_kwargs.get("prior_sections", None)
        
        if prior_sections == {}:
            print("  ✓ integrate_answers with scope:current_section has empty prior_sections")
        else:
            print(f"  ✗ integrate_answers should have empty prior_sections, got: {prior_sections}")
            return False
    else:
        print("  ⚠ integrate_answers was not called (might be OK depending on state)")
    
    # Now test with scope: all_prior_sections
    mock_llm.reset_mock()
    
    handler_config_all = HandlerConfig(
        section_id="section_b",
        mode="integrate_then_questions",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
    )
    
    runner2 = WorkflowRunner(
        lines=lines.copy(),
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["section_a", "section_b"],
    )
    
    state2 = runner2._get_section_state("section_b")
    result2 = runner2._execute_unified_handler("section_b", state2, handler_config_all, dry_run=True)
    
    # Check integrate_answers was called with populated prior_sections
    if mock_llm.integrate_answers.called:
        call_kwargs = mock_llm.integrate_answers.call_args.kwargs
        prior_sections = call_kwargs.get("prior_sections", None)
        
        if isinstance(prior_sections, dict) and "section_a" in prior_sections:
            print("  ✓ integrate_answers with scope:all_prior_sections has prior_sections")
            return True
        else:
            print(f"  ✗ integrate_answers should have prior_sections, got: {prior_sections}")
            return False
    else:
        print("  ⚠ integrate_answers was not called (might be OK depending on state)")
        return False


def test_handler_registry_scope_values():
    """Test that handler registry correctly provides scope values."""
    print("\nTest 4: Handler registry provides correct scope values")
    print("=" * 70)
    
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    # Test a regular section (should have scope: current_section)
    config = registry.get_handler_config("requirements", "problem_statement")
    if config.scope == "current_section":
        print(f"  ✓ problem_statement has scope: current_section")
    else:
        print(f"  ✗ problem_statement should have scope: current_section, got: {config.scope}")
        return False
    
    # Test a review gate (should have scope: all_prior_sections)
    config2 = registry.get_handler_config("requirements", "review_gate:coherence_check")
    if config2.scope == "all_prior_sections":
        print(f"  ✓ review_gate:coherence_check has scope: all_prior_sections")
    else:
        print(f"  ✗ review_gate:coherence_check should have scope: all_prior_sections, got: {config2.scope}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Scope Config Integration Test Suite")
    print("=" * 70)
    
    tests = [
        test_scope_current_section_empty_prior,
        test_scope_all_prior_sections_has_content,
        test_scope_with_answered_questions,
        test_handler_registry_scope_values,
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
