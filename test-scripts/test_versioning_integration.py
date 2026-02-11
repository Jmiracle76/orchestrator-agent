#!/usr/bin/env python3
"""
End-to-end integration test for document versioning.

This test simulates a workflow run with version updates at each milestone.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.versioning import (
    VERSION_MILESTONES,
    get_current_version,
    get_version_for_section,
    should_increment_version,
    update_document_version,
)


def create_test_document():
    """Create a minimal test document based on template."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:doc_format value="markdown" version="1.0" -->',
        "",
        "<!-- workflow:order",
        "problem_statement",
        "goals_objectives",
        "success_criteria",
        "-->",
        "",
        "# Requirements Document",
        "",
        "<!-- meta:version -->",
        "- **Version:** 0.0 ",
        "",
        "<!-- table:document_control -->",
        "| Field | Value |",
        "|-------|-------|",
        "| Current Version | 0.0 |",
        "",
        "<!-- subsection:version_history -->",
        "### Version History",
        "| Version | Date | Author | Changes |",
        "|---------|------|--------|---------|",
        "| <!-- PLACEHOLDER --> | - | - | - |",
        "",
        "<!-- section:problem_statement -->",
        "## Problem Statement",
        "<!-- PLACEHOLDER -->",
        "",
        "<!-- section:goals_objectives -->",
        "## Goals",
        "<!-- PLACEHOLDER -->",
        "",
        "<!-- section:success_criteria -->",
        "## Success Criteria",
        "<!-- PLACEHOLDER -->",
    ]


def simulate_section_completion(lines, section_id):
    """Simulate completing a section by removing placeholder."""
    result = []
    in_section = False
    for line in lines:
        if f"<!-- section:{section_id} -->" in line:
            in_section = True
            result.append(line)
        elif in_section and "<!-- PLACEHOLDER -->" in line:
            # Replace placeholder with content
            result.append(f"Content for {section_id} section.")
            in_section = False
        else:
            result.append(line)
    return result


def test_version_progression():
    """Test version progression through workflow."""
    print("=" * 70)
    print("END-TO-END VERSION PROGRESSION TEST")
    print("=" * 70)
    print()

    lines = create_test_document()
    workflow = ["problem_statement", "goals_objectives", "success_criteria"]

    print(f"Starting version: {get_current_version(lines)}")
    print()

    for section_id in workflow:
        print(f"Processing section: {section_id}")
        print(f"  Current version: {get_current_version(lines)}")

        # Get target version for this section
        target_version = get_version_for_section(section_id)
        print(f"  Target version: {target_version}")

        # Check if we should increment
        current_version = get_current_version(lines)
        should_increment = should_increment_version(section_id, current_version)
        print(f"  Should increment: {should_increment}")

        if should_increment:
            # Simulate section completion
            lines = simulate_section_completion(lines, section_id)

            # Update version
            change_description = f"{section_id.replace('_', ' ').title()} completed"
            lines = update_document_version(lines, target_version, change_description)

            new_version = get_current_version(lines)
            print(f"  Updated to version: {new_version}")

            # Verify version changed
            if new_version != target_version:
                print(f"  ❌ ERROR: Expected {target_version}, got {new_version}")
                return False
            else:
                print(f"  ✅ Version updated successfully")
        else:
            print(f"  ℹ️  No version increment needed")

        print()

    # Final verification
    final_version = get_current_version(lines)
    expected_final = "0.3"  # success_criteria milestone

    print("=" * 70)
    print("FINAL VERIFICATION")
    print("=" * 70)
    print(f"Final version: {final_version}")
    print(f"Expected: {expected_final}")

    if final_version == expected_final:
        print("✅ Version progression test PASSED")
        return True
    else:
        print("❌ Version progression test FAILED")
        return False


def test_version_milestones_coverage():
    """Test that all expected milestones are defined."""
    print("=" * 70)
    print("VERSION MILESTONES COVERAGE TEST")
    print("=" * 70)
    print()

    expected_sections = [
        "problem_statement",
        "goals_objectives",
        "success_criteria",
        "stakeholders_users",
        "assumptions",
        "constraints",
        "review_gate:coherence_check",
        "requirements",
        "interfaces_integrations",
        "data_considerations",
        "review_gate:final_review",
        "approval_record",
    ]

    all_covered = True
    for section in expected_sections:
        version = get_version_for_section(section)
        if version == "0.0":
            print(f"❌ {section}: No milestone defined")
            all_covered = False
        else:
            print(f"✅ {section}: {version}")

    print()
    if all_covered:
        print("✅ All sections have version milestones")
        return True
    else:
        print("❌ Some sections missing version milestones")
        return False


def test_version_history_accumulation():
    """Test that version history accumulates entries."""
    print("=" * 70)
    print("VERSION HISTORY ACCUMULATION TEST")
    print("=" * 70)
    print()

    lines = create_test_document()

    # Apply multiple version updates
    updates = [("0.1", "First update"), ("0.2", "Second update"), ("0.3", "Third update")]

    for version, description in updates:
        print(f"Applying version {version}: {description}")
        lines = update_document_version(lines, version, description)

    # Check that all entries are present
    content = "".join(lines)
    all_found = True

    for version, description in updates:
        if f"| {version} |" not in content:
            print(f"  ❌ Version {version} not found in history")
            all_found = False
        elif description not in content:
            print(f"  ❌ Description '{description}' not found in history")
            all_found = False
        else:
            print(f"  ✅ Version {version} entry found")

    print()
    if all_found:
        print("✅ Version history accumulation test PASSED")
        return True
    else:
        print("❌ Version history accumulation test FAILED")
        return False


def run_all_tests():
    """Run all integration tests."""
    print()
    print("#" * 70)
    print("# DOCUMENT VERSIONING END-TO-END INTEGRATION TEST SUITE")
    print("#" * 70)
    print()

    tests = [
        ("Version Milestones Coverage", test_version_milestones_coverage),
        ("Version Progression", test_version_progression),
        ("Version History Accumulation", test_version_history_accumulation),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))
        print()

    # Summary
    print("#" * 70)
    print("# TEST SUMMARY")
    print("#" * 70)
    print()

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    print()
    print(f"Total: {passed_count}/{total_count} tests passed")
    print()

    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
