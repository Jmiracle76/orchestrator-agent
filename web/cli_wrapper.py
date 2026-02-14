from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, List, Literal, Optional

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
StreamName = Literal["stdout", "stderr"]

_LOG_LEVELS: set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass
class LogEntry:
    level: LogLevel
    message: str
    stream: StreamName


@dataclass
class CLIWrapperResult:
    status: Literal["success", "error", "timeout"]
    exit_code: Optional[int]
    stdout: str
    stderr: str
    logs: List[LogEntry]
    json_blocks: List[Any]
    command: List[str]
    error: Optional[str] = None


def run_requirements_cli(
    *,
    repo_root: str,
    template: str,
    doc: str,
    dry_run: bool = False,
    no_commit: bool = False,
    log_level: str = "INFO",
    max_steps: Optional[int] = None,
    handler_config: Optional[str] = None,
    validate: bool = False,
    strict: bool = False,
    timeout: Optional[float] = 300,
) -> CLIWrapperResult:
    """
    Run the requirements automation CLI as a subprocess and capture structured output.

    Returns a CLIWrapperResult containing exit code, parsed JSON payloads, log entries,
    and raw stdout/stderr for API consumption. Handles timeouts and unexpected errors
    without raising, so callers can relay the failure details directly.
    """
    command = _build_command(
        repo_root=repo_root,
        template=template,
        doc=doc,
        dry_run=dry_run,
        no_commit=no_commit,
        log_level=log_level,
        max_steps=max_steps,
        handler_config=handler_config,
        validate=validate,
        strict=strict,
    )

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "success" if completed.returncode == 0 else "error"
        error = None if status == "success" else f"Process exited with code {completed.returncode}"
        return CLIWrapperResult(
            status=status,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            logs=_collect_logs((stdout, "stdout"), (stderr, "stderr")),
            json_blocks=_collect_json(stdout, stderr),
            command=command,
            error=error,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return CLIWrapperResult(
            status="timeout",
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            logs=_collect_logs((stdout, "stdout"), (stderr, "stderr")),
            json_blocks=_collect_json(stdout, stderr),
            command=command,
            error=f"Process timed out after {timeout} seconds",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return CLIWrapperResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr=str(exc),
            logs=[],
            json_blocks=[],
            command=command,
            error=str(exc),
        )


def _build_command(
    *,
    repo_root: str,
    template: str,
    doc: str,
    dry_run: bool,
    no_commit: bool,
    log_level: str,
    max_steps: Optional[int],
    handler_config: Optional[str],
    validate: bool,
    strict: bool,
) -> List[str]:
    cmd: List[str] = [
        sys.executable,
        "-m",
        "tools.requirements_automation.cli",
        "--repo-root",
        repo_root,
        "--template",
        template,
        "--doc",
        doc,
        "--log-level",
        log_level,
    ]

    if dry_run:
        cmd.append("--dry-run")
    if no_commit:
        cmd.append("--no-commit")
    if max_steps is not None:
        cmd.extend(["--max-steps", str(max_steps)])
    if handler_config:
        cmd.extend(["--handler-config", handler_config])
    if validate:
        cmd.append("--validate")
    if strict:
        cmd.append("--strict")

    return cmd


def _collect_logs(*streams: tuple[str, StreamName]) -> List[LogEntry]:
    entries: List[LogEntry] = []
    for text, stream_name in streams:
        entries.extend(_parse_logs(text or "", stream_name))
    return entries


def _parse_logs(text: str, stream: StreamName) -> List[LogEntry]:
    entries: List[LogEntry] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line[0] in "{[":
            continue
        level, message = _split_log_line(line)
        if level is None:
            continue
        entries.append(LogEntry(level=level, message=message, stream=stream))
    return entries


def _split_log_line(line: str) -> tuple[Optional[LogLevel], str]:
    first, _, remainder = line.partition(" ")
    level = first.rstrip(":").upper()
    if level not in _LOG_LEVELS:
        return None, ""
    return level, remainder.strip()


def _collect_json(*streams: str) -> List[Any]:
    payloads: List[Any] = []
    for text in streams:
        payloads.extend(_extract_json_objects(text or ""))
    return payloads


def _extract_json_objects(text: str) -> List[Any]:
    results: List[Any] = []
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)

    while idx < length:
        next_obj = min((pos for pos in (text.find("{", idx), text.find("[", idx)) if pos != -1), default=-1)
        if next_obj == -1:
            break
        idx = next_obj
        try:
            obj, end = decoder.raw_decode(text, idx)
        except ValueError:
            idx += 1
            continue
        results.append(obj)
        idx = end

    return results
