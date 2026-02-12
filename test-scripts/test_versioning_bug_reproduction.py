#!/usr/bin/env python3
"""
Test to reproduce the version history bug where entries are inserted into wrong tables.

This test creates a document with multiple tables containing placeholders,
and verifies that version history entries are only inserted into the version history table.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.versioning import update_document_version


def create_document_with_multiple_tables():
    """Create a test document with version history and other tables with placeholders."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:version -->',
        '- **Version:** 0.0',
        '',
        '<!-- table:document_control -->',
        '| Field | Value |',
        '|-------|-------|',
        '| Current Version | 0.0 |',
        '',
        '<!-- subsection:version_history -->',
        '### Version History',
        '| Version | Date | Author | Changes |',
        '|---------|------|--------|---------|',
        '| <!-- PLACEHOLDER --> | - | - | - |',
        '',
        '<!-- section:stakeholders_users -->',
        '## Stakeholders and Users',
        '',
        '<!-- subsection:primary_stakeholders -->',
        '### Primary Stakeholders',
        '| Stakeholder | Role | Interest/Need | Contact |',
        '|-------------|------|---------------|---------|',
        '| <!-- PLACEHOLDER --> | - | - | - |',
        '',
        '<!-- subsection:end_users -->',
        '### End Users',
        '| User Type | Characteristics | Needs | Use Cases |',
        '|-----------|----------------|-------|-----------|',
        '| <!-- PLACEHOLDER --> | - | - | - |',
        '',
        '<!-- section:constraints -->',
        '## Constraints',
        '',
        '<!-- subsection:technical_constraints -->',
        '### Technical Constraints',
        '| <!-- PLACEHOLDER --> | - | - | - |',
        '',
        '<!-- subsection:operational_constraints -->',
        '### Operational Constraints',
        '| <!-- PLACEHOLDER --> | - | - | - |',
        '',
    ]


def test_bug_reproduction():
    """Test that reproduces the bug where version entries corrupt other tables."""
    print("=" * 70)
    print("VERSION HISTORY BUG REPRODUCTION TEST")
    print("=" * 70)
    print()
    
    lines = create_document_with_multiple_tables()
    
    # First update - this should work fine (placeholder in version history)
    print("First update (version 0.1)...")
    lines = update_document_version(lines, "0.1", "Problem Statement completed")
    
    # Check version history has the entry
    content = "\n".join(lines)
    if "| 0.1 |" in content:
        print("  ✅ Version 0.1 entry created")
    else:
        print("  ❌ Version 0.1 entry NOT found")
        return False
    
    # Second update - this is where the bug happens
    print("Second update (version 0.2)...")
    lines = update_document_version(lines, "0.2", "Goals completed")
    
    content = "\n".join(lines)
    
    # Check that version 0.2 is in version history
    version_history_section = []
    in_version_history = False
    for line in lines:
        if "<!-- subsection:version_history -->" in line:
            in_version_history = True
        elif in_version_history and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_version_history:
            version_history_section.append(line)
    
    version_history_text = "\n".join(version_history_section)
    
    if "| 0.2 |" in version_history_text:
        print("  ✅ Version 0.2 entry is in version history section")
    else:
        print("  ❌ Version 0.2 entry NOT in version history section")
        print("  Version history section:")
        print(version_history_text)
        return False
    
    # Check that stakeholders table is NOT corrupted
    stakeholders_section = []
    in_stakeholders = False
    for line in lines:
        if "<!-- subsection:primary_stakeholders -->" in line:
            in_stakeholders = True
        elif in_stakeholders and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_stakeholders:
            stakeholders_section.append(line)
    
    stakeholders_text = "\n".join(stakeholders_section)
    
    if "| 0.2 |" in stakeholders_text or "Goals completed" in stakeholders_text:
        print("  ❌ BUG CONFIRMED: Stakeholders table is CORRUPTED with version entry")
        print("  Stakeholders section:")
        print(stakeholders_text)
        return False
    else:
        print("  ✅ Stakeholders table is NOT corrupted")
    
    # Third update
    print("Third update (version 0.3)...")
    lines = update_document_version(lines, "0.3", "Success Criteria completed")
    
    # Check that end_users table is NOT corrupted
    end_users_section = []
    in_end_users = False
    for line in lines:
        if "<!-- subsection:end_users -->" in line:
            in_end_users = True
        elif in_end_users and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_end_users:
            end_users_section.append(line)
    
    end_users_text = "\n".join(end_users_section)
    
    if "| 0.3 |" in end_users_text or "Success Criteria completed" in end_users_text:
        print("  ❌ BUG CONFIRMED: End Users table is CORRUPTED with version entry")
        print("  End users section:")
        print(end_users_text)
        return False
    else:
        print("  ✅ End Users table is NOT corrupted")
    
    print()
    print("✅ All checks passed - Bug is FIXED or not reproducible")
    return True


def test_append_behavior():
    """Test that new entries are appended when placeholder is already consumed."""
    print("=" * 70)
    print("APPEND BEHAVIOR TEST")
    print("=" * 70)
    print()
    
    # Create document with one existing entry (no placeholder)
    lines = [
        '<!-- meta:version -->',
        '- **Version:** 0.1',
        '',
        '<!-- subsection:version_history -->',
        '### Version History',
        '| Version | Date | Author | Changes |',
        '|---------|------|--------|---------|',
        '| 0.1 | 2026-02-12 | requirements-automation | Initial version |',
        '',
        '<!-- section:stakeholders_users -->',
        '## Stakeholders',
        '| <!-- PLACEHOLDER --> | - | - | - |',
    ]
    
    # Add another version
    print("Adding version 0.2...")
    lines = update_document_version(lines, "0.2", "Second version")
    
    # Count version history entries
    version_history_section = []
    in_version_history = False
    for line in lines:
        if "<!-- subsection:version_history -->" in line:
            in_version_history = True
        elif in_version_history and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_version_history:
            version_history_section.append(line)
    
    version_history_text = "\n".join(version_history_section)
    
    # Check both entries exist
    if "| 0.1 |" in version_history_text and "| 0.2 |" in version_history_text:
        print("  ✅ Both version entries found in version history")
        print("Version history:")
        print(version_history_text)
        return True
    else:
        print("  ❌ Version entries missing")
        print("Version history:")
        print(version_history_text)
        return False


def test_duplicate_prevention():
    """Test that duplicate version entries are prevented."""
    print("=" * 70)
    print("DUPLICATE PREVENTION TEST")
    print("=" * 70)
    print()

    lines = [
        '<!-- meta:version -->',
        '- **Version:** 0.1',
        '',
        '<!-- subsection:version_history -->',
        '### Version History',
        '| Version | Date | Author | Changes |',
        '|---------|------|--------|---------|',
        '| 0.1 | 2026-02-12 | requirements-automation | Initial version |',
        '',
    ]

    # Try to add same version again
    print("Attempting to add duplicate version 0.1...")
    lines = update_document_version(lines, "0.1", "Duplicate attempt")

    # Count occurrences of version 0.1
    content = "\n".join(lines)
    count = content.count("| 0.1 |")

    if count == 1:
        print(f"  ✅ Version 0.1 appears only once (duplicate prevented)")
    else:
        print(f"  ❌ Version 0.1 appears {count} times (duplicates not prevented)")
        return False

    # Test with extra spacing
    print("Testing duplicate prevention with extra spacing...")
    lines2 = [
        '<!-- meta:version -->',
        '- **Version:** 0.1',
        '',
        '<!-- subsection:version_history -->',
        '### Version History',
        '| Version | Date | Author | Changes |',
        '|---------|------|--------|---------|',
        '|  0.1  | 2026-02-12 | requirements-automation | Initial version |',  # Extra spaces
        '',
    ]

    lines2 = update_document_version(lines2, "0.1", "Duplicate with spacing")
    content2 = "\n".join(lines2)

    # Count lines that have 0.1 as version (allowing for different spacing)
    version_count = 0
    for line in lines2:
        if line.strip().startswith("|"):
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) > 1 and cells[1] == "0.1":
                version_count += 1

    if version_count == 1:
        print(f"  ✅ Version 0.1 with extra spacing appears only once (duplicate prevented)")
        return True
    else:
        print(f"  ❌ Version 0.1 with spacing appears {version_count} times (duplicates not prevented)")
        return False


if __name__ == "__main__":
    print()
    print("#" * 70)
    print("# VERSION HISTORY BUG REPRODUCTION TEST SUITE")
    print("#" * 70)
    print()
    
    tests = [
        ("Bug Reproduction", test_bug_reproduction),
        ("Append Behavior", test_append_behavior),
        ("Duplicate Prevention", test_duplicate_prevention),
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
    
    sys.exit(0 if passed_count == total_count else 1)
