#!/usr/bin/env python3
"""
Integration test for CLI template creation with commit.

This test validates that when a new document is created from a template,
it is properly committed to git (regression test for the issue where
newly created files were left untracked).

Note: This test requires mocking the LLM client since we don't have an API key.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

# Import after path is set
from requirements_automation.cli import main
from requirements_automation.models import RunResult


def create_mock_llm():
    """Create a mock LLM client that returns no-op results."""
    mock_llm = MagicMock()
    return mock_llm


def create_mock_runner_result(changed=False, blocked=False, target_id="problem_statement"):
    """Create a mock workflow runner result."""
    result = MagicMock()
    result.changed = changed
    result.blocked = blocked
    result.blocked_reasons = []
    result.target_id = target_id
    result.action_taken = "no-op"
    return result


def test_template_creation_commits_file():
    """Test that creating a doc from template commits the file."""
    print("Test 1: CLI template creation commits new file...")

    # Create a temporary git repo for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_repo = tmpdir_path / "work"
        bare_repo = tmpdir_path / "bare.git"

        # Create a bare repo to push to
        subprocess.run(["git", "init", "--bare", str(bare_repo)], check=True, capture_output=True)

        # Initialize working git repo
        test_repo.mkdir()
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(bare_repo)],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )

        # Copy template file
        template_dir = test_repo / "docs" / "templates"
        template_dir.mkdir(parents=True)
        original_template = repo_root / "docs" / "templates" / "requirements-template.md"
        template_path = template_dir / "requirements-template.md"
        shutil.copy2(original_template, template_path)

        # Copy config directory (needed for handler registry)
        config_dir = test_repo / "config"
        config_dir.mkdir(parents=True)
        original_config = repo_root / "config" / "handler_registry.yaml"
        config_path = config_dir / "handler_registry.yaml"
        shutil.copy2(original_config, config_path)

        # Commit the template and config
        subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit with template"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "master"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )

        # Check that working tree is clean
        status_before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        if status_before.strip():
            print(f"  ✗ Working tree not clean before test: {status_before}")
            return False

        # Create path for new doc
        new_doc_path = test_repo / "docs" / "my-requirements.md"

        # Run CLI to create doc from template with mocked LLM and runner
        argv = [
            "--template",
            str(template_path),
            "--doc",
            str(new_doc_path),
            "--repo-root",
            str(test_repo),
            "--log-level",
            "WARNING",  # Reduce noise in test output
        ]

        # Mock the LLM client and WorkflowRunner to avoid API calls
        with patch("requirements_automation.cli.LLMClient") as mock_llm_class:
            with patch("requirements_automation.cli.WorkflowRunner") as mock_runner_class:
                # Setup mocks
                mock_llm = create_mock_llm()
                mock_llm_class.return_value = mock_llm

                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                # Make run_once return a no-op result (unchanged=False)
                mock_result = create_mock_runner_result(changed=False)
                mock_runner.run_once.return_value = mock_result
                mock_runner.lines = []  # Unchanged lines

                exit_code = main(argv)

        # Check that CLI succeeded
        if exit_code != 0:
            print(f"  ✗ CLI returned exit code {exit_code} (expected 0)")
            return False

        # Check that the new document exists
        if not new_doc_path.exists():
            print(f"  ✗ New document was not created: {new_doc_path}")
            return False

        # Check that working tree is clean (file should be committed)
        status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        if status_after.strip():
            print(f"  ✗ Working tree not clean after CLI run (file not committed):")
            print(f"     {status_after}")
            return False

        # Verify the file was actually committed
        log_output = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        if "requirements: initialize from template" not in log_output:
            print(f"  ✗ Commit message doesn't match expected:")
            print(f"     Got: {log_output}")
            return False

        print("  ✓ New document created from template and committed")
        print(f"  ✓ Commit message: {log_output.strip()}")
        return True


def test_template_creation_with_no_commit_flag():
    """Test that --no-commit flag prevents committing template creation."""
    print("\nTest 2: CLI template creation with --no-commit flag...")

    # Create a temporary git repo for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        test_repo = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )

        # Copy template file
        template_dir = test_repo / "docs" / "templates"
        template_dir.mkdir(parents=True)
        original_template = repo_root / "docs" / "templates" / "requirements-template.md"
        template_path = template_dir / "requirements-template.md"
        shutil.copy2(original_template, template_path)

        # Copy config directory
        config_dir = test_repo / "config"
        config_dir.mkdir(parents=True)
        original_config = repo_root / "config" / "handler_registry.yaml"
        config_path = config_dir / "handler_registry.yaml"
        shutil.copy2(original_config, config_path)

        # Commit the template and config
        subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit with template"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )

        # Create path for new doc
        new_doc_path = test_repo / "docs" / "my-requirements.md"

        # Run CLI with --no-commit flag
        argv = [
            "--template",
            str(template_path),
            "--doc",
            str(new_doc_path),
            "--repo-root",
            str(test_repo),
            "--no-commit",
            "--log-level",
            "WARNING",
        ]

        # Mock the LLM client and WorkflowRunner
        with patch("requirements_automation.cli.LLMClient") as mock_llm_class:
            with patch("requirements_automation.cli.WorkflowRunner") as mock_runner_class:
                mock_llm = create_mock_llm()
                mock_llm_class.return_value = mock_llm

                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner
                mock_result = create_mock_runner_result(changed=False)
                mock_runner.run_once.return_value = mock_result
                mock_runner.lines = []

                exit_code = main(argv)

        # Check that CLI succeeded
        if exit_code != 0:
            print(f"  ✗ CLI returned exit code {exit_code} (expected 0)")
            return False

        # Check that the new document exists
        if not new_doc_path.exists():
            print(f"  ✗ New document was not created: {new_doc_path}")
            return False

        # Check that file is untracked (not committed)
        status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        if "??" not in status_after:
            print(f"  ✗ File should be untracked but status is: {status_after}")
            return False

        print("  ✓ New document created but not committed (as expected with --no-commit)")
        return True


def test_template_creation_with_dry_run_flag():
    """Test that --dry-run flag prevents both file creation and commit."""
    print("\nTest 3: CLI template creation with --dry-run flag...")

    # Create a temporary git repo for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        test_repo = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )

        # Copy template file
        template_dir = test_repo / "docs" / "templates"
        template_dir.mkdir(parents=True)
        original_template = repo_root / "docs" / "templates" / "requirements-template.md"
        template_path = template_dir / "requirements-template.md"
        shutil.copy2(original_template, template_path)

        # Copy config directory
        config_dir = test_repo / "config"
        config_dir.mkdir(parents=True)
        original_config = repo_root / "config" / "handler_registry.yaml"
        config_path = config_dir / "handler_registry.yaml"
        shutil.copy2(original_config, config_path)

        # Commit the template and config
        subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit with template"],
            cwd=test_repo,
            check=True,
            capture_output=True,
        )

        # Create path for new doc
        new_doc_path = test_repo / "docs" / "my-requirements.md"

        # Run CLI with --dry-run flag
        argv = [
            "--template",
            str(template_path),
            "--doc",
            str(new_doc_path),
            "--repo-root",
            str(test_repo),
            "--dry-run",
            "--log-level",
            "WARNING",
        ]

        # Mock the LLM client and WorkflowRunner
        with patch("requirements_automation.cli.LLMClient") as mock_llm_class:
            with patch("requirements_automation.cli.WorkflowRunner") as mock_runner_class:
                mock_llm = create_mock_llm()
                mock_llm_class.return_value = mock_llm

                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner
                mock_result = create_mock_runner_result(changed=False)
                mock_runner.run_once.return_value = mock_result
                mock_runner.lines = []

                exit_code = main(argv)

        # Check that CLI succeeded
        if exit_code != 0:
            print(f"  ✗ CLI returned exit code {exit_code} (expected 0)")
            return False

        # In dry-run mode, the file should still exist (template copy happens before dry-run check)
        # but it shouldn't be committed
        if not new_doc_path.exists():
            print(f"  ✗ New document was not created: {new_doc_path}")
            return False

        # Check that file is untracked (not committed in dry-run)
        status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        if "??" not in status_after:
            print(f"  ✗ File should be untracked in dry-run mode, but got: {status_after}")
            return False

        print("  ✓ Dry-run mode: file created but not committed (as expected)")
        return True


def main_test():
    """Run all tests."""
    print("=" * 70)
    print("CLI Template Creation Test Suite")
    print("=" * 70)

    tests = [
        test_template_creation_commits_file,
        test_template_creation_with_no_commit_flag,
        test_template_creation_with_dry_run_flag,
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
