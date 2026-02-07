# Open Questions Table Schema Validation

## Overview

This document describes the Open Questions table schema enforcement system implemented to prevent schema regression and ensure consistency across all requirements documents.

## Canonical Schema

The Open Questions table MUST always use this exact schema with columns in this order:

```markdown
| Question ID | Question | Asked By | Date | Answer | Resolution Status |
```

### Column Specifications

1. **Question ID** - Unique identifier (e.g., Q-001, Q-002)
2. **Question** - The question text
3. **Asked By** - Who raised the question (e.g., Requirements Agent, Product Owner)
4. **Date** - Date the question was raised (YYYY-MM-DD format)
5. **Answer** - Human-provided answer (may be empty for new questions)
6. **Resolution Status** - One of: "Open", "Resolved", or "Deferred"

## Schema Constraints

### Mandatory Requirements
- All six columns MUST be present
- Column order MUST NOT be changed
- Columns MUST NOT be removed, renamed, or replaced
- Answer column may be empty but MUST exist
- Resolution Status MUST be one of the approved values

### Agent Behavior
- The Requirements Agent MUST include all six columns when adding new questions
- The agent MUST NOT replace the table with a reduced schema
- The agent MUST restore malformed tables when encountered
- Schema repairs MUST be logged in Revision History

## Implementation

### Schema Validation (`tools/schema_utils.py`)

The `validate_open_questions_schema()` function:
- Detects missing columns
- Detects incorrect column order
- Returns validation status and missing column list

### Schema Auto-Repair (`tools/schema_utils.py`)

The `repair_open_questions_schema()` function:
- Restores missing columns with appropriate defaults
- Corrects incorrect column order
- Preserves all existing question data
- Returns repaired document and repair status

### Invocation Script Integration (`tools/invoke_requirements_agent.py`)

The invocation script:
1. Validates schema before agent execution
2. Auto-repairs schema violations when detected
3. Emits clear warnings about corrections
4. Logs repairs in git diff for visibility

## Testing

### Schema Validation Tests (`test-scripts/test_open_questions_schema.py`)

Comprehensive test suite covering:
- Valid schema validation
- Missing column detection
- Incorrect column order detection
- Schema repair functionality
- Data preservation during repair
- Edge cases and error handling

Run tests:
```bash
python3 test-scripts/test_open_questions_schema.py
```

### Review Mode Validation Tests (`test-scripts/test_review_mode_validation.py`)

Tests for review_only mode enforcement:
- Patch-style output validation
- Full document rejection
- Malformed output rejection

Run tests:
```bash
python3 test-scripts/test_review_mode_validation.py
```

## Usage

### Manual Validation

```python
from tools.schema_utils import validate_open_questions_schema

with open('docs/requirements.md', 'r') as f:
    content = f.read()

is_valid, missing_columns, header_idx = validate_open_questions_schema(content)
if not is_valid:
    print(f"Schema violation: {missing_columns}")
```

### Manual Repair

```python
from tools.schema_utils import repair_open_questions_schema

with open('docs/requirements.md', 'r') as f:
    content = f.read()

repaired, was_repaired = repair_open_questions_schema(content)
if was_repaired:
    with open('docs/requirements.md', 'w') as f:
        f.write(repaired)
    print("Schema repaired successfully")
```

### Automatic (via Invocation Script)

The invocation script automatically validates and repairs schema:

```bash
python3 tools/invoke_requirements_agent.py < input.txt
```

Output example:
```
[Schema Validation] Checking Open Questions table schema...
⚠️  Schema violation detected: Answer, Resolution Status
🔧 Auto-repairing schema to restore missing columns...
✓ Schema repaired successfully
  Restored columns: Answer, Resolution Status
  All existing question data preserved
```

## Acceptance Criteria

✅ Open Questions table always contains all six required columns  
✅ review_only passes do not modify table structure  
✅ integrate_answers mode relies on the same schema  
✅ Schema violations are detected and corrected deterministically  
✅ Revision History reflects any schema repair actions (via git diff visibility)

## Related Files

- `docs/requirements.md` - Contains canonical schema documentation
- `agent-profiles/requirements-agent.md` - Contains agent behavior constraints
- `tools/invoke_requirements_agent.py` - Invocation script with validation
- `tools/schema_utils.py` - Validation and repair utilities
- `test-scripts/test_open_questions_schema.py` - Comprehensive test suite
- `test-scripts/test_review_mode_validation.py` - Review mode validation tests
