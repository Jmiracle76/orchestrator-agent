from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class SectionSpan:
    section_id: str
    start_line: int
    end_line: int

@dataclass(frozen=True)
class SubsectionSpan:
    subsection_id: str
    start_line: int
    end_line: int

@dataclass
class OpenQuestion:
    question_id: str
    question: str
    date: str
    answer: str
    section_target: str
    status: str  # Open | Resolved | Deferred

@dataclass
class RunResult:
    outcome: str  # no-op | updated | blocked | error
    changed: bool
    blocked_reasons: List[str]
