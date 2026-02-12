# Coherence Check Review Gate

## Overview
The `review_gate:coherence_check` gate enforces automated validation before allowing progression to later sections. It verifies that all prior sections are complete and all risks are properly mitigated.

## Automated Checks

### 1. Section Question Tables
The gate checks all section-level question tables (e.g., `problem_statement_questions`, `assumptions_questions`, etc.) for any "Open" status rows.

**Pass Condition:** Zero "Open" status questions in all prior section tables.

**Example blocking scenario:**
```markdown
<!-- table:problem_statement_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| Q1 | What is the scope? | 2024-01-01 | TBD | Open |  ← BLOCKS GATE
```

**Example passing scenario:**
```markdown
<!-- table:problem_statement_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| Q1 | What is the scope? | 2024-01-01 | Project X | Resolved |  ← PASSES
```

### 2. Risks Table
The gate checks the `<!-- table:risks -->` to ensure all risks have both **Probability** and **Impact** set to "Low".

**Pass Condition:** All risks must have Probability=Low AND Impact=Low.

**Example blocking scenario:**
```markdown
<!-- table:risks -->
| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| R1 | Data breach | High | High | Encryption | Security |  ← BLOCKS GATE
```

**Example passing scenario:**
```markdown
<!-- table:risks -->
| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| R1 | Minor delay | Low | Low | Buffer time | PM |  ← PASSES
```

## Actions on Pass

When the gate passes, it automatically:

### 1. Locks All Prior Sections
All sections before the gate in the workflow order are locked with `lock=true`:

```markdown
<!-- section_lock:problem_statement lock=true -->
<!-- section_lock:goals_objectives lock=true -->
<!-- section_lock:stakeholders_users lock=true -->
... (all sections before the gate)
```

Locked sections cannot be modified by the automation system, preserving the approved content.

### 2. Updates Approval Record
The `<!-- table:approval_record -->` is updated with:
- Current Status: "Coherence Check Passed"
- Recommended By: "requirements-automation"
- Recommendation Date: Current date (YYYY-MM-DD)

```markdown
<!-- table:approval_record -->
| Field | Value |
|-------|-------|
| Current Status | Coherence Check Passed |
| Recommended By | requirements-automation |
| Recommendation Date | 2024-02-12 |
```

## Workflow Integration

The gate is typically placed in the workflow order after initial sections but before detailed requirements:

```markdown
<!-- workflow:order
problem_statement
goals_objectives
stakeholders_users
success_criteria
assumptions
constraints
review_gate:coherence_check  ← Gate enforces validation here
requirements
interfaces_integrations
data_considerations
identified_risks
review_gate:final_review
approval_record
-->
```

## Fixing Blocked Gates

If the gate blocks, the system provides specific reasons:

### For Open Questions:
1. Review all section question tables
2. Resolve or defer open questions
3. Update status column to "Resolved" or "Deferred"
4. Provide answers in the Answer column

### For High-Risk Items:
1. Review the risks table
2. Update mitigation strategies
3. Re-assess Probability and Impact
4. Set both to "Low" once properly mitigated

## Testing

Run the coherence gate tests:
```bash
python3 test-scripts/test_coherence_gate.py
python3 test-scripts/test_coherence_gate_e2e.py
```

## Configuration

The gate configuration in `tools/config/handler_registry.yaml`:
```yaml
review_gate:coherence_check:
  mode: review_gate
  output_format: prose
  subsections: false
  dedupe: false
  preserve_headers: []
  sanitize_remove: []
  llm_profile: requirements_review
  auto_apply_patches: never
  scope: all_prior_sections  # Reviews all sections before this gate
  validation_rules:
    - no_contradictions
    - no_missing_critical_sections
    - consistent_terminology
```

## Implementation Details

### Key Functions
- `check_section_table_for_open_questions()`: Validates section question tables
- `check_risks_table_for_non_low_risks()`: Validates risks table
- `set_section_lock()`: Locks a section programmatically
- `update_approval_record_table()`: Updates approval fields

### Handler Logic
The `ReviewGateHandler` class orchestrates the validation:
1. Performs automated checks before LLM review
2. Returns early with blockers if validation fails
3. Calls LLM for additional review if automated checks pass
4. Applies locking and approval updates on full pass

See `tools/requirements_automation/review_gate_handler.py` for implementation.
