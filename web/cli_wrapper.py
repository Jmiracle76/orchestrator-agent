from __future__ import annotations

import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, List, Literal, Optional

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


def stream_requirements_cli(
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
    on_output_line: Optional[Callable[[str, StreamName], None]] = None,
    on_log: Optional[Callable[[LogEntry], None]] = None,
) -> CLIWrapperResult:
    """
    Run the requirements automation CLI while streaming output lines to callbacks.

    Captures stdout/stderr incrementally to keep callers updated during long-lived runs.
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
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
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

    assert process.stdout is not None
    assert process.stderr is not None

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    parsed_logs: list[LogEntry] = []

    def _pump_stream(stream, collector: list[str], stream_name: StreamName):
        for raw in iter(stream.readline, ""):
            collector.append(raw)
            if on_output_line:
                on_output_line(raw.rstrip("\n"), stream_name)
            entry = _log_entry_from_line(raw, stream_name)
            if entry:
                parsed_logs.append(entry)
                if on_log:
                    on_log(entry)
        stream.close()

    stdout_thread = threading.Thread(
        target=_pump_stream, args=(process.stdout, stdout_lines, "stdout"), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_pump_stream, args=(process.stderr, stderr_lines, "stderr"), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    status: Literal["success", "error", "timeout"]
    error: Optional[str] = None
    exit_code: Optional[int]
    try:
        process.wait(timeout=timeout)
        exit_code = process.returncode
        status = "success" if exit_code == 0 else "error"
        if status == "error":
            error = f"Process exited with code {exit_code}"
    except subprocess.TimeoutExpired:
        process.kill()
        status = "timeout"
        exit_code = None
        error = f"Process timed out after {timeout} seconds"

    stdout_thread.join()
    stderr_thread.join()

    stdout = "".join(stdout_lines)
    stderr = "".join(stderr_lines)

    return CLIWrapperResult(
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        logs=parsed_logs,
        json_blocks=_collect_json(stdout, stderr),
        command=command,
        error=error,
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


def _log_entry_from_line(line: str, stream: StreamName) -> Optional[LogEntry]:
    level, message = _split_log_line(line.strip())
    if level is None:
        return None
    return LogEntry(level=level, message=message, stream=stream)


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
