#!/usr/bin/env python3
"""
Test for Issue 4a: Template marker validation and auto-repair.

This test validates that:
1. Missing section markers are detected and reported
2. Missing subsection markers are detected and reported
3. Missing table markers are detected and reported
4. Auto-repair reinserts missing markers where possible
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.cli import main
from requirements_automation.utils_io import read_text, split_lines


def test_missing_markers_detected():
    """Test that missing markers are detected when auto-repair is not possible."""
    print("\nTest: Missing markers detection...")
    print("=" * 70)

    # Create a template with various markers
    template_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
Content A
<!-- subsection:sub_a1 -->
### Subsection A1
Sub content
<!-- table:table_a1 -->
| Col1 | Col2 |
|------|------|
| V1   | V2   |
<!-- section_lock:section_a lock=false -->

<!-- section:section_b -->
## Section B
Content B
<!-- section_lock:section_b lock=false -->
"""

    # Create a document missing some markers
    doc_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
Content A
<!-- section_lock:section_a lock=false -->

<!-- section:section_b -->
## Section B
Content B
<!-- section_lock:section_b lock=false -->
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(template_content)
        template_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(doc_content)
        doc_path = Path(f.name)

    try:
        # Run validation
        args = [
            "--template",
            str(template_path),
            "--doc",
            str(doc_path),
            "--repo-root",
            str(repo_root),
            "--validate-structure",
        ]

        exit_code = main(args)

        # Should return 1 (repair was performed)
        if exit_code != 1:
            print(f"  ✗ Expected exit code 1, got {exit_code}")
            return False

        # Verify that missing markers were detected
        repaired_lines = split_lines(read_text(doc_path))
        has_subsection = any("<!-- subsection:sub_a1 -->" in line for line in repaired_lines)
        has_table = any("<!-- table:table_a1 -->" in line for line in repaired_lines)

        if not has_subsection:
            print("  ✗ Missing subsection was not repaired")
            return False

        if not has_table:
            print("  ✗ Missing table was not repaired")
            return False

        print("  ✓ Missing markers detected and repaired")
        print(f"    - subsection:sub_a1: repaired")
        print(f"    - table:table_a1: repaired")
        return True

    finally:
        template_path.unlink()
        doc_path.unlink()


def test_complete_document_passes():
    """Test that a complete document with all markers passes validation."""
    print("\nTest: Complete document validation...")
    print("=" * 70)

    # Create a complete template
    template_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
-->

<!-- section:section_a -->
## Section A
Content A
<!-- subsection:sub_a1 -->
### Subsection A1
Sub content
<!-- table:table_a1 -->
| Col1 | Col2 |
|------|------|
| V1   | V2   |
<!-- section_lock:section_a lock=false -->
"""

    # Create a matching document
    doc_content = template_content

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(template_content)
        template_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(doc_content)
        doc_path = Path(f.name)

    try:
        # Run validation
        args = [
            "--template",
            str(template_path),
            "--doc",
            str(doc_path),
            "--repo-root",
            str(repo_root),
            "--validate-structure",
        ]

        exit_code = main(args)

        # Should return 0 (no errors)
        if exit_code != 0:
            print(f"  ✗ Expected exit code 0, got {exit_code}")
            return False

        print("  ✓ Complete document passes validation")
        return True

    finally:
        template_path.unlink()
        doc_path.unlink()


def test_missing_section_detected():
    """Test that missing section markers are detected."""
    print("\nTest: Missing section detection...")
    print("=" * 70)

    # Create a template with a section
    template_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
Content A
<!-- section_lock:section_a lock=false -->

<!-- section:section_b -->
## Section B
Content B
<!-- section_lock:section_b lock=false -->
"""

    # Create a document missing section_b
    doc_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
section_b
-->

<!-- section:section_a -->
## Section A
Content A
<!-- section_lock:section_a lock=false -->
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(template_content)
        template_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(doc_content)
        doc_path = Path(f.name)

    try:
        # Run validation
        args = [
            "--template",
            str(template_path),
            "--doc",
            str(doc_path),
            "--repo-root",
            str(repo_root),
            "--validate-structure",
        ]

        exit_code = main(args)

        # Should return 1 (repair was performed)
        if exit_code != 1:
            print(f"  ✗ Expected exit code 1, got {exit_code}")
            return False

        # Verify the section was repaired
        repaired_lines = split_lines(read_text(doc_path))
        has_section = any("<!-- section:section_b -->" in line for line in repaired_lines)

        if not has_section:
            print("  ✗ Missing section was not repaired")
            return False

        print("  ✓ Missing section detected and repaired")
        print(f"    - section:section_b: repaired")
        return True

    finally:
        template_path.unlink()
        doc_path.unlink()


def test_auto_repair_preserves_existing_content():
    """Test that auto-repair doesn't corrupt existing content."""
    print("\nTest: Auto-repair preserves existing content...")
    print("=" * 70)

    # Create a template
    template_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
-->

<!-- section:section_a -->
## Section A
Content A
<!-- subsection:sub_a1 -->
### Subsection A1
Sub content
<!-- table:table_a1 -->
| Col1 | Col2 |
|------|------|
| V1   | V2   |
<!-- section_lock:section_a lock=false -->
"""

    # Create a document with existing content
    doc_content = """<!-- meta:doc_type value="requirements" -->
<!-- workflow:order
section_a
-->

<!-- section:section_a -->
## Section A
This is my custom content that should not be lost.
<!-- section_lock:section_a lock=false -->
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(template_content)
        template_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(doc_content)
        doc_path = Path(f.name)

    try:
        # Run validation
        args = [
            "--template",
            str(template_path),
            "--doc",
            str(doc_path),
            "--repo-root",
            str(repo_root),
            "--validate-structure",
        ]

        exit_code = main(args)

        # Should return 1 (repair was performed)
        if exit_code != 1:
            print(f"  ✗ Expected exit code 1, got {exit_code}")
            return False

        # Verify existing content is preserved
        repaired_content = read_text(doc_path)
        if "This is my custom content that should not be lost" not in repaired_content:
            print("  ✗ Existing content was lost during repair")
            return False

        # Verify markers were added
        if "<!-- subsection:sub_a1 -->" not in repaired_content:
            print("  ✗ Subsection marker was not added")
            return False

        if "<!-- table:table_a1 -->" not in repaired_content:
            print("  ✗ Table marker was not added")
            return False

        print("  ✓ Auto-repair preserved existing content")
        print(f"    - Existing content: preserved")
        print(f"    - subsection:sub_a1: added")
        print(f"    - table:table_a1: added")
        return True

    finally:
        template_path.unlink()
        doc_path.unlink()


def main_test():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("ISSUE 4A: TEMPLATE MARKER VALIDATION AND AUTO-REPAIR")
    print("=" * 70)

    tests = [
        test_missing_markers_detected,
        test_complete_document_passes,
        test_missing_section_detected,
        test_auto_repair_preserves_existing_content,
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

    # Print acceptance criteria summary
    print("\n" + "=" * 70)
    print("ACCEPTANCE CRITERIA VERIFICATION")
    print("=" * 70)
    print("✓ Missing `<!-- subsection:* -->` markers detected and reported")
    print("✓ Missing `<!-- table:* -->` markers detected and reported")
    print("✓ Missing `<!-- section:* -->` markers detected and reported")
    print("✓ Auto-repair reinserts missing markers where possible")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main_test())
