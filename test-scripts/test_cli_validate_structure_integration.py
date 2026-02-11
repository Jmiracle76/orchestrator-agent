#!/usr/bin/env python3
"""
Integration test for CLI --validate-structure with auto-repair.

This test validates that the CLI correctly detects missing open questions
table and auto-repairs it.
"""
import sys
import tempfile
import os
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.cli import main
from requirements_automation.utils_io import read_text, split_lines
from requirements_automation.open_questions import open_questions_parse


def test_cli_validate_structure_with_missing_table():
    """Test --validate-structure detects and repairs missing open questions table."""
    print("\nTest: CLI --validate-structure with missing table...")
    
    # Create a temporary document with missing open questions table
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""<!-- meta:doc_type value="requirements" -->
<!-- meta:doc_format version="1.0" -->

<!-- workflow:order
problem_statement
risks_open_issues
-->

# Requirements Document

<!-- section:problem_statement -->
## Problem Statement
Test content

<!-- section_lock:problem_statement lock=false -->
---

<!-- section:risks_open_issues -->
## Risks and Open Issues

<!-- subsection:identified_risks -->
### Identified Risks
No risks

<!-- section_lock:risks_open_issues lock=false -->
---
""")
        temp_doc = Path(f.name)
    
    # Create a temporary template (minimal)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
-->
""")
        temp_template = Path(f.name)
    
    # Use actual repo root (has handler registry)
    temp_repo = repo_root
    
    try:
        # Run --validate-structure
        args = [
            "--template", str(temp_template),
            "--doc", str(temp_doc),
            "--repo-root", str(temp_repo),
            "--validate-structure"
        ]
        
        exit_code = main(args)
        
        # Should return 1 (repair was performed)
        if exit_code != 1:
            print(f"  ✗ Expected exit code 1, got {exit_code}")
            return False
        
        # Check that the document was repaired
        lines = split_lines(read_text(temp_doc))
        
        # Verify subsection marker exists
        has_subsection = any("<!-- subsection:open_questions -->" in line for line in lines)
        if not has_subsection:
            print("  ✗ Subsection marker not found after repair")
            return False
        
        # Verify table marker exists
        has_table = any("<!-- table:open_questions -->" in line for line in lines)
        if not has_table:
            print("  ✗ Table marker not found after repair")
            return False
        
        # Verify the table can be parsed by open_questions_parse
        try:
            questions, span, header = open_questions_parse(lines)
            print(f"  ✓ Document repaired successfully")
            print(f"    - Subsection marker: present")
            print(f"    - Table marker: present")
            print(f"    - Table parseable: yes")
            print(f"    - Exit code: {exit_code}")
            return True
        except Exception as e:
            print(f"  ✗ Failed to parse repaired table: {e}")
            return False
        
    finally:
        # Cleanup
        if temp_doc.exists():
            temp_doc.unlink()
        if temp_template.exists():
            temp_template.unlink()


def test_cli_validate_structure_with_complete_table():
    """Test --validate-structure passes with complete table."""
    print("\nTest: CLI --validate-structure with complete table...")
    
    # Create a temporary document with complete open questions table
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""<!-- meta:doc_type value="requirements" -->
<!-- meta:doc_format version="1.0" -->

<!-- workflow:order
problem_statement
risks_open_issues
-->

# Requirements Document

<!-- section:problem_statement -->
## Problem Statement
Test content

<!-- section_lock:problem_statement lock=false -->
---

<!-- section:risks_open_issues -->
## Risks and Open Issues

<!-- subsection:identified_risks -->
### Identified Risks
No risks

<!-- subsection:open_questions -->
### Open Questions

<!-- table:open_questions -->
| Question ID | Question | Date | Answer | Section Target | Resolution Status |
|-------------|----------|------|--------|----------------|-------------------|
| Q-001 | Test? | 2024-01-01 | Yes | problem_statement | Resolved |

<!-- section_lock:risks_open_issues lock=false -->
---
""")
        temp_doc = Path(f.name)
    
    # Create a temporary template (minimal)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
problem_statement
-->
""")
        temp_template = Path(f.name)
    
    # Use actual repo root (has handler registry)
    temp_repo = repo_root
    
    try:
        # Run --validate-structure
        args = [
            "--template", str(temp_template),
            "--doc", str(temp_doc),
            "--repo-root", str(temp_repo),
            "--validate-structure"
        ]
        
        exit_code = main(args)
        
        # Should return 0 (no repairs needed)
        if exit_code == 0:
            print(f"  ✓ Complete table structure validated")
            print(f"    - Exit code: {exit_code}")
            return True
        else:
            print(f"  ✗ Expected exit code 0, got {exit_code}")
            return False
        
    finally:
        # Cleanup
        if temp_doc.exists():
            temp_doc.unlink()
        if temp_template.exists():
            temp_template.unlink()


def main_test():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("CLI INTEGRATION TEST FOR OPEN QUESTIONS VALIDATION")
    print("=" * 70)
    
    tests = [
        test_cli_validate_structure_with_missing_table,
        test_cli_validate_structure_with_complete_table,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Passed: {passed}/{total}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main_test())
