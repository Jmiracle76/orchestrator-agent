from __future__ import annotations
from typing import Tuple
from .config import PHASE_ORDER
from .validators import validate_phase_1_complete, validate_phase_2_complete
from .phases import process_phase_1, process_phase_2, process_placeholder_phase

def choose_phase(lines) -> Tuple[str, bool]:
    for ph in PHASE_ORDER:
        if ph == "phase_1_intent_scope":
            complete, _ = validate_phase_1_complete(lines)
        elif ph == "phase_2_assumptions_constraints":
            p1_complete, _ = validate_phase_1_complete(lines)
            complete = False if not p1_complete else validate_phase_2_complete(lines)[0]
        else:
            complete = False
        if not complete:
            return ph, False
    return PHASE_ORDER[-1], True

def run_phase(phase: str, lines, llm, dry_run: bool):
    if phase == "phase_1_intent_scope":
        return process_phase_1(lines, llm, dry_run)
    if phase == "phase_2_assumptions_constraints":
        return process_phase_2(lines, llm, dry_run)
    return process_placeholder_phase(phase, lines, llm, dry_run)
