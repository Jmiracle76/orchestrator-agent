#!/usr/bin/env python3
"""
Test script to validate that the open_questions subsection is preserved
during section body replacement operations.

This test validates that when replace_block_body_preserving_markers() is called
on a section containing an open_questions subsection, the subsection and its
table are preserved and not overwritten.
"""
import sys
from pathlib import Path
from unittest.mock import Mock

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.parsing import find_sections, find_subsections_within, get_section_span
from requirements_automation.runner_v2 import WorkflowRunner, _get_replacement_end_boundary
from requirements_automation.utils_io import split_lines


def test_get_replacement_end_boundary_with_open_questions():
    """Test that _get_replacement_end_boundary correctly identifies open_questions subsection."""
    print("\nTest 1: Helper function identifies open_questions subsection")
    print("=" * 70)

    # Create a test document with risks_open_issues section containing open_questions subsection
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
risks_open_issues
-->

# Test Document

<!-- section:risks_open_issues -->
## 10. Risks and Open Issues

<!-- subsection:identified_risks -->
### Identified Risks

Risk content here.

<!-- subsection:open_questions -->
### Open Questions

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | Test question? | 2024-01-01 | - | risks_open_issues | Open |

---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "risks_open_issues")
    subs = find_subsections_within(lines, span)

    print(f"  Section span: start={span.start_line}, end={span.end_line}")
    print(f"  Subsections found: {[s.subsection_id for s in subs]}")

    # Get the effective end boundary
    effective_end = _get_replacement_end_boundary(lines, span, subs)

    # Find the open_questions subsection manually
    open_q_sub = None
    for s in subs:
        if s.subsection_id == "open_questions":
            open_q_sub = s
            break

    if open_q_sub:
        print(
            f"  Open questions subsection: start={open_q_sub.start_line}, end={open_q_sub.end_line}"
        )
        print(f"  Effective end boundary: {effective_end}")

        # Verify that effective_end equals the start of open_questions subsection
        if effective_end == open_q_sub.start_line:
            print("  ✓ Helper function correctly returns boundary before open_questions subsection")
            return True
        else:
            print(f"  ✗ Expected boundary={open_q_sub.start_line}, got={effective_end}")
            return False
    else:
        print("  ✗ open_questions subsection not found")
        return False


def test_get_replacement_end_boundary_without_open_questions():
    """Test that _get_replacement_end_boundary returns full span when no open_questions subsection."""
    print("\nTest 2: Helper function returns full span without open_questions")
    print("=" * 70)

    # Create a test document without open_questions subsection
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
requirements
-->

# Test Document

<!-- section:requirements -->
## Requirements

Some content here.

---
"""

    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "requirements")
    subs = find_subsections_within(lines, span)

    print(f"  Section span: start={span.start_line}, end={span.end_line}")
    print(f"  Subsections found: {[s.subsection_id for s in subs]}")

    # Get the effective end boundary
    effective_end = _get_replacement_end_boundary(lines, span, subs)

    print(f"  Effective end boundary: {effective_end}")

    # Verify that effective_end equals the full section end
    if effective_end == span.end_line:
        print("  ✓ Helper function correctly returns full section end when no open_questions")
        return True
    else:
        print(f"  ✗ Expected boundary={span.end_line}, got={effective_end}")
        return False


def test_integration_preserves_open_questions():
    """Test that integration step preserves open_questions subsection."""
    print("\nTest 3: Integration step preserves open_questions subsection")
    print("=" * 70)

    # Create a test document with risks section containing open_questions
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
risks_open_issues
-->

# Test Document

<!-- section:risks_open_issues -->
## 10. Risks and Open Issues

<!-- subsection:identified_risks -->
### Identified Risks

<!-- PLACEHOLDER -->

<!-- subsection:open_questions -->
### Open Questions

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | What are the performance risks? | 2024-01-01 | High load scenarios need testing | risks_open_issues | Open |

<!-- section_lock:risks_open_issues lock=false -->
---
"""

    lines = split_lines(test_doc)

    # Create a mock LLM that returns content for integration
    mock_llm = Mock()
    mock_llm.integrate_answers = Mock(
        return_value="""### Identified Risks

1. **Performance Risk**: High load scenarios need testing
2. **Scalability Risk**: Database bottlenecks under load"""
    )

    # Load handler registry
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["risks_open_issues"],
        handler_registry=registry,
    )

    # Get section state
    state = runner._get_section_state("risks_open_issues")
    print(
        f"  Section state: is_blank={state.is_blank}, has_answered_questions={state.has_answered_questions}"
    )

    # Execute the section (should integrate answers)
    result = runner._execute_section("risks_open_issues", state, dry_run=False)

    print(f"  Execution result: action={result.action_taken}, changed={result.changed}")

    # Verify that open_questions subsection is still present
    updated_doc = "\n".join(runner.lines)

    if "<!-- subsection:open_questions -->" in updated_doc:
        print("  ✓ open_questions subsection marker preserved")
    else:
        print("  ✗ open_questions subsection marker was removed!")
        return False

    if "<!-- table:open_questions -->" in updated_doc:
        print("  ✓ open_questions table marker preserved")
    else:
        print("  ✗ open_questions table marker was removed!")
        return False

    if "Q-001" in updated_doc:
        print("  ✓ open_questions table content preserved")
    else:
        print("  ✗ open_questions table content was removed!")
        return False

    # Verify that identified_risks content was updated
    if "Performance Risk" in updated_doc or "Scalability Risk" in updated_doc:
        print("  ✓ identified_risks content was updated")
    else:
        print("  ✗ identified_risks content was not updated")
        return False

    print("  ✓ Integration preserved open_questions while updating identified_risks")
    return True


def test_drafting_preserves_open_questions():
    """Test that drafting step preserves open_questions subsection."""
    print("\nTest 4: Drafting step preserves open_questions subsection")
    print("=" * 70)

    # Create a test document with blank risks section containing open_questions
    test_doc = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
risks_open_issues
-->

# Test Document

<!-- section:problem_statement -->
## Problem Statement

This is the problem statement content that was completed earlier.

---

<!-- section:risks_open_issues -->
## 10. Risks and Open Issues

<!-- PLACEHOLDER -->

<!-- subsection:open_questions -->
### Open Questions

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | What are the risks? | 2024-01-01 | - | risks_open_issues | Open |

<!-- section_lock:risks_open_issues lock=false -->
---
"""

    lines = split_lines(test_doc)

    # Create a mock LLM that returns content for drafting
    mock_llm = Mock()
    mock_llm.draft_section = Mock(
        return_value="""### Identified Risks

Based on the problem statement, here are the key risks:

1. **Technical Risk**: Implementation complexity
2. **Resource Risk**: Limited development capacity"""
    )

    # Load handler registry
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    # Create workflow runner
    runner = WorkflowRunner(
        lines=lines,
        llm=mock_llm,
        doc_type="requirements",
        workflow_order=["problem_statement", "risks_open_issues"],
        handler_registry=registry,
    )

    # Mark problem_statement as complete
    runner.completed_targets = {"problem_statement"}

    # Get section state
    state = runner._get_section_state("risks_open_issues")
    print(
        f"  Section state: is_blank={state.is_blank}, has_answered_questions={state.has_answered_questions}"
    )

    # Execute the section (should draft content)
    result = runner._execute_section("risks_open_issues", state, dry_run=False)

    print(f"  Execution result: action={result.action_taken}, changed={result.changed}")

    # Verify that open_questions subsection is still present
    updated_doc = "\n".join(runner.lines)

    if "<!-- subsection:open_questions -->" in updated_doc:
        print("  ✓ open_questions subsection marker preserved")
    else:
        print("  ✗ open_questions subsection marker was removed!")
        return False

    if "<!-- table:open_questions -->" in updated_doc:
        print("  ✓ open_questions table marker preserved")
    else:
        print("  ✗ open_questions table marker was removed!")
        return False

    if "Q-001" in updated_doc:
        print("  ✓ open_questions table content preserved")
    else:
        print("  ✗ open_questions table content was removed!")
        return False

    # Verify that drafted content was added
    if "Technical Risk" in updated_doc or "Resource Risk" in updated_doc:
        print("  ✓ Drafted content was added")
    else:
        print("  ✗ Drafted content was not added")
        return False

    print("  ✓ Drafting preserved open_questions while adding drafted content")
    return True


def main():
    """Run all tests."""
    print("Open Questions Preservation Test Suite")
    print("=" * 70)

    results = []

    try:
        results.append(test_get_replacement_end_boundary_with_open_questions())
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        import traceback

        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_get_replacement_end_boundary_without_open_questions())
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        import traceback

        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_integration_preserves_open_questions())
    except Exception as e:
        print(f"✗ Test 3 failed with exception: {e}")
        import traceback

        traceback.print_exc()
        results.append(False)

    try:
        results.append(test_drafting_preserves_open_questions())
    except Exception as e:
        print(f"✗ Test 4 failed with exception: {e}")
        import traceback

        traceback.print_exc()
        results.append(False)

    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
