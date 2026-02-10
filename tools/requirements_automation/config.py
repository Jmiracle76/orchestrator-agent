from __future__ import annotations
import re

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000

AUTOMATION_ACTOR = "requirements-automation"

SECTION_MARKER_RE = re.compile(r"<!--\s*section:(?P<id>[a-z0-9_]+)\s*-->")
SECTION_LOCK_RE   = re.compile(r"<!--\s*section_lock:(?P<id>[a-z0-9_]+)\s+lock=(?P<lock>true|false)\s*-->")
TABLE_MARKER_RE   = re.compile(r"<!--\s*table:(?P<id>[a-z0-9_]+)\s*-->")
SUBSECTION_MARKER_RE = re.compile(r"<!--\s*subsection:(?P<id>[a-z0-9_]+)\s*-->")

PLACEHOLDER_TOKEN = "<!-- PLACEHOLDER -->"

OPEN_Q_COLUMNS = [
    "Question ID",
    "Question",
    "Date",
    "Answer",
    "Section Target",
    "Resolution Status",
]

PHASE_ORDER = [
    "phase_1_intent_scope",
    "phase_2_assumptions_constraints",
    "phase_3_requirements",
    "phase_4_interfaces_data_risks",
    "phase_5_approval",
]

PHASES = {
    "phase_1_intent_scope": ["problem_statement", "goals_objectives", "stakeholders_users", "success_criteria"],
    "phase_2_assumptions_constraints": ["assumptions", "constraints"],
    "phase_3_requirements": ["requirements"],
    "phase_4_interfaces_data_risks": ["interfaces_integrations", "data_considerations", "risks_open_issues"],
    "phase_5_approval": ["approval_record"],
}

TARGET_CANONICAL_MAP = {
    "primary_goals": "goals_objectives",
    "secondary_goals": "goals_objectives",
    "non_goals": "goals_objectives",
}
