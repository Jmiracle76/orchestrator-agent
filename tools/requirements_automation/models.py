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

@dataclass(frozen=True)
class WorkflowResult:
    """Result from executing a single workflow target."""
    target_id: str              # Section or review gate ID processed
    action_taken: str           # "question_gen", "integration", "review", "skip_locked", "no_action", "complete"
    changed: bool               # Document modified?
    blocked: bool               # Needs human intervention?
    blocked_reasons: List[str]  # Why blocked (e.g., "unanswered questions")
    summaries: List[str]        # Human-readable action descriptions
    questions_generated: int    # Count of new questions
    questions_resolved: int     # Count of resolved questions

@dataclass(frozen=True)
class SectionState:
    """State information for a section target."""
    section_id: str
    exists: bool
    locked: bool
    is_blank: bool
    has_placeholder: bool
    has_open_questions: bool
    has_answered_questions: bool

@dataclass(frozen=True)
class HandlerConfig:
    """Configuration for how a section should be processed."""
    section_id: str
    mode: str  # "integrate_then_questions", "questions_then_integrate", "review_gate"
    output_format: str  # "prose", "bullets", "subsections"
    subsections: bool  # allow subsection targeting?
    dedupe: bool  # deduplicate similar content?
    preserve_headers: List[str]  # headers to preserve during rewrite
    sanitize_remove: List[str]  # patterns to remove from LLM output
    llm_profile: str  # profile name (references profiles/ directory)
    auto_apply_patches: bool  # for review gates only
    scope: str  # for review gates: "all_prior_sections", "current_section"
