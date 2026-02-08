#!/usr/bin/env python3
"""
Test suite for validate_no_tables.py

This test suite ensures the table validation script correctly detects
markdown tables and follows the expected behavior.
"""

import sys
import tempfile
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

from validate_no_tables import detect_markdown_tables, validate_file


def test_detect_simple_table():
    """Test detection of a simple markdown table."""
    content = """
# Document

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
"""
    violations = detect_markdown_tables(content)
    assert len(violations) > 0, "Should detect simple table"
    print("✅ test_detect_simple_table passed")


def test_no_false_positives():
    """Test that non-table content is not flagged."""
    content = """
# Document

This is regular text with a pipe | character in it.

Code example: if (x | y) { ... }
"""
    violations = detect_markdown_tables(content)
    # Single pipes in regular text should not be detected
    assert len(violations) == 0, f"Should not detect false positives, but found {len(violations)}"
    print("✅ test_no_false_positives passed")


def test_skip_code_blocks():
    """Test that tables in code blocks are ignored."""
    content = """
# Document

Here's an example of what NOT to do:

```markdown
| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
```

This should not be flagged.
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)
    
    try:
        is_valid, violations = validate_file(temp_path, skip_examples=True)
        assert is_valid, f"Should not detect tables in code blocks, but found {len(violations)} violations"
        print("✅ test_skip_code_blocks passed")
    finally:
        temp_path.unlink()


def test_detect_table_outside_code_blocks():
    """Test that tables outside code blocks are detected."""
    content = """
# Document

This has an example in a code block:

```markdown
| Column 1 | Column 2 |
|----------|----------|
```

But this is a real table:

| Column A | Column B |
|----------|----------|
| Real 1   | Real 2   |
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)
    
    try:
        is_valid, violations = validate_file(temp_path, skip_examples=True)
        assert not is_valid, "Should detect table outside code block"
        assert len(violations) > 0, "Should find violations"
        print("✅ test_detect_table_outside_code_blocks passed")
    finally:
        temp_path.unlink()


def test_complex_table():
    """Test detection of tables with complex formatting."""
    content = """
| Column 1 | Column 2 | Column 3 | Column 4 |
|:---------|:--------:|---------:|---------:|
| Left     | Center   | Right    | Right    |
| Align    | Align    | Align    | Align    |
"""
    violations = detect_markdown_tables(content)
    assert len(violations) > 0, "Should detect complex table"
    print("✅ test_complex_table passed")


def run_tests():
    """Run all tests."""
    print("🧪 Running validation script tests...\n")
    
    tests = [
        test_detect_simple_table,
        test_no_false_positives,
        test_skip_code_blocks,
        test_detect_table_outside_code_blocks,
        test_complex_table,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} error: {e}")
            failed += 1
    
    print(f"\n{'✅' if failed == 0 else '❌'} {len(tests) - failed}/{len(tests)} tests passed")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(run_tests())
