#!/usr/bin/env python3
"""
Test script for draft_section functionality.

This verifies that the LLMClient.draft_section() method and the unified handler
drafting step work correctly.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.llm import LLMClient
from requirements_automation.runner_v2 import WorkflowRunner
from requirements_automation.utils_io import split_lines


def test_draft_section_method_exists():
    """Test that LLMClient has draft_section method."""
    print("Test 1: LLMClient has draft_section method...")

    try:
        # Mock the Anthropic client to avoid needing API key
        with patch("requirements_automation.llm.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                client = LLMClient()

                if not hasattr(client, "draft_section"):
                    print("  ✗ LLMClient missing draft_section method")
                    return False

                if not callable(client.draft_section):
                    print("  ✗ draft_section is not callable")
                    return False

                print("  ✓ LLMClient has draft_section method")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_draft_section_uses_profile_and_context():
    """Test that draft_section includes profile and prior sections in prompt."""
    print("\nTest 2: draft_section uses profile and prior sections...")

    try:
        with patch("requirements_automation.llm.os.getenv", return_value="fake_key"):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                client = LLMClient()

                # Mock the _call method to capture the prompt
                captured_prompt = None

                def mock_call(prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    return "Drafted section content based on prior context."

                client._call = mock_call

                # Call draft_section with prior sections
                prior_sections = {
                    "problem_statement": "The system needs to automate workflows.",
                    "goals_objectives": "Goal 1: Reduce manual work by 80%.",
                }

                result = client.draft_section(
                    section_id="requirements",
                    section_context="<!-- PLACEHOLDER -->",
                    prior_sections=prior_sections,
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

                # Verify document context is in prompt
                if "Document Context" not in captured_prompt:
                    print("  ✗ Document context header not in prompt")
                    return False

                if "problem_statement" not in captured_prompt:
                    print("  ✗ Prior section ID not in prompt")
                    return False

                if "automate workflows" not in captured_prompt:
                    print("  ✗ Prior section content not in prompt")
                    return False

                # Verify task instruction is correct
                if "Draft Section Content from Prior Context" not in captured_prompt:
                    print("  ✗ Task instruction not in prompt")
                    return False

                # Verify output format guidance is in prompt
                if "prose" not in captured_prompt.lower():
                    print("  ✗ Output format guidance not in prompt")
                    return False

                # Verify result is returned
                if not result or "Drafted section content" not in result:
                    print("  ✗ Unexpected result from draft_section")
                    return False

                print("  ✓ draft_section correctly uses profile and prior sections")
                return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_unified_handler_calls_draft_section():
    """Test that unified handler calls draft_section when appropriate."""
    print("\nTest 3: Unified handler calls draft_section with prior context...")

    try:
        # Load handler registry
        config_path = repo_root / "config" / "handler_registry.yaml"
        registry = HandlerRegistry(config_path)

        # Create a test document with completed prior sections and blank requirements section
        test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
goals_objectives
requirements
-->

# Test Document

<!-- section:problem_statement -->
## Problem Statement
The current system requires too much manual work.
<!-- section_lock:problem_statement lock=false -->

<!-- section:goals_objectives -->
## Goals and Objectives
- Reduce manual work by 80%
- Improve efficiency
<!-- section_lock:goals_objectives lock=false -->

<!-- section:requirements -->
## Requirements
<!-- PLACEHOLDER -->
<!-- section_lock:requirements lock=false -->

---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
"""

        lines = split_lines(test_doc)

        # Create mock LLM
        mock_llm = Mock()
        mock_llm.draft_section = Mock(
            return_value="REQ-1: System shall automate workflow steps.\nREQ-2: System shall reduce manual work by 80%."
        )
        mock_llm.generate_open_questions = Mock(return_value=[])

        # Create workflow runner
        runner = WorkflowRunner(
            lines=lines,
            llm=mock_llm,
            doc_type="requirements",
            workflow_order=["problem_statement", "goals_objectives", "requirements"],
            handler_registry=registry,
        )

        # Get handler config for requirements section
        handler_config = registry.get_handler_config("requirements", "requirements")

        # Execute the requirements section
        state = runner._get_section_state("requirements")
        print(f"  Initial section state:")
        print(f"    exists: {state.exists}")
        print(f"    is_blank: {state.is_blank}")
        print(f"    has_placeholder: {state.has_placeholder}")

        # Execute the section
        result = runner._execute_section("requirements", state, dry_run=False)

        print(f"\n  Execution result:")
        print(f"    action_taken: {result.action_taken}")
        print(f"    changed: {result.changed}")
        print(f"    summaries: {result.summaries}")

        # Verify that draft_section was called
        if not mock_llm.draft_section.called:
            print("  ✗ draft_section was not called")
            return False

        print(f"  ✓ draft_section was called")

        # Verify it was called with correct parameters
        call_args = mock_llm.draft_section.call_args
        if call_args.args[0] != "requirements":
            print(f"  ✗ Wrong section_id: {call_args.args[0]}")
            return False

        # Check that prior_sections were passed
        prior_sections = call_args.args[2]
        if not isinstance(prior_sections, dict):
            print("  ✗ prior_sections not passed as dict")
            return False

        if "problem_statement" not in prior_sections:
            print("  ✗ problem_statement not in prior_sections")
            return False

        if "goals_objectives" not in prior_sections:
            print("  ✗ goals_objectives not in prior_sections")
            return False

        print(f"  ✓ draft_section called with correct prior_sections")

        # Verify that section was updated
        if not result.changed:
            print("  ✗ Section was not marked as changed")
            return False

        # Verify summary indicates drafting occurred
        if not any("Drafted initial content" in s for s in result.summaries):
            print(f"  ✗ No draft summary found in: {result.summaries}")
            return False

        print(f"  ✓ Section was updated with draft content")

        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_draft_section_fallback_to_questions():
    """Test that handler falls back to generating questions if draft fails."""
    print("\nTest 4: Fallback to questions when draft returns empty...")

    try:
        # Load handler registry
        config_path = repo_root / "config" / "handler_registry.yaml"
        registry = HandlerRegistry(config_path)

        # Create a test document with blank requirements section
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
"""

        lines = split_lines(test_doc)

        # Create mock LLM that returns empty draft but valid questions
        mock_llm = Mock()
        mock_llm.draft_section = Mock(return_value="")  # Empty draft
        mock_llm.generate_open_questions = Mock(
            return_value=[
                {
                    "question": "What are the key requirements?",
                    "section_target": "requirements",
                    "rationale": "Need clarification",
                }
            ]
        )

        # Create workflow runner
        runner = WorkflowRunner(
            lines=lines,
            llm=mock_llm,
            doc_type="requirements",
            workflow_order=["requirements"],
            handler_registry=registry,
        )

        # Execute the requirements section
        state = runner._get_section_state("requirements")
        result = runner._execute_section("requirements", state, dry_run=False)

        print(f"  Execution result:")
        print(f"    action_taken: {result.action_taken}")
        print(f"    questions_generated: {result.questions_generated}")

        # Since prior_sections is empty (no prior sections), draft_section should NOT be called
        if mock_llm.draft_section.called:
            print("  ✗ draft_section was called even without prior sections")
            return False

        print(f"  ✓ draft_section was not called without prior sections")

        # Verify that generate_open_questions was called instead
        if not mock_llm.generate_open_questions.called:
            print("  ✗ generate_open_questions was not called")
            return False

        print(f"  ✓ Fell back to generating questions")

        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Draft Section Test Suite")
    print("=" * 70)

    tests = [
        test_draft_section_method_exists,
        test_draft_section_uses_profile_and_context,
        test_unified_handler_calls_draft_section,
        test_draft_section_fallback_to_questions,
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
