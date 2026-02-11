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
    auto_apply_patches: str  # for review gates: "never", "always", "if_validation_passes"
    scope: str  # for review gates: "all_prior_sections", "entire_document", "sections:X,Y,Z"
    validation_rules: List[str]  # for review gates: list of validation rules to apply

@dataclass(frozen=True)
class ReviewIssue:
    """Single issue found during review gate execution."""
    severity: str  # "blocker", "warning"
    section: str   # section ID where issue found
    description: str
    suggestion: Optional[str]  # optional fix suggestion

@dataclass(frozen=True)
class ReviewPatch:
    """Suggested patch to fix an issue found during review."""
    section: str       # section ID to patch
    suggestion: str    # proposed replacement content
    rationale: str     # why this patch is needed
    validated: bool    # passed structural validation?

@dataclass(frozen=True)
class ReviewResult:
    """Result from executing a review gate."""
    gate_id: str
    passed: bool       # true if no blocking issues
    issues: List[ReviewIssue]
    patches: List[ReviewPatch]
    scope_sections: List[str]  # sections actually reviewed
    summary: str       # human-readable summary

@dataclass(frozen=True)
class CompletionCheck:
    """Individual completion criterion check result."""
    criterion: str          # Which completion criterion
    passed: bool           # Did this criterion pass?
    details: str           # Human-readable explanation
    blocking: bool         # Is this a blocking failure?

@dataclass(frozen=True)
class CompletionStatus:
    """Overall document completion status."""
    complete: bool                    # Overall: document meets all criteria?
    checks: List[CompletionCheck]     # Individual criterion results
    blocking_failures: List[str]      # List of blocking criterion names that failed
    warnings: List[str]               # Non-blocking issues
    summary: str                      # Human-readable overall status
