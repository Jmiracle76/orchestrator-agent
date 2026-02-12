#!/usr/bin/env python3
"""
End-to-end integration test for coherence_check gate with a realistic document.

This test creates a document similar to the template, processes sections,
and validates the coherence gate behavior.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.llm_client import LLMClient
from requirements_automation.parsing import (
    extract_workflow_order,
    find_sections,
    get_section_span,
    section_is_locked,
)
from requirements_automation.runner_core import WorkflowRunner


def create_realistic_test_document() -> list:
    """Create a realistic test document similar to the template."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:doc_format value="markdown" version="1.0" -->',
        '',
        '<!-- workflow:order',
        'problem_statement',
        'goals_objectives',
        'stakeholders_users',
        'success_criteria',
        'assumptions',
        'constraints',
        'review_gate:coherence_check',
        'requirements',
        '-->',
        '',
        '# Requirements Document',
        '',
        '## 1. Problem Statement',
        '<!-- section:problem_statement -->',
        'We need to build a document automation system that helps teams create and maintain requirements documents.',
        '',
        '### Questions & Issues',
        '<!-- table:problem_statement_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q1 | What is the primary use case? | 2024-01-01 | Requirements automation | Resolved |',
        '',
        '<!-- section_lock:problem_statement lock=false -->',
        '---',
        '',
        '## 2. Goals and Objectives',
        '<!-- section:goals_objectives -->',
        '### Primary Goals',
        '1. Automate requirements document creation',
        '2. Ensure consistency across documents',
        '',
        '### Questions & Issues',
        '<!-- table:goals_objectives_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q2 | What is target completion date? | 2024-01-01 | Q2 2024 | Resolved |',
        '',
        '<!-- section_lock:goals_objectives lock=false -->',
        '---',
        '',
        '## 3. Stakeholders and Users',
        '<!-- section:stakeholders_users -->',
        'Primary stakeholders include development teams and product managers.',
        '',
        '### Questions & Issues',
        '<!-- table:stakeholders_users_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q3 | Who are the key users? | 2024-01-01 | Dev teams | Resolved |',
        '',
        '<!-- section_lock:stakeholders_users lock=false -->',
        '---',
        '',
        '## 4. Success Criteria',
        '<!-- section:success_criteria -->',
        '1. Documents can be generated automatically',
        '2. Quality metrics meet standards',
        '',
        '### Questions & Issues',
        '<!-- table:success_criteria_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q4 | What are the quality metrics? | 2024-01-01 | Completeness | Resolved |',
        '',
        '<!-- section_lock:success_criteria lock=false -->',
        '---',
        '',
        '## 5. Assumptions',
        '<!-- section:assumptions -->',
        '- Users have basic markdown knowledge',
        '- System will run on modern infrastructure',
        '',
        '### Questions & Issues',
        '<!-- table:assumptions_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q5 | Are these assumptions validated? | 2024-01-01 | Yes | Resolved |',
        '',
        '<!-- section_lock:assumptions lock=false -->',
        '---',
        '',
        '## 6. Constraints',
        '<!-- section:constraints -->',
        '### Technical Constraints',
        '- Must work with existing CI/CD pipeline',
        '- Python 3.9+ required',
        '',
        '### Questions & Issues',
        '<!-- table:constraints_questions -->',
        '| Question ID | Question | Date | Answer | Status |',
        '|-------------|----------|------|--------|--------|',
        '| Q6 | Are constraints feasible? | 2024-01-01 | Yes | Resolved |',
        '',
        '<!-- section_lock:constraints lock=false -->',
        '---',
        '',
        '## 10. Identified Risks',
        '<!-- section:identified_risks -->',
        '',
        '<!-- table:risks -->',
        '| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |',
        '|---------|-------------|-------------|--------|---------------------|-------|',
        '| R1 | API changes | Low | Low | Version pinning | Team |',
        '| R2 | Performance issues | Low | Low | Load testing | Team |',
        '',
        '<!-- section_lock:identified_risks lock=false -->',
        '---',
        '',
        '## 13. Approval Record',
        '<!-- section:approval_record -->',
        '',
        '<!-- table:approval_record -->',
        '| Field | Value |',
        '|-------|-------|',
        '| Current Status | Draft |',
        '| Recommended By | Pending |',
        '| Recommendation Date | Pending |',
        '| Approved By | Pending |',
        '| Approval Date | Pending |',
        '',
        '---',
    ]


def test_e2e_coherence_gate_pass():
    """Test end-to-end workflow with passing coherence gate."""
    print("=" * 70)
    print("E2E Test: Coherence Gate Pass Scenario")
    print("=" * 70)
    
    lines = create_realistic_test_document()
    
    # Mock LLM client
    class MockLLM:
        def perform_review(self, gate_id, doc_type, section_contents, llm_profile, validation_rules):
            return {
                "issues": [],
                "patches": [],
                "summary": "All sections look good"
            }
    
    # Load handler registry
    config_path = Path(repo_root / "tools" / "config" / "handler_registry.yaml")
    registry = HandlerRegistry(config_path)
    
    # Extract workflow order
    workflow_order = extract_workflow_order(lines)
    
    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=MockLLM(),
        doc_type="requirements",
        workflow_order=workflow_order,
        handler_registry=registry,
    )
    
    print("\n1. Initial state check...")
    spans = find_sections(runner.lines)
    problem_span = get_section_span(spans, "problem_statement")
    
    if section_is_locked(runner.lines, problem_span):
        print("  ✗ Sections should start unlocked")
        return False
    print("  ✓ Sections start unlocked")
    
    print("\n2. Running workflow to coherence_check gate...")
    
    # Run workflow until we reach the coherence gate
    iterations = 0
    max_iterations = 20
    
    while iterations < max_iterations:
        result = runner.run_once(dry_run=False)
        iterations += 1
        
        print(f"  Iteration {iterations}: {result.target_id} -> {result.action_taken}")
        
        if result.target_id == "review_gate:coherence_check":
            print(f"\n3. Coherence gate result:")
            print(f"  - Passed: {not result.blocked}")
            print(f"  - Changed: {result.changed}")
            print(f"  - Blocked reasons: {result.blocked_reasons}")
            
            if result.blocked:
                print(f"  ✗ Gate should have passed")
                return False
            
            print("  ✓ Gate passed successfully")
            
            # Check if sections were locked
            print("\n4. Checking section locks...")
            spans = find_sections(runner.lines)
            prior_sections = ["problem_statement", "goals_objectives", "stakeholders_users", 
                            "success_criteria", "assumptions", "constraints"]
            
            all_locked = True
            for section_id in prior_sections:
                span = get_section_span(spans, section_id)
                if span and not section_is_locked(runner.lines, span):
                    print(f"  ✗ Section {section_id} should be locked")
                    all_locked = False
            
            if all_locked:
                print("  ✓ All prior sections locked")
            else:
                return False
            
            # Check if approval record was updated
            print("\n5. Checking approval record update...")
            found_update = False
            for line in runner.lines:
                if "| Recommended By |" in line and "requirements-automation" in line:
                    found_update = True
                    break
            
            if found_update:
                print("  ✓ Approval record updated")
            else:
                print("  ✗ Approval record should be updated")
                return False
            
            return True
        
        if result.action_taken == "complete":
            print("  ✗ Workflow completed without reaching coherence gate")
            return False
    
    print(f"  ✗ Max iterations ({max_iterations}) reached")
    return False


def test_e2e_coherence_gate_blocked():
    """Test end-to-end workflow with blocked coherence gate."""
    print("\n" + "=" * 70)
    print("E2E Test: Coherence Gate Blocked Scenario")
    print("=" * 70)
    
    lines = create_realistic_test_document()
    
    # Add an open question to block the gate - but keep section content complete
    # This simulates a scenario where sections are complete but have unresolved questions
    for i, line in enumerate(lines):
        if "| Q1 | What is the primary use case?" in line:
            # Add a new open question instead of changing existing one
            lines.insert(i + 1, '| Q1-new | Is this approach correct? | 2024-01-02 | | Open |')
            break
    
    # Mock LLM client
    class MockLLM:
        def perform_review(self, gate_id, doc_type, section_contents, llm_profile, validation_rules):
            return {
                "issues": [],
                "patches": [],
                "summary": "Review passed"
            }
    
    # Load handler registry
    config_path = Path(repo_root / "tools" / "config" / "handler_registry.yaml")
    registry = HandlerRegistry(config_path)
    
    # Extract workflow order
    workflow_order = extract_workflow_order(lines)
    
    # Since we're testing just the gate behavior, let's directly test it
    from requirements_automation.review_gate_handler import ReviewGateHandler
    from requirements_automation.models import HandlerConfig
    
    print("\n1. Testing coherence gate directly with open question...")
    
    handler = ReviewGateHandler(MockLLM(), lines, "requirements")
    
    config = HandlerConfig(
        section_id="review_gate:coherence_check",
        mode="review_gate",
        output_format="prose",
        subsections=False,
        dedupe=False,
        preserve_headers=[],
        sanitize_remove=[],
        llm_profile="requirements_review",
        auto_apply_patches="never",
        scope="all_prior_sections",
        validation_rules=[],
    )
    
    result = handler.execute_review("review_gate:coherence_check", config)
    
    print(f"\n2. Coherence gate result:")
    print(f"  - Passed: {result.passed}")
    print(f"  - Issues: {len(result.issues)}")
    
    if result.passed:
        print(f"  ✗ Gate should have been blocked")
        return False
    
    if not any("open question" in issue.description.lower() for issue in result.issues):
        print(f"  ✗ Should mention open questions in issues")
        print(f"  Issues: {[i.description for i in result.issues]}")
        return False
    
    print("  ✓ Gate correctly blocked due to open questions")
    
    # Check that sections were NOT locked
    print("\n3. Checking section locks...")
    spans = find_sections(handler.lines)
    problem_span = get_section_span(spans, "problem_statement")
    
    if section_is_locked(handler.lines, problem_span):
        print("  ✗ Sections should not be locked when gate fails")
        return False
    
    print("  ✓ Sections remain unlocked after gate failure")
    
    return True


def main():
    """Run all E2E tests."""
    tests = [
        test_e2e_coherence_gate_pass,
        test_e2e_coherence_gate_blocked,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"E2E Test Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
