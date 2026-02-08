# Table Validation Tool

## Purpose

This validation tool enforces the prohibition against markdown table creation in agent-generated documentation. It scans markdown files to detect table syntax and reports violations.

## Background

As per the agent instructions update, all agents are prohibited from creating or modifying markdown tables in their outputs. Instead, agents should use section-based narrative structures with headings, bullet points, and descriptive paragraphs.

## Usage

### Validate a single file

```bash
python3 tools/validate_no_tables.py path/to/file.md
```

### Validate all markdown files in a directory

```bash
python3 tools/validate_no_tables.py path/to/directory/
```

### Validate current directory

```bash
python3 tools/validate_no_tables.py
```

### Options

- `--pattern PATTERN`: Specify file pattern to match (default: `*.md`)
- `--include-examples`: Include code blocks in validation (by default, tables in code blocks are ignored)

### Examples

Validate agent profiles directory:
```bash
python3 tools/validate_no_tables.py agent-profiles/
```

Validate all markdown files including examples in code blocks:
```bash
python3 tools/validate_no_tables.py docs/ --include-examples
```

Validate only specific markdown files:
```bash
python3 tools/validate_no_tables.py docs/ --pattern "requirements*.md"
```

## Exit Codes

- `0`: No tables detected (success)
- `1`: Tables detected or error occurred (failure)

## What is Detected

The tool detects markdown table syntax including:

- Table separator lines (e.g., `|---|---|`)
- Table data lines with multiple pipe characters (e.g., `| Cell 1 | Cell 2 |`)

## What is Ignored (by default)

- Content within code blocks (triple backticks)
- Inline code (single backticks)
- Single pipe characters in regular text

This ensures that documentation examples showing table syntax (like the agent profiles that demonstrate what NOT to do) are not flagged.

## Testing

Run the test suite to ensure the validation tool works correctly:

```bash
python3 test-scripts/test_validate_no_tables.py
```

## Integration

This tool can be integrated into CI/CD pipelines to automatically validate that agent outputs don't contain tables:

```yaml
# GitHub Actions example
- name: Validate no tables in agent outputs
  run: python3 tools/validate_no_tables.py docs/
```

## Rationale

The prohibition against tables encourages:

1. **Better narrative flow**: Section-based structures are easier to read and understand
2. **Accessibility**: Screen readers handle narrative text better than tables
3. **Maintainability**: Text-based structures are easier to update and version control
4. **Flexibility**: Narrative structures adapt better to different output formats

## Alternative Formats

Instead of tables, use:

### For structured data:

```markdown
### Item 1: Widget A
- **Property:** Value A
- **Status:** Active
- **Notes:** Important information here

### Item 2: Widget B
- **Property:** Value B
- **Status:** Inactive
- **Notes:** More details here
```

### For comparisons:

```markdown
### Option A
- **Pros:** Fast, efficient, widely supported
- **Cons:** Complex setup, steep learning curve
- **Recommendation:** Best for large teams

### Option B
- **Pros:** Simple, quick to deploy
- **Cons:** Limited features
- **Recommendation:** Best for small projects
```

### For status tracking:

```markdown
### Requirements Coverage

#### FR-001: User Authentication
- **Status:** Complete
- **Test Coverage:** TC-001, TC-002, TC-003
- **Acceptance Criteria:** ✅ 100% met
- **Notes:** All security tests passed

#### FR-002: User Profile
- **Status:** In Progress
- **Test Coverage:** TC-004 (pending)
- **Acceptance Criteria:** ⏳ 60% met
- **Notes:** Awaiting design approval
```
