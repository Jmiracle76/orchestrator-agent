# Per-Section Question Management

## Overview

As of version 1.0, the orchestrator-agent has replaced the single global "Open Questions" table with per-section "Questions & Issues" tables. This provides better isolation, traceability, and section-scoped question management.

## What Changed

### Before (Global Questions)
- Single `Open Questions` table in the `risks_open_issues` section
- Global namespace for question IDs (Q-001, Q-002, etc.)
- Questions tagged with `Section Target` column to indicate which section they belong to

### After (Per-Section Questions)
- Each core section (2-6) has its own `Questions & Issues` subsection
- Section-scoped question IDs (e.g., `problem_statement-Q1`, `goals_objectives-Q1`)
- Better isolation and no need for section target tagging

## Sections with Question Tables

The following sections now have per-section question tables:

1. **Problem Statement** (`problem_statement`)
   - Table: `problem_statement_questions`
   - Bootstrap questions about pain points, users, and consequences

2. **Goals and Objectives** (`goals_objectives`)
   - Table: `goals_objectives_questions`
   - Bootstrap questions about success indicators, alignment, and dependencies

3. **Stakeholders and Users** (`stakeholders_users`)
   - Table: `stakeholders_users_questions`
   - Bootstrap questions about stakeholder identification, communication, and conflicts

4. **Success Criteria** (`success_criteria`)
   - Table: `success_criteria_questions`
   - Bootstrap questions about measurement and verification

5. **Assumptions** (`assumptions`)
   - Table: `assumptions_questions`
   - Bootstrap questions about validation and impact

6. **Constraints** (`constraints`)
   - Table: `constraints_questions`
   - Bootstrap questions about workarounds and prioritization

## Question Table Format

Each section's question table has the following structure:

```markdown
<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:SECTION_ID_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| SECTION_ID-Q1 | Question text | YYYY-MM-DD | | Open |
```

Note the differences from the global table:
- **5 columns** instead of 6 (no `Section Target` column needed)
- **Section-scoped IDs** (e.g., `problem_statement-Q1` instead of `Q-001`)
- **Status values**: `Open`, `Resolved`, `Deferred`

## Backward Compatibility

The implementation maintains **full backward compatibility**:

1. **Global questions still work**: Documents with the old global `Open Questions` table continue to function
2. **Automatic fallback**: If a section doesn't have a per-section table, the system automatically falls back to the global table
3. **Dual support**: The workflow runner checks both section-specific and global tables

## Migration

To convert existing documents from global to per-section questions:

```bash
python tools/requirements_automation/migrate_questions.py --doc path/to/requirements.md
```

The migration tool:
1. Parses the global `Open Questions` table
2. Distributes questions to appropriate section tables based on `Section Target`
3. Updates question IDs to section-scoped format (e.g., `Q-001` → `problem_statement-Q1`)
4. Preserves the global table for backward compatibility

## Handler Configuration

Sections are configured in `tools/config/handler_registry.yaml`:

```yaml
requirements:
  problem_statement:
    mode: integrate_then_questions
    questions_table: problem_statement_questions  # Per-section table
    bootstrap_questions: true  # Use bootstrap questions from template
    # ... other config
```

## API Changes

### New Functions

**`section_questions.py`** - New module for per-section question management:

- `parse_section_questions(lines, section_id)` - Parse section-specific questions
- `insert_section_question(lines, section_id, question, date)` - Insert single question
- `insert_section_questions_batch(lines, section_id, questions)` - Insert multiple questions
- `resolve_section_question(lines, section_id, question_id)` - Mark question as resolved
- `resolve_section_questions_batch(lines, section_id, question_ids)` - Resolve multiple questions
- `has_open_section_questions(lines, section_id)` - Check for open questions
- `section_has_answered_questions(lines, section_id)` - Check for answered questions

### Updated Functions

**`runner_state.py`**:
- `get_section_state(lines, target_id, handler_config=None)` - Now accepts optional handler_config to determine which question table to use

**`runner_integration.py`**:
- `integrate_answered_questions()` - Now supports both global and section-specific tables
- `generate_questions_for_section()` - Routes questions to appropriate table

## Testing

Run the test suite to verify section questions functionality:

```bash
# Focused tests for section questions
python test-scripts/test_section_questions.py

# Integration tests
python test-scripts/test_integration.py
```

## Benefits

1. **Better Isolation**: Questions are isolated to their respective sections
2. **Clearer Organization**: No need to scan a global table for relevant questions
3. **Scoped IDs**: Question IDs are self-documenting (e.g., `problem_statement-Q1`)
4. **Easier Navigation**: Questions appear directly in the section they relate to
5. **Better Traceability**: Direct link between questions and section content

## Future Considerations

- Consider removing global questions table support in a future major version
- Add section-specific question templates for other document types
- Enhance migration tool to handle edge cases
