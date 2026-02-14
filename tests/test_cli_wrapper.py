import subprocess
import sys
from unittest.mock import patch

from web.cli_wrapper import run_requirements_cli


@patch("web.cli_wrapper.subprocess.run")
def test_builds_command_with_all_supported_flags(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"outcome": "updated"}',
        stderr="",
    )

    result = run_requirements_cli(
        repo_root="/repo",
        template="/templates/req.md",
        doc="/docs/req.md",
        dry_run=True,
        no_commit=True,
        log_level="debug",
        max_steps=3,
        handler_config="/handlers.yaml",
        validate=True,
        strict=True,
        timeout=123,
    )

    called_args = mock_run.call_args
    command = called_args.args[0]
    assert command[:3] == [sys.executable, "-m", "tools.requirements_automation.cli"]
    assert "--repo-root" in command and "/repo" in command
    assert "--template" in command and "/templates/req.md" in command
    assert "--doc" in command and "/docs/req.md" in command
    assert "--dry-run" in command
    assert "--no-commit" in command
    assert ["--log-level", "debug"] in [
        command[i : i + 2] for i in range(len(command) - 1)
    ]
    assert ["--max-steps", "3"] in [command[i : i + 2] for i in range(len(command) - 1)]
    assert ["--handler-config", "/handlers.yaml"] in [
        command[i : i + 2] for i in range(len(command) - 1)
    ]
    assert "--validate" in command
    assert "--strict" in command
    assert called_args.kwargs["timeout"] == 123

    assert result.status == "success"
    assert result.exit_code == 0
    assert result.json_blocks == [{"outcome": "updated"}]


@patch("web.cli_wrapper.subprocess.run")
def test_parses_logs_and_json_from_both_streams(mock_run):
    stdout = "INFO Starting workflow\n{\n  \"outcome\": \"updated\"\n}\n"
    stderr = "WARNING Something odd\n{\"detail\": \"warn\"}"
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout=stdout,
        stderr=stderr,
    )

    result = run_requirements_cli(
        repo_root="/repo",
        template="/tmpl.md",
        doc="/doc.md",
    )

    assert result.status == "error"
    assert result.exit_code == 1
    assert len(result.json_blocks) == 2
    assert {"outcome": "updated"} in result.json_blocks
    assert {"detail": "warn"} in result.json_blocks

    log_levels = {(log.level, log.stream) for log in result.logs}
    assert ("INFO", "stdout") in log_levels
    assert ("WARNING", "stderr") in log_levels


@patch("web.cli_wrapper.subprocess.run")
def test_handles_timeout_with_partial_output(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd=["python"],
        timeout=2,
        output='INFO Pre-run\n{"outcome": "blocked"}',
        stderr="ERROR Too slow",
    )

    result = run_requirements_cli(
        repo_root="/repo",
        template="/tmpl.md",
        doc="/doc.md",
        timeout=2,
    )

    assert result.status == "timeout"
    assert result.exit_code is None
    assert {"outcome": "blocked"} in result.json_blocks
    log_levels = {(log.level, log.stream) for log in result.logs}
    assert ("INFO", "stdout") in log_levels
    assert ("ERROR", "stderr") in log_levels
    assert "timed out" in (result.error or "")
