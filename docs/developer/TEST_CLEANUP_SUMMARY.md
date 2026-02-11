# Test Scripts Cleanup - February 2026

## Overview
This document summarizes the test cleanup performed on 2026-02-11 to focus on integration and validation tests for MVP delivery.

## Changes Made

### Tests Retained in `test-scripts/` (8 files)
These tests remain active for MVP and integration purposes:

**Integration Tests:**
- `test_integration.py` - Main integration test suite
- `test_e2e_prior_context.py` - End-to-end prior context integration test

**CLI Tests:**
- `test_cli_template_creation.py` - CLI template creation tests
- `test_cli_validate.py` - CLI validation tests

**Validation Tests:**
- `validate_acceptance_criteria.py` - Main acceptance criteria validation
- `validate_prior_context_acceptance_criteria.py` - Prior context acceptance criteria
- `validate_review_gate_acceptance_criteria.py` - Review gate acceptance criteria
- `validate_structural_validation_acceptance_criteria.py` - Structural validation acceptance criteria

### Tests Archived to `test-archive/` (17 files)
The following unit and manual test scripts were moved to the archive:

1. `manual_verify_draft_section.py`
2. `test_cli_validate_structure_integration.py`
3. `test_document_validator.py`
4. `test_draft_section.py`
5. `test_gather_prior_sections.py`
6. `test_handler_registry.py`
7. `test_llm_profile_integration.py`
8. `test_open_questions_validation.py`
9. `test_preserve_open_questions.py`
10. `test_prior_sections.py`
11. `test_profile_loader.py`
12. `test_review_gate_handler.py`
13. `test_review_gate_persistence.py`
14. `test_scope_config_integration.py`
15. `test_structural_validation_integration.py`
16. `test_structural_validator.py`
17. `test_unified_handler.py`

## Documentation Updates

The following documentation was updated to reflect the changes:

1. **README.md** - Updated test examples and project structure
2. **contributing.md** - Updated testing guidelines and file structure
3. **docs/llm-profiles-guide.md** - Updated test commands
4. **docs/review-gate-handler-summary.md** - Updated test file references
5. **IMPLEMENTATION_SUMMARY.md** - Updated test file references
6. **test-archive/ARCHIVE_README.md** - Created comprehensive archive documentation

## Rationale

The tests were archived to:
1. **Focus CI/CD resources** - Run only critical integration and validation tests
2. **Reduce maintenance burden** - Avoid maintaining outdated unit tests
3. **Streamline development** - Faster test execution for MVP delivery
4. **Preserve history** - Keep archived tests for potential future reference

## CI/CD Impact

**No CI/CD configuration found** - This repository does not have `.github/workflows/` or other CI/CD configuration files at the time of this cleanup. When CI/CD is added in the future, it should only run the tests in `test-scripts/`.

## Running Tests

To run the active test suite:

```bash
# Integration tests
python test-scripts/test_integration.py
python test-scripts/test_e2e_prior_context.py

# CLI tests
python test-scripts/test_cli_template_creation.py
python test-scripts/test_cli_validate.py

# Validation tests
python test-scripts/validate_acceptance_criteria.py
python test-scripts/validate_prior_context_acceptance_criteria.py
python test-scripts/validate_review_gate_acceptance_criteria.py
python test-scripts/validate_structural_validation_acceptance_criteria.py
```

## Restoring Archived Tests

If you need to restore any archived test:

1. Copy the file from `test-archive/` back to `test-scripts/`
2. Update any dependencies or imports as needed
3. Verify the test works with the current codebase
4. Consider writing new tests instead if significant changes are needed

## Related Issue

This cleanup addresses the requirements specified in the GitHub issue to remove/archive outdated unit test scripts while keeping only integration and validation tests critical for MVP delivery.
