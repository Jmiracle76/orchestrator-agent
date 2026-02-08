#!/usr/bin/env python3
"""
Validation script to detect markdown tables in agent-generated documents.

This script checks for markdown table syntax in documentation files
to ensure agents are following the prohibition against table creation.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def detect_markdown_tables(content: str) -> List[Tuple[int, str]]:
    """
    Detect markdown table patterns in content.
    
    Returns a list of (line_number, line_content) tuples for lines
    that appear to be part of a markdown table.
    """
    lines = content.split('\n')
    table_lines = []
    
    # Pattern to detect markdown table separator lines (e.g., |---|---|)
    separator_pattern = re.compile(r'^\s*\|[\s\-:]+\|\s*$')
    
    # Pattern to detect markdown table data lines (e.g., | cell1 | cell2 |)
    table_pattern = re.compile(r'^\s*\|[^\n]+\|\s*$')
    
    for i, line in enumerate(lines, start=1):
        # Check for table separator line (strong indicator of a table)
        if separator_pattern.match(line):
            table_lines.append((i, line.strip()))
        # Check for potential table data line (only if it looks like a table)
        elif table_pattern.match(line) and '|' in line:
            # Additional check: must have at least 2 pipe characters
            if line.count('|') >= 3:  # At least | content | content |
                table_lines.append((i, line.strip()))
    
    return table_lines


def validate_file(file_path: Path, skip_examples: bool = True) -> Tuple[bool, List[Tuple[int, str]]]:
    """
    Validate a single file for markdown tables.
    
    Args:
        file_path: Path to the file to validate
        skip_examples: If True, skip checking content within code blocks (default: True)
    
    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # If skip_examples is True, remove code blocks before checking
        if skip_examples:
            # Remove content between triple backticks (code blocks)
            content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
            # Remove content between single backticks (inline code)
            content = re.sub(r'`[^`]+`', '', content)
        
        violations = detect_markdown_tables(content)
        
        return len(violations) == 0, violations
        
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return False, []


def validate_directory(directory: Path, pattern: str = "*.md", skip_examples: bool = True) -> bool:
    """
    Validate all markdown files in a directory.
    
    Args:
        directory: Directory to scan
        pattern: File pattern to match (default: "*.md")
        skip_examples: If True, skip checking content within code blocks
    
    Returns:
        True if all files are valid, False otherwise
    """
    all_valid = True
    files_checked = 0
    
    for file_path in directory.rglob(pattern):
        # Skip certain directories
        if any(part in file_path.parts for part in ['.git', 'node_modules', '__pycache__']):
            continue
            
        files_checked += 1
        is_valid, violations = validate_file(file_path, skip_examples)
        
        if not is_valid:
            all_valid = False
            print(f"\n❌ Table(s) detected in: {file_path}")
            print(f"   Found {len(violations)} potential table line(s):")
            for line_num, line_content in violations[:5]:  # Show first 5 violations
                print(f"   Line {line_num}: {line_content}")
            if len(violations) > 5:
                print(f"   ... and {len(violations) - 5} more")
    
    print(f"\n{'✅' if all_valid else '❌'} Checked {files_checked} file(s)")
    return all_valid


def main():
    """Main entry point for the validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate that documentation files don't contain markdown tables"
    )
    parser.add_argument(
        'path',
        type=Path,
        nargs='?',
        default=Path.cwd(),
        help='Path to file or directory to validate (default: current directory)'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*.md',
        help='File pattern to match (default: *.md)'
    )
    parser.add_argument(
        '--include-examples',
        action='store_true',
        help='Include code blocks in validation (by default, they are skipped)'
    )
    
    args = parser.parse_args()
    
    path = args.path.resolve()
    skip_examples = not args.include_examples
    
    print(f"🔍 Validating markdown files for table prohibition...")
    print(f"   Path: {path}")
    print(f"   Pattern: {args.pattern}")
    print(f"   Skip code blocks: {skip_examples}")
    
    if path.is_file():
        is_valid, violations = validate_file(path, skip_examples)
        if not is_valid:
            print(f"\n❌ Table(s) detected in: {path}")
            print(f"   Found {len(violations)} potential table line(s):")
            for line_num, line_content in violations:
                print(f"   Line {line_num}: {line_content}")
            sys.exit(1)
        else:
            print(f"\n✅ No tables detected in: {path}")
            sys.exit(0)
    
    elif path.is_dir():
        is_valid = validate_directory(path, args.pattern, skip_examples)
        sys.exit(0 if is_valid else 1)
    
    else:
        print(f"❌ Error: Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
