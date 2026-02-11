#!/usr/bin/env python3
"""
Test script for prior_sections support in LLMClient.

This verifies that generate_open_questions() and integrate_answers()
correctly include document context when prior_sections is provided.
"""
import sys
from pathlib import Path
from unittest.mock import patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.llm import LLMClient
from requirements_automation.models import OpenQuestion


def test_generate_questions_with_prior_sections():
    """Test that generate_open_questions includes prior sections in prompt."""
    print("Test 1: generate_open_questions with prior_sections...")
    
    try:
        with patch('requirements_automation.llm.os.getenv', return_value='fake_key'):
            with patch('requirements_automation.llm.LLMClient._make_client'):
                client = LLMClient()
                
                # Mock the _call method to capture the prompt
                captured_prompt = None
                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return '{"questions": []}'
                
                client._call = mock_call
                
                # Call with prior_sections
                prior = {
                    "problem_statement": "This is a problem statement section.",
                    "goals_objectives": "These are the goals and objectives."
                }
                
                client.generate_open_questions(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    llm_profile="requirements",
                    prior_sections=prior
                )
                
                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False
                
                # Verify Document Context header is present
                if "## Document Context (completed sections)" not in captured_prompt:
                    print("  ✗ Document Context header not in prompt")
                    return False
                
                # Verify section headers are present
                if "### problem_statement" not in captured_prompt:
                    print("  ✗ problem_statement section not in prompt")
                    return False
                
                if "### goals_objectives" not in captured_prompt:
                    print("  ✗ goals_objectives section not in prompt")
                    return False
                
                # Verify section content is present
                if "This is a problem statement section." not in captured_prompt:
                    print("  ✗ problem_statement content not in prompt")
                    return False
                
                if "These are the goals and objectives." not in captured_prompt:
                    print("  ✗ goals_objectives content not in prompt")
                    return False
                
                # Verify task instruction mentions document context
                if "Given the document context above" not in captured_prompt:
                    print("  ✗ Task instruction doesn't reference document context")
                    return False
                
                print("  ✓ Prior sections correctly injected into prompt")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generate_questions_without_prior_sections():
    """Test that generate_open_questions works without prior sections."""
    print("\nTest 2: generate_open_questions without prior_sections...")
    
    try:
        with patch('requirements_automation.llm.os.getenv', return_value='fake_key'):
            with patch('requirements_automation.llm.LLMClient._make_client'):
                client = LLMClient()
                
                # Mock the _call method to capture the prompt
                captured_prompt = None
                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return '{"questions": []}'
                
                client._call = mock_call
                
                # Call without prior_sections
                client.generate_open_questions(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    llm_profile="requirements"
                )
                
                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False
                
                # Verify Document Context is NOT present
                if "## Document Context" in captured_prompt:
                    print("  ✗ Document Context should not be in prompt")
                    return False
                
                # Verify task instruction does NOT mention document context
                if "Given the document context above" in captured_prompt:
                    print("  ✗ Task instruction should not reference document context")
                    return False
                
                # Verify basic task instruction is present
                if "Generate 2-5 clarifying questions" not in captured_prompt:
                    print("  ✗ Basic task instruction not in prompt")
                    return False
                
                print("  ✓ Prompt correctly excludes document context")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generate_questions_with_empty_prior_sections():
    """Test that generate_open_questions handles empty prior_sections dict."""
    print("\nTest 3: generate_open_questions with empty prior_sections...")
    
    try:
        with patch('requirements_automation.llm.os.getenv', return_value='fake_key'):
            with patch('requirements_automation.llm.LLMClient._make_client'):
                client = LLMClient()
                
                # Mock the _call method to capture the prompt
                captured_prompt = None
                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return '{"questions": []}'
                
                client._call = mock_call
                
                # Call with empty prior_sections dict
                client.generate_open_questions(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    llm_profile="requirements",
                    prior_sections={}
                )
                
                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False
                
                # Verify Document Context is NOT present
                if "## Document Context" in captured_prompt:
                    print("  ✗ Document Context should not be in prompt for empty dict")
                    return False
                
                # Verify task instruction does NOT mention document context
                if "Given the document context above" in captured_prompt:
                    print("  ✗ Task instruction should not reference document context")
                    return False
                
                print("  ✓ Empty prior_sections handled correctly")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integrate_answers_with_prior_sections():
    """Test that integrate_answers includes prior sections in prompt."""
    print("\nTest 4: integrate_answers with prior_sections...")
    
    try:
        with patch('requirements_automation.llm.os.getenv', return_value='fake_key'):
            with patch('requirements_automation.llm.LLMClient._make_client'):
                client = LLMClient()
                
                # Mock the _call method to capture the prompt
                captured_prompt = None
                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return "Rewritten section content"
                
                client._call = mock_call
                
                # Create test question
                test_question = OpenQuestion(
                    question_id="Q1",
                    question="What is the performance requirement?",
                    date="2024-01-01",
                    answer="Response time should be under 200ms",
                    section_target="technical_requirements",
                    status="Open"
                )
                
                # Call with prior_sections
                prior = {
                    "problem_statement": "This is a problem statement section.",
                    "goals_objectives": "These are the goals and objectives."
                }
                
                client.integrate_answers(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    answered_questions=[test_question],
                    llm_profile="requirements",
                    output_format="prose",
                    prior_sections=prior
                )
                
                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False
                
                # Verify Document Context header is present
                if "## Document Context (completed sections)" not in captured_prompt:
                    print("  ✗ Document Context header not in prompt")
                    return False
                
                # Verify section headers are present
                if "### problem_statement" not in captured_prompt:
                    print("  ✗ problem_statement section not in prompt")
                    return False
                
                # Verify section content is present
                if "This is a problem statement section." not in captured_prompt:
                    print("  ✗ problem_statement content not in prompt")
                    return False
                
                # Verify task instruction mentions document context
                if "Using the document context and answered questions" not in captured_prompt:
                    print("  ✗ Task instruction doesn't reference document context")
                    return False
                
                print("  ✓ Prior sections correctly injected into prompt")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integrate_answers_without_prior_sections():
    """Test that integrate_answers works without prior sections."""
    print("\nTest 5: integrate_answers without prior_sections...")
    
    try:
        with patch('requirements_automation.llm.os.getenv', return_value='fake_key'):
            with patch('requirements_automation.llm.LLMClient._make_client'):
                client = LLMClient()
                
                # Mock the _call method to capture the prompt
                captured_prompt = None
                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return "Rewritten section content"
                
                client._call = mock_call
                
                # Create test question
                test_question = OpenQuestion(
                    question_id="Q1",
                    question="What is the performance requirement?",
                    date="2024-01-01",
                    answer="Response time should be under 200ms",
                    section_target="technical_requirements",
                    status="Open"
                )
                
                # Call without prior_sections
                client.integrate_answers(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    answered_questions=[test_question],
                    llm_profile="requirements",
                    output_format="prose"
                )
                
                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False
                
                # Verify Document Context is NOT present
                if "## Document Context" in captured_prompt:
                    print("  ✗ Document Context should not be in prompt")
                    return False
                
                # Verify task instruction does NOT mention document context
                if "Using the document context" in captured_prompt:
                    print("  ✗ Task instruction should not reference document context")
                    return False
                
                # Verify basic task instruction is present
                if "Rewrite the section incorporating answers" not in captured_prompt:
                    print("  ✗ Basic task instruction not in prompt")
                    return False
                
                print("  ✓ Prompt correctly excludes document context")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integrate_answers_with_empty_prior_sections():
    """Test that integrate_answers handles empty prior_sections dict."""
    print("\nTest 6: integrate_answers with empty prior_sections...")
    
    try:
        with patch('requirements_automation.llm.os.getenv', return_value='fake_key'):
            with patch('requirements_automation.llm.LLMClient._make_client'):
                client = LLMClient()
                
                # Mock the _call method to capture the prompt
                captured_prompt = None
                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return "Rewritten section content"
                
                client._call = mock_call
                
                # Create test question
                test_question = OpenQuestion(
                    question_id="Q1",
                    question="What is the performance requirement?",
                    date="2024-01-01",
                    answer="Response time should be under 200ms",
                    section_target="technical_requirements",
                    status="Open"
                )
                
                # Call with empty prior_sections dict
                client.integrate_answers(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    answered_questions=[test_question],
                    llm_profile="requirements",
                    output_format="prose",
                    prior_sections={}
                )
                
                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False
                
                # Verify Document Context is NOT present
                if "## Document Context" in captured_prompt:
                    print("  ✗ Document Context should not be in prompt for empty dict")
                    return False
                
                # Verify task instruction does NOT mention document context
                if "Using the document context" in captured_prompt:
                    print("  ✗ Task instruction should not reference document context")
                    return False
                
                print("  ✓ Empty prior_sections handled correctly")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Prior Sections Support Test Suite")
    print("=" * 70)
    
    tests = [
        test_generate_questions_with_prior_sections,
        test_generate_questions_without_prior_sections,
        test_generate_questions_with_empty_prior_sections,
        test_integrate_answers_with_prior_sections,
        test_integrate_answers_without_prior_sections,
        test_integrate_answers_with_empty_prior_sections,
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
