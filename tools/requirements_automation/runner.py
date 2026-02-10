from __future__ import annotations
from typing import List, Tuple
from .config import PHASES, is_special_workflow_target
from .validators import validate_section_complete
from .phases import process_phase_1, process_phase_2, process_placeholder_phase

def choose_next_target(lines: List[str], workflow_order: List[str]) -> Tuple[str, bool]:
    """Return the next incomplete workflow target and whether all are complete."""
    if not workflow_order:
        raise ValueError("Workflow order is empty.")
    for target in workflow_order:
        if is_special_workflow_target(target):
            return target, False
        complete, _ = validate_section_complete(target, lines)
        if not complete:
            return target, False
    return workflow_order[-1], True

def run_phase(target: str, lines, llm, dry_run: bool, doc_type: str | None = None):
    """Dispatch to the appropriate phase handler."""
    if target in PHASES["phase_1_intent_scope"]:
        return process_phase_1(lines, llm, dry_run, target_section=target)
    if target in PHASES["phase_2_assumptions_constraints"]:
        return process_phase_2(lines, llm, dry_run, target_section=target)
    return process_placeholder_phase(target, lines, llm, dry_run)
