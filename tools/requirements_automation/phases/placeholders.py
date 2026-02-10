from __future__ import annotations
from typing import List, Tuple

def process_placeholder_phase(phase_name: str, lines: List[str], *_args, **_kwargs) -> Tuple[List[str], bool, List[str], bool, List[str]]:
    """Return a consistent blocked response for unimplemented phases."""
    return lines, False, [f"{phase_name} not implemented yet"], True, []
