from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class SectionSpan:
    """Line span for a top-level section marker in the requirements doc."""
    section_id: str
    start_line: int
    end_line: int

@dataclass(frozen=True)
class SubsectionSpan:
    """Line span for a subsection marker nested within a section."""
    subsection_id: str
    start_line: int
    end_line: int

@dataclass
class OpenQuestion:
    """Row model for the Open Questions tracking table."""
    question_id: str
    question: str
    date: str
    answer: str
    section_target: str
    status: str  # Open | Resolved | Deferred

@dataclass
class RunResult:
    """Outcome summary for a single automation run."""
    outcome: str  # no-op | updated | blocked | error
    changed: bool
    blocked_reasons: List[str]
