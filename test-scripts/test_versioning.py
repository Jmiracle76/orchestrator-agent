#!/usr/bin/env python3
"""
Test suite for document versioning functionality.

Tests the versioning module's ability to track and update document versions
based on workflow completion milestones.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.versioning import (
    get_version_for_section,
    should_increment_version,
    update_document_version,
    get_current_version,
    _parse_version,
    _compare_versions,
)


def test_version_milestone_mapping():
    """Test that sections map to correct version milestones."""
    print("Test 1: Version milestone mapping...")
    
    tests = [
        ("problem_statement", "0.1"),
        ("goals_objectives", "0.2"),
        ("success_criteria", "0.3"),
        ("stakeholders_users", "0.4"),
        ("assumptions", "0.5"),
        ("constraints", "0.6"),
        ("review_gate:coherence_check", "0.7"),
        ("requirements", "0.8"),
        ("interfaces_integrations", "0.8"),
        ("data_considerations", "0.8"),
        ("review_gate:final_review", "0.9"),
        ("approval_record", "1.0"),
        ("unknown_section", "0.0"),  # Default for unknown sections
    ]
    
    all_passed = True
    for section_id, expected_version in tests:
        actual = get_version_for_section(section_id)
        if actual != expected_version:
            print(f"  ✗ {section_id}: expected {expected_version}, got {actual}")
            all_passed = False
    
    if all_passed:
        print("  ✅ All version milestone mappings correct")
    
    return all_passed


def test_version_parsing():
    """Test version string parsing."""
    print("Test 2: Version parsing...")
    
    tests = [
        ("0.0", (0, 0)),
        ("0.1", (0, 1)),
        ("1.0", (1, 0)),
        ("0.9", (0, 9)),
    ]
    
    all_passed = True
    for version_str, expected_tuple in tests:
        try:
            actual = _parse_version(version_str)
            if actual != expected_tuple:
                print(f"  ✗ {version_str}: expected {expected_tuple}, got {actual}")
                all_passed = False
        except ValueError as e:
            print(f"  ✗ {version_str}: parsing failed: {e}")
            all_passed = False
    
    # Test invalid formats
    invalid_tests = ["1", "1.0.0", "v1.0", "abc"]
    for invalid_version in invalid_tests:
        try:
            _parse_version(invalid_version)
            print(f"  ✗ {invalid_version}: should have raised ValueError")
            all_passed = False
        except ValueError:
            pass  # Expected
    
    if all_passed:
        print("  ✅ Version parsing works correctly")
    
    return all_passed


def test_version_comparison():
    """Test version comparison logic."""
    print("Test 3: Version comparison...")
    
    tests = [
        ("0.1", "0.0", 1),   # 0.1 > 0.0
        ("0.0", "0.1", -1),  # 0.0 < 0.1
        ("0.5", "0.5", 0),   # 0.5 == 0.5
        ("1.0", "0.9", 1),   # 1.0 > 0.9
        ("0.2", "0.8", -1),  # 0.2 < 0.8
    ]
    
    all_passed = True
    for v1, v2, expected_sign in tests:
        actual = _compare_versions(v1, v2)
        actual_sign = 1 if actual > 0 else (-1 if actual < 0 else 0)
        
        if actual_sign != expected_sign:
            print(f"  ✗ compare({v1}, {v2}): expected {expected_sign}, got {actual_sign}")
            all_passed = False
    
    if all_passed:
        print("  ✅ Version comparison works correctly")
    
    return all_passed


def test_should_increment_version():
    """Test version increment logic."""
    print("Test 4: Version increment logic...")
    
    tests = [
        ("problem_statement", "0.0", True),   # 0.1 > 0.0, should increment
        ("problem_statement", "0.1", False),  # 0.1 == 0.1, no increment
        ("problem_statement", "0.5", False),  # 0.1 < 0.5, no increment
        ("goals_objectives", "0.1", True),    # 0.2 > 0.1, should increment
        ("approval_record", "0.9", True),     # 1.0 > 0.9, should increment
        ("approval_record", "1.0", False),    # 1.0 == 1.0, no increment
        ("unknown_section", "0.0", False),    # No milestone for unknown
    ]
    
    all_passed = True
    for section_id, current_version, expected_result in tests:
        actual = should_increment_version(section_id, current_version)
        if actual != expected_result:
            print(f"  ✗ should_increment({section_id}, {current_version}): "
                  f"expected {expected_result}, got {actual}")
            all_passed = False
    
    if all_passed:
        print("  ✅ Version increment logic works correctly")
    
    return all_passed


def test_get_current_version():
    """Test extracting current version from document."""
    print("Test 5: Get current version from document...")
    
    # Test document with version 0.5
    test_doc = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- meta:version -->",
        "- **Version:** 0.5",
        "",
        "# Requirements Document",
    ]
    
    version = get_current_version(test_doc)
    if version == "0.5":
        print("  ✅ Correctly extracted version 0.5")
        result = True
    else:
        print(f"  ✗ Expected 0.5, got {version}")
        result = False
    
    # Test document without version (should return 0.0)
    test_doc_no_version = [
        "# Requirements Document",
        "Some content",
    ]
    
    version = get_current_version(test_doc_no_version)
    if version == "0.0":
        print("  ✅ Correctly returned 0.0 for missing version")
    else:
        print(f"  ✗ Expected 0.0 for missing version, got {version}")
        result = False
    
    return result


def test_update_document_version():
    """Test updating version throughout document."""
    print("Test 6: Update document version...")
    
    test_doc = [
        "<!-- meta:doc_type value=\"requirements\" -->",
        "<!-- meta:version -->",
        "- **Version:** 0.0",
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
    ]
    
    # Update to version 0.1
    updated_doc = update_document_version(test_doc, "0.1", "Problem statement completed")
    
    all_passed = True
    
    # Check meta version updated
    meta_found = False
    for i, line in enumerate(updated_doc):
        if "<!-- meta:version -->" in line and i + 1 < len(updated_doc):
            if "0.1" in updated_doc[i + 1]:
                print("  ✅ Meta version updated to 0.1")
                meta_found = True
                break
    if not meta_found:
        print("  ✗ Meta version not updated")
        all_passed = False
    
    # Check Document Control table updated
    table_found = False
    for line in updated_doc:
        if "| Current Version | 0.1 |" in line:
            print("  ✅ Document Control table updated")
            table_found = True
            break
    if not table_found:
        print("  ✗ Document Control table not updated")
        all_passed = False
    
    # Check Version History entry added
    history_found = False
    for line in updated_doc:
        if "| 0.1 |" in line and "Problem statement completed" in line:
            print("  ✅ Version History entry added")
            history_found = True
            break
    if not history_found:
        print("  ✗ Version History entry not added")
        all_passed = False
    
    return all_passed


def run_all_tests():
    """Run all test cases."""
    print("=" * 60)
    print("DOCUMENT VERSIONING TEST SUITE")
    print("=" * 60)
    print()
    
    tests = [
        test_version_milestone_mapping,
        test_version_parsing,
        test_version_comparison,
        test_should_increment_version,
        test_get_current_version,
        test_update_document_version,
    ]
    
    results = []
    for test_func in tests:
        try:
            passed = test_func()
            results.append((test_func.__name__, passed))
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append((test_func.__name__, False))
        print()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed_count}/{total_count} tests passed")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
