#!/usr/bin/env python3
"""
End-to-end validation test for the version history bug fix.

This test simulates the exact scenario described in the problem statement:
multiple version updates with various tables containing placeholders.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.versioning import update_document_version, get_current_version


def create_realistic_document():
    """Create a realistic requirements document with multiple sections and tables."""
    return [
        '<!-- meta:doc_type value="requirements" -->',
        '<!-- meta:doc_format value="markdown" version="1.0" -->',
        '',
        '# Requirements Document',
        '',
        '<!-- meta:version -->',
        '- **Version:** 0.0',
        '',
        '<!-- table:document_control -->',
        '| Field | Value |',
        '|-------|-------|',
        '| Current Version | 0.0 |',
        '| Status | Draft |',
        '',
        '<!-- subsection:version_history -->',
        '### Version History',
        '| Version | Date | Author | Changes |',
        '|---------|------|--------|---------|',
        '| <!-- PLACEHOLDER --> | - | - | - |',
        '',
        '<!-- section:problem_statement -->',
        '## Problem Statement',
        'This is the problem statement.',
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
        '<!-- section:assumptions -->',
        '## Assumptions',
        '| Assumption | Rationale | Impact if Wrong |',
        '|------------|-----------|-----------------|',
        '| <!-- PLACEHOLDER --> | - | - |',
        '',
        '<!-- section:constraints -->',
        '## Constraints',
        '',
        '<!-- subsection:technical_constraints -->',
        '### Technical Constraints',
        '| Constraint | Description | Mitigation |',
        '|------------|-------------|------------|',
        '| <!-- PLACEHOLDER --> | - | - |',
        '',
        '<!-- subsection:operational_constraints -->',
        '### Operational Constraints',
        '| Constraint | Description | Impact |',
        '|------------|-------------|--------|',
        '| <!-- PLACEHOLDER --> | - | - |',
        '',
    ]


def validate_section_not_corrupted(lines, section_marker, section_name, versions_to_check):
    """Validate that a section's table hasn't been corrupted with version entries."""
    in_section = False
    section_content = []
    
    for line in lines:
        if section_marker in line:
            in_section = True
        elif in_section and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_section:
            section_content.append(line)
    
    section_text = "\n".join(section_content)
    
    for version in versions_to_check:
        if f"| {version} |" in section_text:
            print(f"  ❌ ERROR: {section_name} contains version entry {version}")
            print(f"  Section content:")
            print(section_text)
            return False
    
    return True


def validate_version_in_history(lines, version, changes):
    """Validate that a version entry exists in the version history table."""
    in_version_history = False
    version_history_content = []
    
    for line in lines:
        if "<!-- subsection:version_history -->" in line:
            in_version_history = True
        elif in_version_history and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_version_history:
            version_history_content.append(line)
    
    version_history_text = "\n".join(version_history_content)
    
    if f"| {version} |" in version_history_text and changes in version_history_text:
        return True
    
    print(f"  ❌ ERROR: Version {version} not found in version history")
    print("  Version history content:")
    print(version_history_text)
    return False


def test_realistic_scenario():
    """Test the fix with a realistic multi-version update scenario."""
    print("=" * 70)
    print("REALISTIC E2E SCENARIO TEST")
    print("=" * 70)
    print()
    
    lines = create_realistic_document()
    
    # Simulate multiple version updates as described in problem statement
    updates = [
        ("0.1", "Problem Statement completed"),
        ("0.2", "Goals Objectives completed"),
        ("0.3", "Success Criteria completed"),
        ("0.4", "Stakeholders Users completed"),
        ("0.5", "Assumptions completed"),
        ("0.6", "Constraints completed"),
        ("0.7", "Coherence Check completed"),
    ]
    
    all_passed = True
    
    for version, changes in updates:
        print(f"Applying version {version}: {changes}")
        lines = update_document_version(lines, version, changes)
        
        # Validate version is in history
        if not validate_version_in_history(lines, version, changes):
            all_passed = False
            break
        
        print(f"  ✅ Version {version} entry is in version history")
    
    if not all_passed:
        return False
    
    print()
    print("Validating that other tables are NOT corrupted...")
    
    # Check that all versions from 0.4 onwards (which triggered the bug) 
    # did NOT corrupt other tables
    corrupted_versions = ["0.4", "0.5", "0.6", "0.7"]
    
    checks = [
        ("<!-- subsection:primary_stakeholders -->", "Primary Stakeholders table", corrupted_versions),
        ("<!-- subsection:end_users -->", "End Users table", corrupted_versions),
        ("<!-- subsection:technical_constraints -->", "Technical Constraints table", corrupted_versions),
        ("<!-- subsection:operational_constraints -->", "Operational Constraints table", corrupted_versions),
    ]
    
    for marker, name, versions in checks:
        if validate_section_not_corrupted(lines, marker, name, versions):
            print(f"  ✅ {name} is NOT corrupted")
        else:
            all_passed = False
    
    print()
    
    # Count version entries in version history
    in_version_history = False
    version_entries = 0
    
    for line in lines:
        if "<!-- subsection:version_history -->" in line:
            in_version_history = True
        elif in_version_history and ("<!-- section:" in line or "<!-- subsection:" in line):
            break
        elif in_version_history and line.strip().startswith("|"):
            # Skip header and separator rows
            if "Version" not in line and "---" not in line and "PLACEHOLDER" not in line:
                cells = [cell.strip() for cell in line.split("|")]
                # Check if this looks like a version entry (first cell should be a version number)
                if len(cells) > 1 and cells[1] and cells[1][0].isdigit():
                    version_entries += 1
    
    expected_entries = len(updates)
    if version_entries == expected_entries:
        print(f"✅ Version history has exactly {version_entries} entries (expected {expected_entries})")
    else:
        print(f"❌ Version history has {version_entries} entries (expected {expected_entries})")
        all_passed = False
    
    print()
    
    if all_passed:
        print("✅ REALISTIC E2E SCENARIO TEST PASSED")
        print("   All version entries are in the correct location")
        print("   No tables were corrupted")
    else:
        print("❌ REALISTIC E2E SCENARIO TEST FAILED")
    
    return all_passed


if __name__ == "__main__":
    print()
    print("#" * 70)
    print("# VERSION HISTORY BUG FIX - E2E VALIDATION")
    print("#" * 70)
    print()
    
    success = test_realistic_scenario()
    
    sys.exit(0 if success else 1)
