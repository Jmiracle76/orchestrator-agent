# Implementation Summary: Issue 3b - Preserve Stakeholders & Users Tables

## Overview
Successfully implemented preservation of `primary_stakeholders` and `end_users` tables during LLM drafting operations for the stakeholders_users section.

## Problem Statement
The LLM was not instructed to preserve table format when drafting content for the stakeholders_users section, which could result in prose replacing the structured tables.

## Root Cause
The `stakeholders_users` section had `subsections: false` in the handler configuration, which prevented the subsection structure (including table type information) from being passed to the LLM prompts.

## Solution
Updated the handler configuration in `tools/config/handler_registry.yaml` to set `subsections: true` for the stakeholders_users section. This enables:

1. **Subsection Structure Building**: The `_build_subsection_structure()` function identifies `primary_stakeholders` and `end_users` as table subsections (already defined in `TABLE_SUBSECTIONS`)

2. **LLM Prompt Instructions**: The `_build_subsection_guidance()` function generates clear instructions for the LLM:
   - "Output: Markdown table rows only (no header, just data rows with pipe delimiters)"

3. **Content Preservation**: The existing `replace_block_body_preserving_markers()` function preserves all subsection markers, headers, and table content

## Changes Made

### Configuration Change
**File**: `tools/config/handler_registry.yaml`
```yaml
stakeholders_users:
  mode: integrate_then_questions
  output_format: prose
  subsections: true  # Changed from false to true
  # ... rest of config
```

### Test Files Added
1. **test_stakeholders_users_tables.py** - Unit tests for table preservation
   - Test 1: Verify table markers and data preserved during editing
   - Test 2: Verify subsection structure built correctly with table types

2. **test_stakeholders_users_e2e.py** - End-to-end integration tests
   - Test 1: Draft section preserves table subsections with data rows
   - Test 2: Subsection structure correctly identifies table types

3. **verify_stakeholders_prompt.py** - Prompt verification
   - Validates LLM receives table format instructions

4. **validate_issue_3b.py** - Acceptance criteria validation
   - Comprehensive validation of all requirements

## Acceptance Criteria - SATISFIED ✅

### ✅ Primary stakeholders table preserved with data rows after drafting
- Subsection structure passed to LLM with type='table'
- LLM instructed: "Markdown table rows only"
- Table markers and headers preserved by editing logic
- Verified by: test_stakeholders_users_e2e.py

### ✅ End users table preserved with data rows after drafting
- Subsection structure passed to LLM with type='table'
- LLM instructed: "Markdown table rows only"
- Table markers and headers preserved by editing logic
- Verified by: test_stakeholders_users_e2e.py

### ✅ Questions & Issues table preserved
- questions_issues subsection excluded from content structure
- LLM will not overwrite questions_issues subsection
- Table content preserved by boundary calculation logic
- Verified by: test_stakeholders_users_tables.py

## Testing Results

### New Tests
```
✅ test_stakeholders_users_tables.py     : 2/2 tests passed
✅ test_stakeholders_users_e2e.py        : 2/2 tests passed
✅ verify_stakeholders_prompt.py         : All validations passed
✅ validate_issue_3b.py                  : All criteria satisfied
```

### Regression Testing
```
✅ test_subsection_preservation.py       : 5/5 tests passed
✅ test_goals_objectives_subsections.py  : 3/3 tests passed
✅ test_goals_objectives_e2e.py          : 3/3 tests passed
```

### Security
```
✅ CodeQL Analysis: 0 vulnerabilities found
✅ Code Review: No issues found
```

## Technical Details

### How It Works

1. **Configuration Loading**: Handler registry loads stakeholders_users config with `subsections: true`

2. **Structure Building**: When processing stakeholders_users section:
   ```python
   structure = _build_subsection_structure(lines, span, handler_config)
   # Returns: [
   #   {"id": "primary_stakeholders", "type": "table"},
   #   {"id": "end_users", "type": "table"}
   # ]
   ```

3. **Prompt Generation**: LLM prompt includes subsection guidance:
   ```
   **Subsection Structure:**
   This section has the following subsections. Output content using subsection delimiters:

   ### Primary Stakeholders
   Output: Markdown table rows only (no header, just data rows with pipe delimiters).

   ### End Users
   Output: Markdown table rows only (no header, just data rows with pipe delimiters).
   ```

4. **Content Replacement**: The editing function preserves:
   - Subsection markers: `<!-- subsection:primary_stakeholders -->`
   - Table markers: `<!-- table:primary_stakeholders -->`
   - Section headers: `### Primary Stakeholders`
   - Table headers: `| Stakeholder | Role | Interest/Need | Contact |`
   - Existing table content

### Key Code Components

- **TABLE_SUBSECTIONS** (runner_integration.py): Defines which subsections contain tables
  ```python
  TABLE_SUBSECTIONS = {
      "primary_stakeholders",
      "end_users",
      "external_systems",
      "data_exchange",
      "risks",
  }
  ```

- **_build_subsection_structure()** (runner_integration.py): Builds subsection metadata
  - Filters out question subsections
  - Maps subsection IDs to types (table, bullets, prose)

- **_build_subsection_guidance()** (llm_prompts.py): Generates LLM instructions
  - For type='table': "Output: Markdown table rows only"
  - For type='bullets': "Output: Bullet list items"
  - For type='prose': "Output: Prose or list as appropriate"

- **replace_block_body_preserving_markers()** (editing.py): Safe content replacement
  - Preserves all subsection markers and their content
  - Only replaces the section preamble

## Impact

### Minimal Changes
- ✅ Only 1 line changed in production code (configuration file)
- ✅ No changes to core logic or algorithms
- ✅ Leverages existing infrastructure

### Extensibility
This pattern can be applied to any section with table subsections:
- Already working for goals_objectives (bullet subsections)
- Can be extended to interfaces_integrations (external_systems, data_exchange tables)
- Can be extended to identified_risks (risks table)

## Dependencies
This implementation depends on Issues 2a and 2b as specified:
- Issue 2a: Per-section question tables (provides questions_issues subsection)
- Issue 2b: Bootstrap questions from template (provides initial question rows)

## Verification Steps
To verify this implementation works:

1. Run the validation script:
   ```bash
   python test-scripts/validate_issue_3b.py
   ```

2. Run the test suite:
   ```bash
   python test-scripts/test_stakeholders_users_tables.py
   python test-scripts/test_stakeholders_users_e2e.py
   ```

3. Manual testing (if needed):
   - Create a requirements document with stakeholders_users section
   - Run draft_section command for stakeholders_users
   - Verify table structure is preserved with data rows

## Conclusion
The implementation successfully addresses all acceptance criteria with minimal changes. The solution leverages existing infrastructure and follows established patterns, ensuring maintainability and consistency with the rest of the codebase.

---
**Security Summary**: No security vulnerabilities found (CodeQL analysis: 0 alerts)
**Review Status**: Code review completed with no issues
**Test Coverage**: All new tests pass, no regressions in existing tests
