# Requirements Document Style

## Document Purpose
This is a technical requirements document defining system/project specifications.

## Language Guidelines
- Use present tense declarative statements ("The system SHALL...")
- Avoid conditionals ("might", "could", "possibly")
- Be specific and measurable where possible
- Use RFC 2119 keywords appropriately: SHALL, MUST, SHOULD, MAY

## Question Generation Guidelines
- Ask about missing critical requirements (security, performance, data)
- Ask about ambiguous scope boundaries
- Ask about stakeholder priorities or constraints
- Do NOT ask questions answerable from existing context
- Target questions to specific sections (use section_target field)

## Integration Guidelines
- Convert answers into requirement-style statements
- Organize content logically (general → specific)
- Remove placeholder wording ("TBD", "to be determined")
- Preserve traceability to original questions where reasonable
- For assumptions: use bullet format, one assumption per line
- For constraints: organize under Technical/Operational/Resource subsections
