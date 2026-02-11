#!/usr/bin/env python3
"""
Integration test for CLI --validate flag.

This test validates that the CLI correctly checks document completion
using the --validate flag.
"""
import sys
import tempfile
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.cli import main


def test_validate_incomplete_document():
    """Test --validate flag with incomplete document."""
    print("Test 1: CLI --validate with incomplete document...")

    # Create a temporary incomplete document
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """<!-- meta:doc_type value="requirements" -->
<!-- meta:doc_format version="1.0" -->

<!-- workflow:order
problem_statement
goals_objectives
-->

# Requirements Document

## Open Questions
<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
| ----------- | -------- | ---- | ------ | -------------- | ----------------- |
| Q-001 | Test question? | 2024-01-01 |  | problem_statement | Open |

<!-- section:problem_statement -->
## Problem Statement
<!-- PLACEHOLDER -->

<!-- section:goals_objectives -->
## Goals & Objectives
- Goal 1
"""
        )
        temp_doc = Path(f.name)

    template_path = repo_root / "docs" / "templates" / "requirements-template.md"

    try:
        # Run CLI with --validate flag
        argv = [
            "--template",
            str(template_path),
            "--doc",
            str(temp_doc),
            "--repo-root",
            str(repo_root),
            "--validate",
        ]

        exit_code = main(argv)

        if exit_code == 1:
            print("  ✓ CLI returned exit code 1 (incomplete)")
            return True
        else:
            print(f"  ✗ CLI returned exit code {exit_code} (expected 1)")
            return False
    finally:
        temp_doc.unlink()


def test_validate_complete_document():
    """Test --validate flag with complete document."""
    print("\nTest 2: CLI --validate with complete document...")

    # Create a temporary complete document
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """<!-- meta:doc_type value="requirements" -->
<!-- meta:doc_format version="1.0" -->

<!-- workflow:order
problem_statement
goals_objectives
-->

# Requirements Document

## Open Questions
<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
| ----------- | -------- | ---- | ------ | -------------- | ----------------- |
| Q-001 | Test question? | 2024-01-01 | Test answer | problem_statement | Resolved |

<!-- section:problem_statement -->
## Problem Statement
This is a complete problem statement.

<!-- section:goals_objectives -->
## Goals & Objectives
- Goal 1
- Goal 2
"""
        )
        temp_doc = Path(f.name)

    template_path = repo_root / "docs" / "templates" / "requirements-template.md"

    try:
        # Run CLI with --validate flag
        argv = [
            "--template",
            str(template_path),
            "--doc",
            str(temp_doc),
            "--repo-root",
            str(repo_root),
            "--validate",
        ]

        exit_code = main(argv)

        if exit_code == 0:
            print("  ✓ CLI returned exit code 0 (complete)")
            return True
        else:
            print(f"  ✗ CLI returned exit code {exit_code} (expected 0)")
            return False
    finally:
        temp_doc.unlink()


def test_validate_strict_mode():
    """Test --validate --strict flag with deferred questions."""
    print("\nTest 3: CLI --validate --strict with deferred questions...")

    # Create a document with deferred questions
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """<!-- meta:doc_type value="requirements" -->
<!-- meta:doc_format version="1.0" -->

<!-- workflow:order
problem_statement
goals_objectives
-->

# Requirements Document

## Open Questions
<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
| ----------- | -------- | ---- | ------ | -------------- | ----------------- |
| Q-001 | Test question? | 2024-01-01 | Answer later | problem_statement | Deferred |

<!-- section:problem_statement -->
## Problem Statement
This is a complete problem statement.

<!-- section:goals_objectives -->
## Goals & Objectives
- Goal 1
- Goal 2
"""
        )
        temp_doc = Path(f.name)

    template_path = repo_root / "docs" / "templates" / "requirements-template.md"

    try:
        # Run CLI with --validate flag (normal mode - should pass)
        argv_normal = [
            "--template",
            str(template_path),
            "--doc",
            str(temp_doc),
            "--repo-root",
            str(repo_root),
            "--validate",
        ]

        exit_code_normal = main(argv_normal)

        # Run CLI with --validate --strict flag (should fail)
        argv_strict = [
            "--template",
            str(template_path),
            "--doc",
            str(temp_doc),
            "--repo-root",
            str(repo_root),
            "--validate",
            "--strict",
        ]

        exit_code_strict = main(argv_strict)

        if exit_code_normal == 0 and exit_code_strict == 1:
            print("  ✓ Normal mode: exit code 0 (complete)")
            print("  ✓ Strict mode: exit code 1 (incomplete)")
            return True
        else:
            print(f"  ✗ Normal mode: exit code {exit_code_normal} (expected 0)")
            print(f"  ✗ Strict mode: exit code {exit_code_strict} (expected 1)")
            return False
    finally:
        temp_doc.unlink()


def main_test():
    """Run all tests."""
    print("=" * 70)
    print("CLI Validation Test Suite")
    print("=" * 70)

    tests = [
        test_validate_incomplete_document,
        test_validate_complete_document,
        test_validate_strict_mode,
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
    sys.exit(main_test())
