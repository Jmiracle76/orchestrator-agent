#!/usr/bin/env python3
"""
Test script for context-aware LLM prompt enhancements.

This verifies that:
1. format_prior_sections() matches the issue specification
2. Question generation prompts include proper instructions when prior context is available
3. Prior sections are formatted with clear instructions to avoid redundancy
"""
import sys
from pathlib import Path
from unittest.mock import patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.llm_prompts import (
    build_open_questions_prompt,
    format_prior_sections,
)
from requirements_automation.llm_client import LLMClient


def test_format_prior_sections_header():
    """Test that format_prior_sections() uses correct header from issue spec."""
    print("Test 1: format_prior_sections header format...")

    prior = {
        "problem_statement": "This is the problem statement.",
        "goals_objectives": "These are the goals.",
    }

    formatted = format_prior_sections(prior)

    # Check for new header format
    if "## Previously Completed Sections" not in formatted:
        print("  ✗ Header should be '## Previously Completed Sections'")
        print(f"  Got: {formatted[:100]}")
        return False

    # Check for instructions about avoiding redundancy
    if "Avoid asking questions that have already been answered" not in formatted:
        print("  ✗ Missing instruction about avoiding redundant questions")
        return False

    # Check for usage instructions
    if "Use the following completed sections as context" not in formatted:
        print("  ✗ Missing instruction about using sections as context")
        return False

    print("  ✓ Header and instructions match specification")
    return True


def test_format_prior_sections_readable_titles():
    """Test that section IDs are formatted as readable titles."""
    print("\nTest 2: Section IDs formatted as readable titles...")

    prior = {
        "problem_statement": "Problem content",
        "goals_objectives": "Goals content",
        "technical_requirements": "Requirements content",
    }

    formatted = format_prior_sections(prior)

    # Check that section IDs are formatted as titles
    if "### Problem Statement" not in formatted:
        print("  ✗ 'problem_statement' should be formatted as '### Problem Statement'")
        return False

    if "### Goals Objectives" not in formatted:
        print("  ✗ 'goals_objectives' should be formatted as '### Goals Objectives'")
        return False

    if "### Technical Requirements" not in formatted:
        print("  ✗ 'technical_requirements' should be formatted as '### Technical Requirements'")
        return False

    print("  ✓ Section IDs correctly formatted as readable titles")
    return True


def test_format_prior_sections_content_preserved():
    """Test that section content is preserved and properly formatted."""
    print("\nTest 3: Section content preserved...")

    prior = {
        "problem_statement": "This is the problem.\nIt has multiple lines.",
        "goals_objectives": "Goal 1\nGoal 2",
    }

    formatted = format_prior_sections(prior)

    if "This is the problem.\nIt has multiple lines." not in formatted:
        print("  ✗ problem_statement content not preserved")
        return False

    if "Goal 1\nGoal 2" not in formatted:
        print("  ✗ goals_objectives content not preserved")
        return False

    print("  ✓ Section content correctly preserved")
    return True


def test_format_prior_sections_empty():
    """Test that empty prior sections returns empty string."""
    print("\nTest 4: Empty prior sections...")

    formatted = format_prior_sections({})

    if formatted != "":
        print(f"  ✗ Empty dict should return empty string, got: {formatted}")
        return False

    print("  ✓ Empty prior sections handled correctly")
    return True


def test_question_prompt_with_prior_context():
    """Test that question generation prompt includes enhanced instructions with prior context."""
    print("\nTest 5: Question generation prompt with prior context...")

    prior = {
        "problem_statement": "Problem description",
        "goals_objectives": "Goals and objectives",
    }

    prompt = build_open_questions_prompt(
        section_id="technical_requirements",
        section_context="To be filled",
        full_profile="You are a requirements analyst.",
        prior_sections=prior,
    )

    # Check that prior context header is present
    if "## Previously Completed Sections" not in prompt:
        print("  ✗ Prior context header missing from prompt")
        return False

    # Check that section content is included
    if "Problem description" not in prompt:
        print("  ✗ Prior section content missing from prompt")
        return False

    # Check for enhanced task instructions (from issue spec)
    expected_instructions = [
        "Fill gaps in the current section",
        "Build on information from prior sections",
        "Do NOT repeat questions already answered in prior sections",
        "Help establish clear, testable requirements",
    ]

    for instruction in expected_instructions:
        if instruction not in prompt:
            print(f"  ✗ Missing instruction: {instruction}")
            return False

    print("  ✓ Question prompt includes enhanced instructions with prior context")
    return True


def test_question_prompt_without_prior_context():
    """Test that question generation prompt works without prior context."""
    print("\nTest 6: Question generation prompt without prior context...")

    prompt = build_open_questions_prompt(
        section_id="problem_statement",
        section_context="To be filled",
        full_profile="You are a requirements analyst.",
        prior_sections=None,
    )

    # Should not have prior context header
    if "## Previously Completed Sections" in prompt:
        print("  ✗ Prior context header should not be present")
        return False

    # Should have simple instruction
    if "Generate 2-5 clarifying questions to help complete this section." not in prompt:
        print("  ✗ Simple instruction missing when no prior context")
        return False

    # Should not have enhanced instructions
    if "Build on information from prior sections" in prompt:
        print("  ✗ Enhanced instructions should not be present without prior context")
        return False

    print("  ✓ Question prompt works correctly without prior context")
    return True


def test_llm_client_integration_with_prior_context():
    """Test that LLMClient correctly passes prior context through to prompts."""
    print("\nTest 7: LLMClient integration with prior context...")

    try:
        with patch("requirements_automation.llm_client.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm_client.LLMClient._make_client"):
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
                    "problem_statement": "Problem content",
                    "goals_objectives": "Goals content",
                }

                client.generate_open_questions(
                    section_id="technical_requirements",
                    section_context="To be filled",
                    llm_profile="requirements",
                    prior_sections=prior,
                )

                if captured_prompt is None:
                    print("  ✗ No prompt captured")
                    return False

                # Verify new header format
                if "## Previously Completed Sections" not in captured_prompt:
                    print("  ✗ New header format not in prompt")
                    print(f"  Got header: {captured_prompt[:200]}")
                    return False

                # Verify enhanced instructions
                if "Do NOT repeat questions already answered in prior sections" not in captured_prompt:
                    print("  ✗ Enhanced instructions not in prompt")
                    return False

                # Verify readable section titles
                if "### Problem Statement" not in captured_prompt:
                    print("  ✗ Readable section title not in prompt")
                    return False

                print("  ✓ LLMClient correctly uses enhanced prompt format")
                return True

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Context-Aware LLM Prompt Test Suite")
    print("=" * 70)

    tests = [
        test_format_prior_sections_header,
        test_format_prior_sections_readable_titles,
        test_format_prior_sections_content_preserved,
        test_format_prior_sections_empty,
        test_question_prompt_with_prior_context,
        test_question_prompt_without_prior_context,
        test_llm_client_integration_with_prior_context,
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
