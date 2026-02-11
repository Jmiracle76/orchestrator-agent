# Test Archive

This directory contains archived unit and manual test scripts that were moved from `test-scripts/` as part of cleanup to focus on integration and validation tests only.

## Archived Tests

The following test files were archived on 2026-02-11:

### Unit Tests
- `manual_verify_draft_section.py` - Manual verification script for draft section functionality
- `test_cli_validate_structure_integration.py` - CLI structure validation integration test
- `test_document_validator.py` - Document validator unit tests
- `test_draft_section.py` - Draft section unit tests
- `test_gather_prior_sections.py` - Prior sections gathering unit tests
- `test_handler_registry.py` - Handler registry unit tests
- `test_llm_profile_integration.py` - LLM profile integration tests
- `test_open_questions_validation.py` - Open questions validation tests
- `test_preserve_open_questions.py` - Open questions preservation tests
- `test_prior_sections.py` - Prior sections unit tests
- `test_profile_loader.py` - Profile loader unit tests
- `test_review_gate_handler.py` - Review gate handler unit tests
- `test_review_gate_persistence.py` - Review gate persistence tests
- `test_scope_config_integration.py` - Scope configuration integration tests
- `test_structural_validation_integration.py` - Structural validation integration tests
- `test_structural_validator.py` - Structural validator unit tests
- `test_unified_handler.py` - Unified handler unit tests

## Active Tests (Remaining in test-scripts/)

The following tests remain active for MVP and integration purposes:

### Integration Tests
- `test_integration.py` - Main integration test suite
- `test_e2e_prior_context.py` - End-to-end prior context integration test

### CLI Tests
- `test_cli_template_creation.py` - CLI template creation tests
- `test_cli_validate.py` - CLI validation tests

### Validation Tests
- `validate_acceptance_criteria.py` - Main acceptance criteria validation
- `validate_prior_context_acceptance_criteria.py` - Prior context acceptance criteria
- `validate_review_gate_acceptance_criteria.py` - Review gate acceptance criteria
- `validate_structural_validation_acceptance_criteria.py` - Structural validation acceptance criteria

## Purpose of Archive

These tests were archived to:
1. Focus CI/CD on critical integration and validation tests
2. Reduce maintenance burden on outdated unit tests
3. Streamline test execution for MVP delivery
4. Maintain test history without deleting potentially useful code

## Restoring Archived Tests

If you need to restore any of these tests:

1. Copy the test file back to `test-scripts/` directory
2. Update any dependencies or imports as needed
3. Verify the test still works with current codebase
4. Update CI/CD configuration if needed

## Notes

- These tests may be outdated and require updates to work with the current codebase
- Some tests may have dependencies on deprecated code
- Consider writing new tests rather than restoring old ones if significant changes are needed
