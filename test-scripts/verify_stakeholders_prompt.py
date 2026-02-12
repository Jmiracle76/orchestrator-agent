#!/usr/bin/env python3
"""
Manual verification of LLM prompt for stakeholders_users section.

This script demonstrates what the LLM prompt will look like when
drafting or integrating answers for the stakeholders_users section.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.llm_prompts import build_draft_section_prompt
from requirements_automation.parsing import find_sections, get_section_span, find_subsections_within
from requirements_automation.runner_integration import _build_subsection_structure
from requirements_automation.utils_io import split_lines


def main():
    print("\n" + "=" * 70)
    print("STAKEHOLDERS_USERS LLM PROMPT VERIFICATION")
    print("=" * 70)
    
    # Load handler config
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    handler_config = registry.get_handler_config("requirements", "stakeholders_users")
    
    print(f"\nHandler Config:")
    print(f"  subsections: {handler_config.subsections}")
    print(f"  output_format: {handler_config.output_format}")
    print(f"  llm_profile: {handler_config.llm_profile}")
    
    # Create a test document with stakeholders_users section
    test_doc = """<!-- section:stakeholders_users -->
## 4. Stakeholders and Users

<!-- PLACEHOLDER -->

<!-- subsection:primary_stakeholders -->
### Primary Stakeholders

<!-- table:primary_stakeholders -->
| Stakeholder | Role | Interest/Need | Contact |
|-------------|------|---------------|---------|
| <!-- PLACEHOLDER --> | - | - | - |

<!-- subsection:end_users -->
### End Users

<!-- table:end_users -->
| User Type | Characteristics | Needs | Use Cases |
|-----------|----------------|-------|-----------|
| <!-- PLACEHOLDER --> | - | - | - |

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- section_lock:stakeholders_users lock=false -->
"""
    
    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "stakeholders_users")
    
    # Build subsection structure
    structure = _build_subsection_structure(lines, span, handler_config)
    
    print(f"\nSubsection Structure:")
    for sub in structure:
        print(f"  - {sub['id']}: {sub['type']}")
    
    # Get section body
    from requirements_automation.parsing import section_body
    ctx = section_body(lines, span)
    
    # Build a sample prompt
    prior_sections = {
        "problem_statement": "We need to modernize our data processing system.",
        "goals_objectives": "Primary goals: Improve performance, reduce costs."
    }
    
    prompt = build_draft_section_prompt(
        section_id="stakeholders_users",
        section_context=ctx,
        prior_sections=prior_sections,
        full_profile="You are a requirements analyst.",
        output_format=handler_config.output_format,
        subsection_structure=structure,
    )
    
    print("\n" + "=" * 70)
    print("GENERATED LLM PROMPT (relevant section):")
    print("=" * 70)
    
    # Extract and display the subsection guidance part of the prompt
    lines_prompt = prompt.split('\n')
    in_subsection_section = False
    subsection_lines = []
    
    for line in lines_prompt:
        if '**Subsection Structure:**' in line:
            in_subsection_section = True
        if in_subsection_section:
            subsection_lines.append(line)
            if line.strip() == '' and len(subsection_lines) > 10:
                break
    
    print('\n'.join(subsection_lines))
    
    print("\n" + "=" * 70)
    print("VERIFICATION:")
    print("=" * 70)
    
    # Verify the prompt contains table guidance
    if "### Primary Stakeholders" in prompt:
        print("  ✓ Primary Stakeholders subsection header in prompt")
    else:
        print("  ✗ Primary Stakeholders subsection header NOT in prompt")
        return 1
    
    if "Markdown table rows only" in prompt:
        print("  ✓ Table format instruction present in prompt")
    else:
        print("  ✗ Table format instruction NOT present in prompt")
        return 1
    
    if "no header, just data rows with pipe delimiters" in prompt:
        print("  ✓ Specific table row instruction present")
    else:
        print("  ✗ Specific table row instruction NOT present")
        return 1
    
    if "### End Users" in prompt:
        print("  ✓ End Users subsection header in prompt")
    else:
        print("  ✗ End Users subsection header NOT in prompt")
        return 1
    
    print("\n✓ All verifications passed!")
    print("  The LLM will receive clear instructions to output table rows")
    print("  for both primary_stakeholders and end_users subsections.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
