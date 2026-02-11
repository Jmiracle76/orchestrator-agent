#!/usr/bin/env python3
"""
Acceptance Criteria Validation for Integration Tests: Prior-Context-Enabled Requirements Drafting

This script validates all acceptance criteria from the issue are met.
"""
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent


def run_test_script(script_name):
    """Run a test script and return whether it passed."""
    script_path = repo_root / "test-scripts" / script_name
    if not script_path.exists():
        print(f"    ✗ Test script not found: {script_name}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check if tests passed based on exit code
        if result.returncode == 0:
            # Also check output for "passed" indicator
            if "tests passed" in result.stdout:
                # Extract test count
                import re

                match = re.search(r"(\d+)/(\d+) tests passed", result.stdout)
                if match and match.group(1) == match.group(2):
                    print(f"    ✓ {script_name}: {match.group(1)}/{match.group(2)} tests passed")
                    return True
            print(f"    ✓ {script_name}: passed")
            return True
        else:
            print(f"    ✗ {script_name}: failed (exit code {result.returncode})")
            if result.stdout:
                print(f"       Output: {result.stdout[-500:]}")  # Last 500 chars
            return False
    except subprocess.TimeoutExpired:
        print(f"    ✗ {script_name}: timed out")
        return False
    except Exception as e:
        print(f"    ✗ {script_name}: exception {e}")
        return False


def validate_acceptance_criteria():
    """Validate all acceptance criteria."""
    print("=" * 70)
    print("Acceptance Criteria Validation")
    print("Integration Tests: Prior-Context-Enabled Requirements Drafting")
    print("=" * 70)

    criteria = []

    # Criterion 1: Unit tests pass for LLM prompt construction with/without prior sections
    print("\n1. Unit tests pass for LLM prompt construction with/without prior sections")
    passed = run_test_script("test_prior_sections.py")
    criteria.append(("LLM prompt construction tests", passed))

    # Criterion 2: Unit tests pass for _gather_prior_sections() edge cases
    print("\n2. Unit tests pass for _gather_prior_sections() edge cases")
    passed = run_test_script("test_gather_prior_sections.py")
    criteria.append(("_gather_prior_sections() tests", passed))

    # Criterion 3: Unit tests for scope config integration
    print("\n3. Unit tests for scope config integration")
    passed = run_test_script("test_scope_config_integration.py")
    criteria.append(("Scope config integration tests", passed))

    # Criterion 4: Integration test confirms end-to-end flow with prior context
    print("\n4. Integration test confirms end-to-end flow with prior context")
    passed = run_test_script("test_e2e_prior_context.py")
    criteria.append(("End-to-end integration tests", passed))

    # Additional checks
    print("\n5. Implementation files exist and contain expected functionality")

    # Check that runner_v2.py has scope-based prior_sections logic
    runner_path = repo_root / "tools" / "requirements_automation" / "runner_v2.py"
    if runner_path.exists():
        content = runner_path.read_text()
        if 'handler_config.scope == "all_prior_sections"' in content:
            print("    ✓ runner_v2.py implements scope-based prior_sections filtering")
            criteria.append(("Scope-based filtering implementation", True))
        else:
            print("    ✗ runner_v2.py missing scope-based filtering")
            criteria.append(("Scope-based filtering implementation", False))
    else:
        print("    ✗ runner_v2.py not found")
        criteria.append(("Scope-based filtering implementation", False))

    # Check that test files exist
    test_files = [
        "test_prior_sections.py",
        "test_gather_prior_sections.py",
        "test_scope_config_integration.py",
        "test_e2e_prior_context.py",
    ]

    print("\n6. All required test files exist")
    all_exist = True
    for test_file in test_files:
        test_path = repo_root / "test-scripts" / test_file
        if test_path.exists():
            print(f"    ✓ {test_file}")
        else:
            print(f"    ✗ {test_file} missing")
            all_exist = False
    criteria.append(("Required test files exist", all_exist))

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    for criterion, passed in criteria:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {criterion}")

    print("\n" + "=" * 70)
    passed_count = sum(1 for _, passed in criteria if passed)
    total_count = len(criteria)
    print(f"Results: {passed_count}/{total_count} criteria passed")
    print("=" * 70)

    if passed_count == total_count:
        print("\n🎉 All acceptance criteria met!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} acceptance criteria not met")
        return 1


if __name__ == "__main__":
    sys.exit(validate_acceptance_criteria())
