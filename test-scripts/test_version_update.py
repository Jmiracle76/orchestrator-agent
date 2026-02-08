#!/usr/bin/env python3
"""
Test script to validate document version update behavior.

This script tests that:
1. Version History is updated with new version
2. Document Control table fields are updated atomically
3. Header version field is updated
4. All fields are consistent
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import apply_patches


def test_version_update_review_mode():
    """Test that version updates work correctly in review mode."""
    sample_doc = """# Requirements Document

**Version:** 0.0

## 1. Document Control

| Field | Value |
|-------|-------|
| Current Version | 0.0 |
| Last Modified | 2026-01-01 |
| Modified By | Template |

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.0 | 2026-01-01 | Template | Initial version |
"""
    
    agent_output = """## REVIEW_OUTPUT

### STATUS_UPDATE
Ready for Approval

### RISKS
No new risks

### OPEN_QUESTIONS
No new questions
"""
    
    # Apply patches in review mode
    updated_doc, _ = apply_patches(sample_doc, agent_output, "review")
    
    # Verify Version History was updated
    assert "| 0.1 |" in updated_doc, "Version History should contain 0.1"
    assert "Requirements Agent" in updated_doc, "Version History should credit Requirements Agent"
    
    # Verify Document Control table was updated
    assert "| Current Version | 0.1 |" in updated_doc, "Current Version should be updated to 0.1"
    
    # Verify Last Modified contains today's date in the Document Control table
    import re
    dc_last_modified = re.search(r'\| Last Modified \| ([\d-]+) \|', updated_doc)
    assert dc_last_modified, "Last Modified should exist in Document Control table"
    assert "2026-" in dc_last_modified.group(1), "Last Modified should contain current date"
    
    assert "| Modified By | Requirements Agent |" in updated_doc, "Modified By should be updated"
    
    # Verify header version was updated
    assert "**Version:** 0.1" in updated_doc, "Header version should be updated to 0.1"
    
    print("✓ Review mode version update test passed")


def test_version_increment():
    """Test that version increments correctly."""
    sample_doc = """# Requirements Document

**Version:** 0.5

## 1. Document Control

| Field | Value |
|-------|-------|
| Current Version | 0.5 |
| Last Modified | 2026-01-01 |
| Modified By | Previous Agent |

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.5 | 2026-01-15 | Previous Agent | Previous change |
| 0.0 | 2026-01-01 | Template | Initial version |
"""
    
    agent_output = """## INTEGRATION_OUTPUT

### STATUS_UPDATE
Pending

### PATCHES
No patches
"""
    
    # Apply patches in integrate mode
    updated_doc, _ = apply_patches(sample_doc, agent_output, "integrate")
    
    # Verify version was incremented to 0.6
    assert "| 0.6 |" in updated_doc, "Version should be incremented to 0.6"
    assert "| Current Version | 0.6 |" in updated_doc, "Current Version should be 0.6"
    assert "**Version:** 0.6" in updated_doc, "Header version should be 0.6"
    
    print("✓ Version increment test passed")


def test_consistency():
    """Test that all version references are consistent."""
    sample_doc = """# Requirements Document

**Version:** 1.2

## 1. Document Control

| Field | Value |
|-------|-------|
| Current Version | 1.2 |
| Last Modified | 2026-01-01 |
| Modified By | Human |

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.2 | 2026-01-20 | Human | Some changes |
"""
    
    agent_output = """## REVIEW_OUTPUT

### STATUS_UPDATE
Ready for Approval
"""
    
    updated_doc, _ = apply_patches(sample_doc, agent_output, "review")
    
    # Extract version from different locations
    import re
    
    # Version History
    vh_match = re.search(r'\| (\d+\.\d+) \|.*?\| Requirements Agent \|', updated_doc)
    assert vh_match, "Version History should have new entry"
    vh_version = vh_match.group(1)
    
    # Document Control
    dc_match = re.search(r'\| Current Version \| (\d+\.\d+) \|', updated_doc)
    assert dc_match, "Document Control should have Current Version"
    dc_version = dc_match.group(1)
    
    # Header
    hdr_match = re.search(r'\*\*Version:\*\* (\d+\.\d+)', updated_doc)
    assert hdr_match, "Header should have Version field"
    hdr_version = hdr_match.group(1)
    
    # All should be the same
    assert vh_version == dc_version == hdr_version == "1.3", \
        f"All versions should be consistent: VH={vh_version}, DC={dc_version}, HDR={hdr_version}"
    
    print("✓ Consistency test passed")


if __name__ == "__main__":
    try:
        test_version_update_review_mode()
        test_version_increment()
        test_consistency()
        print("\n✓ All version update tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
