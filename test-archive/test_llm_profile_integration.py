#!/usr/bin/env python3
"""
Test script for LLM profile integration.

This verifies that the LLMClient correctly loads and uses profiles.
Note: This doesn't make actual LLM API calls, just validates the
prompt construction.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.llm import LLMClient
from requirements_automation.models import OpenQuestion


def test_llm_client_has_profile_loader():
    """Test that LLMClient initializes with ProfileLoader."""
    print("Test 1: LLMClient has ProfileLoader...")

    try:
        # Mock the Anthropic client to avoid needing API key
        with patch("requirements_automation.llm.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                client = LLMClient()

                if not hasattr(client, "profile_loader"):
                    print("  ✗ LLMClient missing profile_loader attribute")
                    return False

                if client.profile_loader is None:
                    print("  ✗ ProfileLoader is None")
                    return False

                print("  ✓ LLMClient has ProfileLoader instance")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_generate_questions_uses_profile():
    """Test that generate_open_questions includes profile in prompt."""
    print("\nTest 2: generate_open_questions uses profile...")

    try:
        with patch("requirements_automation.llm.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                client = LLMClient()

                # Mock the _call method to capture the prompt
                captured_prompt = None

                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    # Return valid JSON response
                    return '{"questions": []}'

                client._call = mock_call

                # Call generate_open_questions
                client.generate_open_questions(
                    section_id="test_section",
                    section_context="Test context",
                    llm_profile="requirements",
                )

                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False

                # Verify profile content is in prompt
                if "Core Rules" not in captured_prompt:
                    print("  ✗ Base policy not in prompt")
                    return False

                if "Document Purpose" not in captured_prompt:
                    print("  ✗ Requirements profile not in prompt")
                    return False

                # Verify task-specific content is also in prompt
                if "test_section" not in captured_prompt:
                    print("  ✗ Section ID not in prompt")
                    return False

                print("  ✓ Profile correctly injected into prompt")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_integrate_answers_uses_profile():
    """Test that integrate_answers includes profile in prompt."""
    print("\nTest 3: integrate_answers uses profile...")

    try:
        with patch("requirements_automation.llm.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                client = LLMClient()

                # Mock the _call method to capture the prompt
                captured_prompt = None

                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return "Updated section content"

                client._call = mock_call

                # Create a test question
                test_question = OpenQuestion(
                    question_id="Q1",
                    question="Test question?",
                    date="2024-01-01",
                    answer="Test answer",
                    section_target="test_section",
                    status="Open",
                )

                # Call integrate_answers
                client.integrate_answers(
                    section_id="test_section",
                    section_context="Test context",
                    answered_questions=[test_question],
                    llm_profile="requirements",
                    output_format="prose",
                )

                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False

                # Verify profile content is in prompt
                if "Core Rules" not in captured_prompt:
                    print("  ✗ Base policy not in prompt")
                    return False

                if "Document Purpose" not in captured_prompt:
                    print("  ✗ Requirements profile not in prompt")
                    return False

                # Verify output format guidance is in prompt
                if "prose" not in captured_prompt.lower():
                    print("  ✗ Output format guidance not in prompt")
                    return False

                print("  ✓ Profile correctly injected into prompt")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_different_profile_support():
    """Test that different profiles can be used."""
    print("\nTest 4: Support for different profiles...")

    try:
        with patch("requirements_automation.llm.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                client = LLMClient()

                # Mock the _call method
                captured_prompts = []

                def mock_call(prompt):
                    captured_prompts.append(prompt)
                    return '{"questions": []}'

                client._call = mock_call

                # Test with requirements profile
                client.generate_open_questions(
                    section_id="test", section_context="test", llm_profile="requirements"
                )

                # Test with requirements_review profile
                client.generate_open_questions(
                    section_id="test", section_context="test", llm_profile="requirements_review"
                )

                if len(captured_prompts) != 2:
                    print(f"  ✗ Expected 2 prompts, got {len(captured_prompts)}")
                    return False

                # Verify first prompt has requirements content
                if "Language Guidelines" not in captured_prompts[0]:
                    print("  ✗ First prompt missing requirements profile content")
                    return False

                # Verify second prompt has review content
                if "Review Objective" not in captured_prompts[1]:
                    print("  ✗ Second prompt missing review profile content")
                    return False

                print("  ✓ Different profiles loaded correctly")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("LLM Profile Integration Test Suite")
    print("=" * 70)

    tests = [
        test_llm_client_has_profile_loader,
        test_generate_questions_uses_profile,
        test_integrate_answers_uses_profile,
        test_different_profile_support,
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
