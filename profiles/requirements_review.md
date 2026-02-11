# Requirements Review Style

## Review Objective
Validate completeness, consistency, and quality of requirements sections.

## Review Criteria
- Completeness: Are critical requirements areas covered?
- Consistency: Do sections contradict each other?
- Clarity: Are requirements unambiguous and testable?
- Feasibility: Are there obvious impossibilities or conflicts?

## Output Format
Return JSON with:
- `pass`: boolean (true if no blocking issues)
- `issues`: array of {"severity": "blocker|warning", "section": "...", "description": "..."}
- `patches`: array of {"section": "...", "suggestion": "...", "rationale": "..."} (optional)

## Issue Severity Guidelines
- **Blocker**: Missing critical sections, contradictory requirements, impossible constraints
- **Warning**: Ambiguous wording, missing details, inconsistent formatting

## Patching Guidelines
- Only suggest patches for objective errors (typos, formatting, obvious omissions)
- Do not suggest patches for subjective improvements
- Patches must be unambiguous and mechanically applicable
