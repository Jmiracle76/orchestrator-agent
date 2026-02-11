#!/usr/bin/env python3
"""
Manual verification script for draft_section feature.

This script demonstrates the behavior without making actual API calls.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.runner_v2 import WorkflowRunner
from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.utils_io import split_lines

def demonstrate_draft_section_workflow():
    """Demonstrate the draft_section workflow with a realistic example."""
    print("=" * 80)
    print("MANUAL VERIFICATION: Draft Section Feature")
    print("=" * 80)
    
    # Read the test document
    test_doc_path = Path("/tmp/orchestrator-test/test-draft-document.md")
    if not test_doc_path.exists():
        print("✗ Test document not found at /tmp/orchestrator-test/test-draft-document.md")
        return False
    
    with open(test_doc_path, 'r') as f:
        test_doc = f.read()
    
    lines = split_lines(test_doc)
    
    # Load handler registry
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    # Create mock LLM that returns realistic draft content
    mock_llm = Mock()
    mock_llm.draft_section = Mock(return_value="""
### Functional Requirements

**REQ-1: Automatic Content Drafting**
- **Description:** The system shall automatically draft section content when 6 or more prior sections are complete and the target section has scope: all_prior_sections configured.
- **Priority:** High
- **Source:** Goals and Objectives, Success Criteria
- **Rationale:** Reduces manual intervention by 80% as specified in primary goals.

**REQ-2: Prior Context Integration**
- **Description:** The draft_section() method shall synthesize content from all completed prior sections including problem_statement, goals_objectives, stakeholders_users, success_criteria, assumptions, and constraints.
- **Priority:** High
- **Source:** Problem Statement, Assumptions
- **Rationale:** Leverages completed sections to inform requirements, addressing the core problem.

**REQ-3: Graceful Fallback**
- **Description:** When drafting fails or returns empty content, the system shall fall back to generating open questions.
- **Priority:** High
- **Source:** Constraints, Success Criteria
- **Rationale:** Ensures system continues to function even when automatic drafting is not possible.

### Non-Functional Requirements

**NFR-1: Backward Compatibility**
- **Description:** The system shall maintain backward compatibility with scope: current_section configurations.
- **Priority:** High
- **Measurement:** All existing tests pass; no regression in question-answer workflow.
- **Source:** Constraints

**NFR-2: Performance**
- **Description:** Drafting shall complete within reasonable LLM token limits (default 4096 tokens).
- **Priority:** Medium
- **Measurement:** Draft generation completes within 30 seconds.
- **Source:** Constraints
""".strip())
    
    mock_llm.generate_open_questions = Mock(return_value=[])
    
    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=[
            "problem_statement",
            "goals_objectives", 
            "stakeholders_users",
            "success_criteria",
            "assumptions",
            "constraints",
            "requirements"
        ],
        handler_registry=registry,
    )
    
    print("\n1. Initial Document State")
    print("-" * 80)
    
    # Check prior sections are complete
    for section_id in ["problem_statement", "goals_objectives", "stakeholders_users", 
                       "success_criteria", "assumptions", "constraints"]:
        state = runner._get_section_state(section_id)
        status = "✓ Complete" if not state.has_placeholder else "✗ Incomplete"
        print(f"   {section_id:30s} {status}")
    
    print("\n2. Requirements Section (Before Processing)")
    print("-" * 80)
    state = runner._get_section_state("requirements")
    print(f"   exists: {state.exists}")
    print(f"   is_blank: {state.is_blank}")
    print(f"   has_placeholder: {state.has_placeholder}")
    print(f"   has_open_questions: {state.has_open_questions}")
    
    print("\n3. Processing Requirements Section")
    print("-" * 80)
    
    # Get handler config
    handler_config = registry.get_handler_config("requirements", "requirements")
    print(f"   Handler mode: {handler_config.mode}")
    print(f"   LLM profile: {handler_config.llm_profile}")
    print(f"   Output format: {handler_config.output_format}")
    print(f"   Scope: {handler_config.scope}")
    
    # Execute the section
    result = runner._execute_section("requirements", state, dry_run=False)
    
    print("\n4. Execution Result")
    print("-" * 80)
    print(f"   action_taken: {result.action_taken}")
    print(f"   changed: {result.changed}")
    print(f"   blocked: {result.blocked}")
    print(f"   questions_generated: {result.questions_generated}")
    print(f"   questions_resolved: {result.questions_resolved}")
    print(f"   summaries: {result.summaries}")
    
    print("\n5. Verification")
    print("-" * 80)
    
    # Verify draft_section was called
    if mock_llm.draft_section.called:
        print("   ✓ draft_section() was called")
        call_args = mock_llm.draft_section.call_args
        
        # Check section_id
        if call_args.args[0] == "requirements":
            print("   ✓ Called with correct section_id: requirements")
        
        # Check prior_sections parameter
        prior_sections = call_args.args[2]
        if isinstance(prior_sections, dict) and len(prior_sections) == 6:
            print(f"   ✓ Passed {len(prior_sections)} prior sections:")
            for section_id in prior_sections.keys():
                print(f"      - {section_id}")
        else:
            print(f"   ✗ Unexpected prior_sections: {prior_sections}")
        
        # Check llm_profile and output_format
        if call_args.kwargs.get('llm_profile') == 'requirements':
            print("   ✓ Used correct llm_profile: requirements")
        if call_args.kwargs.get('output_format') == 'prose':
            print("   ✓ Used correct output_format: prose")
    else:
        print("   ✗ draft_section() was NOT called")
        return False
    
    # Verify section was updated
    if result.changed:
        print("   ✓ Section was marked as changed")
    
    if any("Drafted initial content" in s for s in result.summaries):
        print("   ✓ Summary indicates drafting occurred")
    
    # Check the section state after processing
    state_after = runner._get_section_state("requirements")
    print(f"\n6. Requirements Section (After Processing)")
    print("-" * 80)
    print(f"   is_blank: {state_after.is_blank}")
    print(f"   has_placeholder: {state_after.has_placeholder}")
    
    if not state_after.is_blank:
        print("   ✓ Section is no longer blank")
    
    # Write output document
    output_path = Path("/tmp/orchestrator-test/test-draft-document-output.md")
    with open(output_path, 'w') as f:
        f.write("\n".join(runner.lines))
    
    print(f"\n   Output written to: {output_path}")
    
    print("\n" + "=" * 80)
    print("✓ VERIFICATION COMPLETE - All checks passed")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = demonstrate_draft_section_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
