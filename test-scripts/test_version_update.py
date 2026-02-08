#!/usr/bin/env python3
"""
Test script to validate that version fields remain unchanged.

This script tests that:
1. Version fields are not modified by patch application
2. Document Control and header versions remain consistent
"""

import sys
from pathlib import Path

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from invoke_requirements_agent import apply_patches


def test_version_unchanged_review_mode():
    """Test that version fields are unchanged in review mode."""
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
    
    updated_doc = apply_patches(sample_doc, agent_output, "review")

    assert "| 0.0 |" in updated_doc, "Version History should remain unchanged"
    assert "| Current Version | 0.0 |" in updated_doc, "Current Version should remain unchanged"
    assert "| Last Modified | 2026-01-01 |" in updated_doc, "Last Modified should remain unchanged"
    assert "| Modified By | Template |" in updated_doc, "Modified By should remain unchanged"
    assert "**Version:** 0.0" in updated_doc, "Header version should remain unchanged"

    print("✓ Review mode version unchanged test passed")


def test_version_unchanged_integrate_mode():
    """Test that version fields are unchanged in integrate mode."""
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

### INTEGRATED_SECTIONS
No updates
"""

    updated_doc = apply_patches(sample_doc, agent_output, "integrate")

    assert "| 0.5 |" in updated_doc, "Version History should remain unchanged"
    assert "| Current Version | 0.5 |" in updated_doc, "Current Version should remain unchanged"
    assert "| Last Modified | 2026-01-01 |" in updated_doc, "Last Modified should remain unchanged"
    assert "| Modified By | Previous Agent |" in updated_doc, "Modified By should remain unchanged"
    assert "**Version:** 0.5" in updated_doc, "Header version should remain unchanged"

    print("✓ Integrate mode version unchanged test passed")


def test_consistency():
    """Test that all version references remain consistent."""
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
    
    updated_doc = apply_patches(sample_doc, agent_output, "review")
    
    # Extract version from different locations
    import re
    
    # Version History
    vh_match = re.search(r'\| (\d+\.\d+) \|.*?\| Human \|', updated_doc)
    assert vh_match, "Version History should have existing entry"
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
    assert vh_version == dc_version == hdr_version == "1.2", \
        f"All versions should be consistent: VH={vh_version}, DC={dc_version}, HDR={hdr_version}"

    print("✓ Consistency test passed")


if __name__ == "__main__":
    try:
        test_version_unchanged_review_mode()
        test_version_unchanged_integrate_mode()
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
