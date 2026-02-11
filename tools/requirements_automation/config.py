from __future__ import annotations

import re

# LLM configuration for question generation and answer integration.
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

# Actor name used for reporting or audit trails.
AUTOMATION_ACTOR = "requirements-automation"

# Markers used inside markdown to delineate structure.
SECTION_MARKER_RE = re.compile(r"<!--\s*section:(?P<id>[a-z0-9_]+)\s*-->")
SECTION_LOCK_RE = re.compile(
    r"<!--\s*section_lock:(?P<id>[a-z0-9_]+)\s+lock=(?P<lock>true|false)\s*-->"
)
TABLE_MARKER_RE = re.compile(r"<!--\s*table:(?P<id>[a-z0-9_]+)\s*-->")
SUBSECTION_MARKER_RE = re.compile(r"<!--\s*subsection:(?P<id>[a-z0-9_]+)\s*-->")
META_MARKER_RE = re.compile(
    r"<!--\s*meta:(?P<key>[a-z_]+)"
    r"(?:\s+value=\"(?P<value>[^\"]+)\")?"
    r"(?:\s+version=\"(?P<version>[^\"]+)\")?\s*-->"
)

# Placeholder indicates a section still needs human input.
PLACEHOLDER_TOKEN = "<!-- PLACEHOLDER -->"

# Supported document types used for metadata-driven routing.
SUPPORTED_DOC_TYPES = ["requirements", "research", "planning"]
DEFAULT_DOC_TYPE = "requirements"
SUPPORTED_METADATA_KEYS = {"doc_type", "doc_format"}

# Expected header columns for the Open Questions table.
OPEN_Q_COLUMNS = [
    "Question ID",
    "Question",
    "Date",
    "Answer",
    "Section Target",
    "Resolution Status",
]

# Open question status values
QUESTION_STATUS_OPEN = "Open"
QUESTION_STATUS_RESOLVED = "Resolved"
QUESTION_STATUS_DEFERRED = "Deferred"

# Deprecated: Phase order controls progression through the requirements workflow.
PHASE_ORDER = [
    "phase_1_intent_scope",
    "phase_2_assumptions_constraints",
    "phase_3_requirements",
    "phase_4_interfaces_data_risks",
    "phase_5_approval",
]

# Sections required for each phase (deprecated in favor of workflow order).
PHASES = {
    "phase_1_intent_scope": [
        "problem_statement",
        "goals_objectives",
        "stakeholders_users",
        "success_criteria",
    ],
    "phase_2_assumptions_constraints": ["assumptions", "constraints"],
    "phase_3_requirements": ["requirements"],
    "phase_4_interfaces_data_risks": [
        "interfaces_integrations",
        "data_considerations",
        "risks_open_issues",
    ],
    "phase_5_approval": ["approval_record"],
}

# Workflow targets that are not section IDs (extensible prefix list).
SPECIAL_WORKFLOW_PREFIXES = ["review_gate:"]


def is_special_workflow_target(target: str) -> bool:
    return any(target.startswith(prefix) for prefix in SPECIAL_WORKFLOW_PREFIXES)


# Maps alias section IDs to canonical targets for consistency.
TARGET_CANONICAL_MAP = {
    "primary_goals": "goals_objectives",
    "secondary_goals": "goals_objectives",
    "non_goals": "goals_objectives",
}

# Review gate result marker for persistence
REVIEW_GATE_RESULT_RE = re.compile(
    r"<!--\s*review_gate_result:(?P<gate_id>[a-z0-9_:]+)"
    r"\s+status=(?P<status>passed|failed)"
    r"(?:\s+issues=(?P<issues>\d+))?"
    r"(?:\s+warnings=(?P<warnings>\d+))?\s*-->"
)

# Document completion requirements
COMPLETION_CRITERIA = {
    "no_placeholders_in_required_sections": True,  # Required sections must not have PLACEHOLDER token
    "no_open_questions": True,  # No questions with status "Open"
    "all_review_gates_pass": True,  # All review gates in workflow must pass
    "structure_valid": True,  # All structural validators pass (markers, table schema)
    "all_workflow_targets_complete": True,  # All targets in workflow order marked complete
}

# Optional criteria (can be disabled via flags)
OPTIONAL_CRITERIA = {
    "no_deferred_questions": False,  # Strict mode: even "Deferred" questions must be resolved
    "no_warnings_from_review": False,  # Strict mode: review gates must have zero warnings
}
