# Issue 3f: Interfaces & Integrations and Data Considerations – Clearer Formatting - Validation Report

**Issue:** Ensure interfaces_integrations tables (external_systems, data_exchange) and data_considerations subsections (data_requirements, privacy_security, data_retention) are preserved and clearly formatted after LLM drafting.

**Status:** ✅ COMPLETE - All acceptance criteria satisfied

## Acceptance Criteria

### ✅ 1. All interface tables preserved after drafting
**Status:** VERIFIED

**Evidence:**
- Test file: `test-scripts/test_interfaces_integrations_subsections.py`
- All 3 unit tests pass
- Tests verify both table subsections (external_systems, data_exchange) are preserved after content replacement
- Tests verify table markers (`<!-- table:external_systems -->`, `<!-- table:data_exchange -->`) are preserved
- Tests verify table headers and content are not replaced with prose
- Tests verify Questions & Issues table is also preserved

**Test Results:**
```
Test 1: Table subsections preserved in interfaces_integrations ✓
Test 2: Subsection preservation with existing table content ✓
Test 3: Empty preamble with subsections containing table content ✓
```

### ✅ 2. All data consideration subsections preserved after drafting
**Status:** VERIFIED

**Evidence:**
- Test file: `test-scripts/test_data_considerations_subsections.py`
- All 3 unit tests pass
- Tests verify all three subsections (data_requirements, privacy_security, data_retention) are preserved after content replacement
- Tests verify subsection markers (`<!-- subsection:data_requirements -->`, etc.) are preserved
- Tests verify bullet list structure within each subsection is preserved
- Tests verify Questions & Issues table is also preserved

**Test Results:**
```
Test 1: All subsections preserved in data_considerations ✓
Test 2: Subsection preservation with existing bullet list content ✓
Test 3: Empty preamble with subsections containing bullet lists ✓
```

### ✅ 3. Questions & Issues tables preserved (once added per 1a)
**Status:** VERIFIED

**Evidence:**
- Both test suites verify Questions & Issues table preservation
- Table marker `<!-- table:interfaces_integrations_questions -->` is preserved in interfaces_integrations section
- Table marker `<!-- table:data_considerations_questions -->` is preserved in data_considerations section
- Questions & Issues subsection is correctly excluded from content structure (it's metadata, not drafted content)

## Implementation Details

### Handler Registry Configuration

**File:** `tools/config/handler_registry.yaml`

#### interfaces_integrations (lines 124-135)
```yaml
interfaces_integrations:
  mode: integrate_then_questions
  output_format: prose
  subsections: true  # supports external_systems, data_exchange subsections with table content
  dedupe: false
  preserve_headers: []
  sanitize_remove: []
  llm_profile: requirements
  auto_apply_patches: never
  scope: all_prior_sections
  questions_table: interfaces_integrations_questions  # Per-section question table
  bootstrap_questions: true  # Pre-populate from template
```

**Key Changes:**
- ✅ `subsections: true` - Enables subsection preservation
- ✅ `questions_table: interfaces_integrations_questions` - Configures per-section question table
- ✅ `bootstrap_questions: true` - Pre-populates questions from template

#### data_considerations (lines 137-148)
```yaml
data_considerations:
  mode: integrate_then_questions
  output_format: bullets
  subsections: true  # supports data_requirements, privacy_security, data_retention subsections
  dedupe: false
  preserve_headers: []
  sanitize_remove: []
  llm_profile: requirements
  auto_apply_patches: never
  scope: all_prior_sections
  questions_table: data_considerations_questions  # Per-section question table
  bootstrap_questions: true  # Pre-populate from template
```

**Key Changes:**
- ✅ `subsections: true` - Enables subsection preservation
- ✅ `output_format: bullets` - Matches bullet list format in subsections
- ✅ `questions_table: data_considerations_questions` - Configures per-section question table
- ✅ `bootstrap_questions: true` - Pre-populates questions from template

### Subsection Structure Detection

**File:** `tools/requirements_automation/runner_integration.py`

The `_build_subsection_structure()` function (lines 37-85) correctly identifies subsections and their types:

**For interfaces_integrations:**
```python
structure = [
    {'id': 'external_systems', 'type': 'table'},
    {'id': 'data_exchange', 'type': 'table'}
]
```

**For data_considerations:**
```python
structure = [
    {'id': 'data_requirements', 'type': 'bullets'},
    {'id': 'privacy_security', 'type': 'bullets'},
    {'id': 'data_retention', 'type': 'bullets'}
]
```

The `TABLE_SUBSECTIONS` set (lines 28-34) correctly includes:
- ✅ `external_systems`
- ✅ `data_exchange`

This ensures these subsections are recognized as table format and not converted to prose during LLM drafting.

### Template Structure

**File:** `docs/templates/requirements-template.md`

#### interfaces_integrations (lines 259-288)
```markdown
<!-- section:interfaces_integrations -->
## 8. Interfaces and Integrations

<!-- subsection:external_systems -->
### External Systems

<!-- table:external_systems -->
| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|

<!-- subsection:data_exchange -->
### Data Exchange

<!-- table:data_exchange -->
| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:interfaces_integrations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
```

#### data_considerations (lines 290-318)
```markdown
<!-- section:data_considerations -->
## 9. Data Considerations

<!-- subsection:data_requirements -->
### Data Requirements
- [Data entity 1] 
- [Data entity 2] 

<!-- subsection:privacy_security -->
### Privacy & Security
- [Privacy consideration] 
- [Security consideration] 

<!-- subsection:data_retention -->
### Data Retention
- [Retention policy 1] 
- [Retention policy 2] 

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:data_considerations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
```

**Template Verification:**
- ✅ All subsection markers present
- ✅ All table markers present
- ✅ Questions & Issues tables configured with correct names
- ✅ Bullet list structure preserved in data_considerations subsections
- ✅ Table structure preserved in interfaces_integrations subsections

## Integration Tests

**File:** `test-scripts/test_interfaces_data_integration.py`

Integration tests verify the complete workflow:

1. ✅ Handler registry correctly configured for interfaces_integrations
2. ✅ Handler registry correctly configured for data_considerations
3. ✅ Subsection structure building identifies external_systems and data_exchange as table type
4. ✅ Subsection structure building identifies data_requirements, privacy_security, data_retention as bullets type
5. ✅ Questions & Issues subsections correctly excluded from content structure

**Test Results:**
```
Test 1: interfaces_integrations handler configuration ✓
Test 2: data_considerations handler configuration ✓
Test 3: interfaces_integrations subsection structure building ✓
Test 4: data_considerations subsection structure building ✓
```

## Existing Tests Verification

All existing subsection preservation tests continue to pass:

- ✅ `test-scripts/test_goals_objectives_subsections.py` (3/3 tests pass)
- ✅ `test-scripts/test_subsection_preservation.py` (5/5 tests pass)

This confirms that our changes:
1. Do not break existing functionality
2. Follow the same patterns as previous subsection preservation implementations
3. Are consistent with the existing codebase

## Dependencies

This implementation builds on previous work:

### ✅ Issue 2a: Marker protection in replace_block_body
**Implementation:** `tools/requirements_automation/editing.py`
- Function: `replace_block_body_preserving_markers()`
- Preserves all subsection markers when replacing section content
- Only replaces preamble (content before first subsection)
- All subsections and their content remain intact

### ✅ Issue 2b: Per-subsection LLM prompts
**Implementation:** `tools/requirements_automation/llm_prompts.py`
- Function: `_build_subsection_guidance()`
- Builds subsection structure information for LLM prompts
- All three LLM prompt builders accept `subsection_structure` parameter:
  - `build_draft_section_prompt()`
  - `build_integrate_answers_prompt()`
  - `build_open_questions_prompt()`

### ✅ Issue 3a: Goals & Objectives Subsection Preservation
**Implementation:** Established patterns for subsection preservation
- Handler registry configuration with `subsections: true`
- Per-section question tables
- Bootstrap questions from template
- Subsection structure building and type detection

## Summary

This implementation ensures that:

1. **interfaces_integrations section:**
   - external_systems table is preserved (not replaced with prose)
   - data_exchange table is preserved (not replaced with prose)
   - Table structure and content are maintained during LLM drafting
   - Questions & Issues table is preserved

2. **data_considerations section:**
   - data_requirements subsection retains its bullet list structure
   - privacy_security subsection retains its bullet list structure
   - data_retention subsection retains its bullet list structure
   - Questions & Issues table is preserved

3. **Handler configuration:**
   - Both sections configured with `subsections: true`
   - Per-section question tables configured
   - Bootstrap questions enabled
   - Appropriate output formats set (prose for interfaces, bullets for data_considerations)

4. **Subsection structure detection:**
   - external_systems and data_exchange correctly identified as table type
   - data_requirements, privacy_security, data_retention correctly identified as bullets type
   - Questions & Issues subsections correctly excluded from content structure

All acceptance criteria have been met and verified through comprehensive unit and integration tests.
