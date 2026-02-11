"""Formatting utilities for CLI output."""

from __future__ import annotations

from typing import List

from .models import WorkflowResult


def format_review_gate_output(result: WorkflowResult) -> str:
    """
    Format review gate results in human-readable format.

    Args:
        result: WorkflowResult from review gate execution

    Returns:
        Formatted string suitable for CLI output
    """
    if result.action_taken != "review_gate":
        return ""

    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"Review Gate: {result.target_id}")

    # Status
    status = "PASSED" if not result.blocked else "FAILED"

    # Count issues by severity
    blocker_count = len([r for r in result.blocked_reasons if r.startswith("blocker:")])
    warning_count = len([s for s in result.summaries if s.startswith("warning:")])

    if blocker_count > 0 or warning_count > 0:
        lines.append(f"Status: {status} ({blocker_count} blocker issues, {warning_count} warnings)")
    else:
        lines.append(f"Status: {status}")

    lines.append("")

    # Summary (first item in summaries is the overall summary)
    if result.summaries:
        summary = result.summaries[0]
        if not summary.startswith("blocker:") and not summary.startswith("warning:"):
            lines.append(f"Summary: {summary}")
            lines.append("")

    # Blockers
    if result.blocked_reasons:
        lines.append("Blockers:")
        for reason in result.blocked_reasons:
            # Remove "blocker:" prefix if present
            clean_reason = reason.replace("blocker:", "").strip()
            lines.append(f"  - {clean_reason}")
        lines.append("")

    # Warnings
    warnings = [s for s in result.summaries if s.startswith("warning:")]
    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            # Remove "warning:" prefix
            clean_warning = warning.replace("warning:", "").strip()
            lines.append(f"  - {clean_warning}")
        lines.append("")

    # Patches info
    # Note: We can't access patch details directly from WorkflowResult,
    # but we can indicate if patches were applied based on the changed flag
    if result.changed:
        lines.append("Patches: Auto-applied (document modified)")
    else:
        lines.append("Patches: Available for manual review (auto-apply disabled)")

    lines.append("=" * 70)
    lines.append("")

    return "\n".join(lines)
