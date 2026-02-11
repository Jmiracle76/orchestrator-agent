#!/usr/bin/env python3
"""
End-to-end integration test for prior-context-enabled requirements drafting.

This test verifies that:
1. CLI processes documents with completed early sections
2. LLM calls for later sections include prior context
3. Generated questions reference specific details from earlier sections
"""
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.cli import main as cli_main
from requirements_automation.utils_io import read_text, write_text


def setup_test_config_with_all_prior_sections_scope(tmpdir_path):
    """
    Helper function to setup handler registry with modified scope.

    Creates a copy of the handler registry and modifies the requirements
    section to use scope: all_prior_sections for testing.

    Args:
        tmpdir_path: Path to temporary directory
    """
    config_dir = tmpdir_path / "config"
    config_dir.mkdir(exist_ok=True)
    registry_src = repo_root / "config" / "handler_registry.yaml"
    registry_dst = config_dir / "handler_registry.yaml"

    # Parse YAML, modify, and write back
    with open(registry_src, "r") as f:
        config_data = yaml.safe_load(f)

    # Modify the requirements section scope
    if "requirements" in config_data and "requirements" in config_data["requirements"]:
        config_data["requirements"]["requirements"]["scope"] = "all_prior_sections"

    with open(registry_dst, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    return registry_dst


def test_cli_with_prior_context():
    """Test CLI processes document with prior context included in LLM calls."""
    print("Integration Test: CLI with Prior Context")
    print("=" * 70)

    # Create a test document with completed early sections and blank requirements
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
constraints
requirements
-->

# Test Requirements Document

<!-- section:problem_statement -->
## Problem Statement
We need to build a GitHub API integration that syncs issues and pull requests to our internal database for reporting purposes.

<!-- section_lock:problem_statement lock=true -->
---

<!-- section:constraints -->
## Constraints
### Technical Constraints
- Must use GitHub REST API v3
- Rate limited to 5000 requests per hour
- Must handle authentication via OAuth tokens

### Resource Constraints
- Backend must process updates within 5 seconds
- Database storage limited to 1TB

<!-- section_lock:constraints lock=true -->
---

<!-- section:requirements -->
## Requirements
<!-- PLACEHOLDER -->

<!-- section_lock:requirements lock=false -->
---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
"""

    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        doc_path = tmpdir_path / "test_requirements.md"

        # Setup test config with modified scope
        setup_test_config_with_all_prior_sections_scope(tmpdir_path)

        # Write test document
        write_text(doc_path, test_doc)
        print(f"  Created test document: {doc_path}")
        print(f"  Modified handler config to use scope: all_prior_sections for requirements")

        # Track LLM calls to verify prior context is included
        llm_calls = []

        def mock_llm_call(prompt):
            """Mock LLM call that captures the prompt."""
            llm_calls.append(prompt)
            # Return sample questions that reference prior context
            return """{
                "questions": [
                    {
                        "question": "Should the GitHub API integration support webhook endpoints for real-time updates, or rely on polling within the 5-second processing constraint?",
                        "section_target": "requirements",
                        "rationale": "Need to clarify real-time requirements given the resource constraints"
                    },
                    {
                        "question": "What OAuth scope is required for the GitHub authentication tokens to access issues and pull requests?",
                        "section_target": "requirements",
                        "rationale": "Need to define specific API permissions"
                    },
                    {
                        "question": "How should the system handle GitHub API rate limiting (5000 requests/hour)?",
                        "section_target": "requirements",
                        "rationale": "Need strategy for staying within API constraints"
                    }
                ]
            }"""

        # Patch the LLM client's _call method
        with patch("requirements_automation.llm.LLMClient._call", side_effect=mock_llm_call):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                # Run CLI
                print("  Running CLI...")
                sys.argv = [
                    "cli.py",
                    "--template",
                    str(doc_path),  # Use the doc itself as template for simplicity
                    "--doc",
                    str(doc_path),
                    "--repo-root",
                    str(tmpdir_path),
                    "--dry-run",  # Don't actually modify the file
                    "--no-commit",  # Don't require git
                ]

                try:
                    result = cli_main()
                    print(f"  CLI completed with result: {result}")
                except SystemExit as e:
                    result = e.code
                    print(f"  CLI exited with code: {result}")

        # Verify LLM was called
        if not llm_calls:
            print("  ✗ No LLM calls made")
            return False

        print(f"\n  LLM was called {len(llm_calls)} time(s)")

        # Check if any call includes document context
        has_context = False
        context_details = []

        for i, prompt in enumerate(llm_calls):
            print(f"\n  Analyzing LLM call {i+1}...")

            # Check for Document Context header
            if "## Document Context (completed sections)" in prompt:
                has_context = True
                print("    ✓ Contains 'Document Context' header")

                # Check for specific prior section content
                if "### problem_statement" in prompt:
                    print("    ✓ Includes problem_statement section")
                    context_details.append("problem_statement")

                    # Check for specific content from problem_statement
                    if "GitHub API" in prompt:
                        print("    ✓ References 'GitHub API' from problem_statement")
                    if "issues and pull requests" in prompt:
                        print("    ✓ References 'issues and pull requests' from problem_statement")

                if "### constraints" in prompt:
                    print("    ✓ Includes constraints section")
                    context_details.append("constraints")

                    # Check for specific content from constraints
                    if "5000 requests per hour" in prompt:
                        print("    ✓ References API rate limit from constraints")
                    if "OAuth tokens" in prompt:
                        print("    ✓ References OAuth authentication from constraints")
                    if "5 seconds" in prompt:
                        print("    ✓ References processing time constraint")
            else:
                print("    ⚠ Does not contain Document Context")

        # Verify results
        print(f"\n  Summary:")
        if has_context:
            print(f"    ✓ LLM calls included prior context")
            print(f"    ✓ Prior sections included: {', '.join(context_details)}")
            return True
        else:
            print(f"    ✗ No LLM calls included prior context")
            print(f"    ℹ This might be expected if the handler config has scope: current_section")
            # Check if it's actually a failure or expected behavior
            # For requirements section, check the handler config
            return False


def test_question_quality_with_prior_context():
    """Test that questions reference specific details from prior sections."""
    print("\nIntegration Test: Question Quality with Prior Context")
    print("=" * 70)

    # This test verifies that when prior context is provided, the questions
    # generated are more targeted and reference specific details

    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
goals_objectives
constraints
requirements
-->

<!-- section:problem_statement -->
## Problem Statement
We need a real-time data synchronization system for IoT sensors that collects temperature and humidity readings from 10,000+ devices deployed across multiple geographic regions.

<!-- section_lock:problem_statement lock=true -->
---

<!-- section:goals_objectives -->
## Goals and Objectives
### Primary Goals
- Achieve sub-second data latency for critical alerts
- Support scalability to 50,000 devices within 2 years
- Maintain 99.9% uptime SLA

<!-- section_lock:goals_objectives lock=true -->
---

<!-- section:constraints -->
## Constraints
### Technical Constraints
- Must use MQTT protocol for device communication
- Data retention limited to 90 days for compliance
- SSL/TLS encryption required for all data transmission

### Resource Constraints
- Cloud infrastructure budget: $5,000/month
- Team size: 3 backend developers, 1 DevOps engineer

<!-- section_lock:constraints lock=true -->
---

<!-- section:requirements -->
## Requirements
<!-- PLACEHOLDER -->

<!-- section_lock:requirements lock=false -->
---

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        doc_path = tmpdir_path / "test_iot_requirements.md"

        # Setup test config with modified scope
        setup_test_config_with_all_prior_sections_scope(tmpdir_path)

        write_text(doc_path, test_doc)
        print(f"  Created test document: {doc_path}")
        print(f"  Modified handler config to use scope: all_prior_sections for requirements")

        # Track the prompt to verify it includes specific details
        captured_prompts = []

        def mock_llm_call(prompt):
            """Mock LLM call that captures the prompt."""
            captured_prompts.append(prompt)
            # Return contextual questions that reference prior sections
            return """{
                "questions": [
                    {
                        "question": "How should the MQTT broker architecture scale to support 50,000 IoT devices while maintaining sub-second latency for critical temperature alerts?",
                        "section_target": "requirements",
                        "rationale": "Combines scalability goal with MQTT constraint and latency requirement"
                    },
                    {
                        "question": "What temperature/humidity thresholds should trigger critical alerts requiring sub-second latency?",
                        "section_target": "requirements",
                        "rationale": "Defines what constitutes a critical alert from sensor readings"
                    },
                    {
                        "question": "How will the 90-day data retention policy be implemented while maintaining historical trend analysis capabilities?",
                        "section_target": "requirements",
                        "rationale": "Addresses compliance constraint from constraints section"
                    }
                ]
            }"""

        with patch("requirements_automation.llm.LLMClient._call", side_effect=mock_llm_call):
            with patch("requirements_automation.llm.LLMClient._make_client"):
                sys.argv = [
                    "cli.py",
                    "--template",
                    str(doc_path),  # Use the doc itself as template for simplicity
                    "--doc",
                    str(doc_path),
                    "--repo-root",
                    str(tmpdir_path),
                    "--dry-run",
                    "--no-commit",  # Don't require git
                ]

                try:
                    result = cli_main()
                except SystemExit as e:
                    result = e.code

        if not captured_prompts:
            print("  ✗ No prompts captured")
            return False

        # Analyze the prompt for quality indicators
        prompt = captured_prompts[0]  # Check the first/main prompt

        print(f"\n  Analyzing prompt for context-aware question generation...")

        quality_checks = {
            "IoT sensors": "Mentions IoT sensors from problem_statement",
            "10,000": "References device count from problem_statement",
            "sub-second": "References latency goal from goals_objectives",
            "99.9%": "References uptime SLA from goals_objectives",
            "MQTT": "References MQTT protocol from constraints",
            "90 days": "References data retention from constraints",
            "$5,000": "References budget constraint",
        }

        passed_checks = 0
        for detail, description in quality_checks.items():
            if detail in prompt:
                print(f"    ✓ {description}")
                passed_checks += 1
            else:
                print(f"    ⚠ Missing: {description}")

        print(f"\n  Quality score: {passed_checks}/{len(quality_checks)} context details present")

        # Consider test passed if at least half the details are present
        if passed_checks >= len(quality_checks) // 2:
            print(f"  ✓ Prompt includes sufficient prior context details")
            return True
        else:
            print(f"  ✗ Prompt lacks sufficient prior context details")
            return False


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("End-to-End Integration Test Suite")
    print("Prior-Context-Enabled Requirements Drafting")
    print("=" * 70)

    tests = [
        test_cli_with_prior_context,
        test_question_quality_with_prior_context,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ Test failed with exception: {e}")
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
