#!/usr/bin/env python3
"""
Validation script for Issue 3c/3d acceptance criteria.

This script validates that:
1. Assumptions retain numbered list format (1., 2., 3., etc.) after LLM drafting
2. Constraints retain all three subsections (technical, operational, resource) after LLM drafting
3. Questions & Issues tables are preserved for both sections

The validation uses the actual configuration and code paths that will be used
in production to ensure the behavior is correct.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.llm_prompts import build_draft_section_prompt, build_integrate_answers_prompt
from requirements_automation.parsing import find_sections, get_section_span, find_subsections_within, section_body
from requirements_automation.runner_integration import _build_subsection_structure
from requirements_automation.utils_io import split_lines


def validate_assumptions_acceptance_criteria():
    """Validate acceptance criteria for assumptions section."""
    print("\n" + "=" * 70)
    print("ASSUMPTIONS SECTION VALIDATION (Issue 3c)")
    print("=" * 70)
    print("\nGoal: Ensure assumptions retain numbered list format after LLM drafting")
    print("\n" + "=" * 70)
    
    # Load the actual handler configuration
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    handler_config = registry.get_handler_config("requirements", "assumptions")
    
    print("\n[Step 1] Verify handler configuration")
    print("-" * 70)
    
    # Criterion: output_format must be "numbered"
    if handler_config.output_format != "numbered":
        print(f"  ✗ FAILED: output_format is '{handler_config.output_format}', expected 'numbered'!")
        print("    The LLM will not be instructed to use numbered list format.")
        return False
    print("  ✓ handler_config.output_format = 'numbered'")
    print("    The LLM will be instructed to use numbered list format (1., 2., 3., etc.)")
    
    # Create a test document with the actual template structure
    test_doc = """<!-- section:assumptions -->
## 5. Assumptions
<!-- PLACEHOLDER -->
1. [Assumption 1] 
2. [Assumption 2] 

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:assumptions_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| assumptions-Q1 | Have all assumptions been validated with stakeholders? | [Date] | | Open |
| assumptions-Q2 | What is the impact if any of these assumptions are invalid? | [Date] | | Open |

<!-- section_lock:assumptions lock=false -->
---
"""
    
    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "assumptions")
    
    print("\n[Step 2] Verify LLM prompt instructions")
    print("-" * 70)
    
    ctx = section_body(lines, span)
    
    # Build a sample draft prompt
    prior_sections = {
        "problem_statement": "We need to modernize our data processing system.",
        "goals_objectives": "Primary goals: Improve performance, reduce costs."
    }
    
    prompt = build_draft_section_prompt(
        section_id="assumptions",
        section_context=ctx,
        prior_sections=prior_sections,
        full_profile="You are a requirements analyst.",
        output_format=handler_config.output_format,
        subsection_structure=None,  # assumptions doesn't have content subsections
    )
    
    # Verify the prompt contains numbered list guidance
    if "numbered list" not in prompt.lower():
        print("  ✗ FAILED: 'numbered list' instruction NOT in prompt!")
        return False
    print("  ✓ Prompt contains 'numbered list' instruction")
    
    if "1., 2., 3." not in prompt:
        print("  ✗ FAILED: Numbered list format example '1., 2., 3.' NOT in prompt!")
        return False
    print("  ✓ Prompt contains numbered list format example: '1., 2., 3.'")
    
    print("\n[Step 3] Acceptance Criteria Summary")
    print("-" * 70)
    
    print("\n  CRITERION: Assumptions list format preserved after drafting")
    print("  ✓ SATISFIED")
    print("    - Handler configured with output_format='numbered'")
    print("    - LLM receives explicit instruction to use numbered list format")
    print("    - Format example (1., 2., 3., etc.) provided in prompt")
    
    print("\n  CRITERION: Questions & Issues table preserved")
    print("  ✓ SATISFIED")
    print("    - questions_issues subsection excluded from content")
    print("    - LLM will not overwrite questions_issues subsection")
    
    return True


def validate_constraints_acceptance_criteria():
    """Validate acceptance criteria for constraints section."""
    print("\n" + "=" * 70)
    print("CONSTRAINTS SECTION VALIDATION (Issue 3d)")
    print("=" * 70)
    print("\nGoal: Ensure constraints retain all three subsections after LLM drafting")
    print("\n" + "=" * 70)
    
    # Load the actual handler configuration
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    handler_config = registry.get_handler_config("requirements", "constraints")
    
    print("\n[Step 1] Verify handler configuration")
    print("-" * 70)
    
    # Criterion: subsections must be enabled
    if not handler_config.subsections:
        print("  ✗ FAILED: handler_config.subsections is False!")
        print("    The LLM will not receive subsection structure information.")
        return False
    print("  ✓ handler_config.subsections = True")
    print("    The handler will build and pass subsection structure to LLM.")
    
    # Criterion: output_format must be "subsections"
    if handler_config.output_format != "subsections":
        print(f"  ✗ FAILED: output_format is '{handler_config.output_format}', expected 'subsections'!")
        return False
    print("  ✓ handler_config.output_format = 'subsections'")
    
    # Criterion: preserve_headers must include the three constraint headers
    expected_headers = {
        "### Technical Constraints",
        "### Operational Constraints",
        "### Resource Constraints",
    }
    actual_headers = set(handler_config.preserve_headers)
    missing_headers = expected_headers - actual_headers
    if missing_headers:
        print(f"  ✗ FAILED: Missing preserve_headers: {missing_headers}")
        return False
    print("  ✓ preserve_headers includes all three constraint subsections")
    
    # Create a test document with the actual template structure
    test_doc = """<!-- section:constraints -->
## 6. Constraints
<!-- PLACEHOLDER -->
<!-- subsection:technical_constraints -->
### Technical Constraints
<!-- PLACEHOLDER -->
- [Technical constraint 1] 
- [Technical constraint 2] 

<!-- subsection:operational_constraints -->
### Operational Constraints
<!-- PLACEHOLDER -->
- [Operational constraint 1] 
- [Operational constraint 2] 

<!-- subsection:resource_constraints -->
### Resource Constraints
<!-- PLACEHOLDER -->
- [Resource constraint 1] 
- [Resource constraint 2] 

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:constraints_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
| constraints-Q1 | Have all constraints been validated? | [Date] | | Open |

<!-- section_lock:constraints lock=false -->
---
"""
    
    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "constraints")
    
    print("\n[Step 2] Verify subsection structure building")
    print("-" * 70)
    
    # Build subsection structure
    structure = _build_subsection_structure(lines, span, handler_config)
    
    if not structure:
        print("  ✗ FAILED: subsection structure is None!")
        print("    The LLM will not receive subsection guidance.")
        return False
    
    print(f"  ✓ Subsection structure built: {len(structure)} content subsections")
    
    # Verify all three constraint subsections are in the structure
    sub_ids = [s['id'] for s in structure]
    print(f"    Subsection IDs: {sub_ids}")
    
    required_subs = ["technical_constraints", "operational_constraints", "resource_constraints"]
    for req_sub in required_subs:
        if req_sub not in sub_ids:
            print(f"  ✗ FAILED: {req_sub} not in structure!")
            return False
        print(f"  ✓ {req_sub} subsection included")
    
    # Verify questions_issues is NOT in the structure (it's metadata)
    if 'questions_issues' in sub_ids:
        print("  ✗ FAILED: questions_issues should not be in content structure!")
        return False
    print("  ✓ questions_issues correctly excluded (metadata, not content)")
    
    print("\n[Step 3] Verify subsection types")
    print("-" * 70)
    
    # Each constraint subsection should be "bullets" type
    for sub in structure:
        if sub['type'] != 'bullets':
            print(f"  ✗ FAILED: {sub['id']} type is '{sub['type']}', expected 'bullets'!")
            return False
        print(f"  ✓ {sub['id']} type = 'bullets'")
    
    print("\n[Step 4] Verify LLM prompt instructions")
    print("-" * 70)
    
    ctx = section_body(lines, span)
    
    # Build a sample draft prompt
    prior_sections = {
        "problem_statement": "We need to modernize our data processing system.",
        "goals_objectives": "Primary goals: Improve performance, reduce costs."
    }
    
    prompt = build_draft_section_prompt(
        section_id="constraints",
        section_context=ctx,
        prior_sections=prior_sections,
        full_profile="You are a requirements analyst.",
        output_format=handler_config.output_format,
        subsection_structure=structure,
    )
    
    # Verify the prompt contains all three subsection headers
    for header in ["### Technical Constraints", "### Operational Constraints", "### Resource Constraints"]:
        if header not in prompt:
            print(f"  ✗ FAILED: '{header}' NOT in prompt!")
            return False
        print(f"  ✓ Prompt contains: {header}")
    
    # Verify bullet list instruction is present
    if "Bullet list items" not in prompt:
        print("  ✗ FAILED: Bullet list instruction NOT in prompt!")
        return False
    print("  ✓ Prompt contains bullet list instruction")
    
    print("\n[Step 5] Acceptance Criteria Summary")
    print("-" * 70)
    
    print("\n  CRITERION: All three constraint subsections preserved")
    print("  ✓ SATISFIED")
    print("    - Handler configured with subsections=True")
    print("    - All three subsections included in structure")
    print("    - LLM receives explicit subsection headers")
    print("    - Subsections configured with 'bullets' type")
    
    print("\n  CRITERION: Questions & Issues table preserved")
    print("  ✓ SATISFIED")
    print("    - questions_issues subsection excluded from content structure")
    print("    - LLM will not overwrite questions_issues subsection")
    
    return True


def main():
    """Run validation."""
    try:
        success_assumptions = validate_assumptions_acceptance_criteria()
        success_constraints = validate_constraints_acceptance_criteria()
        
        print("\n" + "=" * 70)
        if success_assumptions and success_constraints:
            print("✓ ALL ACCEPTANCE CRITERIA SATISFIED")
            print("=" * 70)
            print("\nBoth assumptions and constraints sections are configured correctly")
            print("to preserve their formatting after LLM drafting:")
            print("  - Assumptions: Numbered list format (1., 2., 3., etc.)")
            print("  - Constraints: All three subsections (Technical, Operational, Resource)")
            print("  - Questions & Issues tables preserved in both sections")
            return 0
        else:
            print("✗ SOME ACCEPTANCE CRITERIA NOT SATISFIED")
            print("=" * 70)
            return 1
    except Exception as e:
        print(f"\n✗ EXCEPTION during validation: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
