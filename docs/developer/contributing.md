# Contributing to Orchestrator Agent

Thank you for your interest in contributing to the Orchestrator Agent project! This guide provides technical details for developers who want to contribute to the codebase.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Code Structure](#code-structure)
4. [Development Workflow](#development-workflow)
5. [Testing Guidelines](#testing-guidelines)
6. [Code Style](#code-style)
7. [Pull Request Process](#pull-request-process)
8. [Common Tasks](#common-tasks)

---

## Architecture Overview

The Orchestrator Agent uses a **document-driven workflow model** where processing order is declared in templates, not hardcoded in the application. For comprehensive architecture details, see the [Architecture Guide](../architecture/overview.md).

### Core Components

- **CLI** (`tools/requirements_automation/cli.py`): Command-line interface and argument parsing
- **WorkflowRunner** (`tools/requirements_automation/runner_v2.py`): Main workflow orchestration
- **HandlerRegistry** (`tools/requirements_automation/handler_registry.py`): Section behavior configuration
- **ProfileLoader** (`tools/requirements_automation/profile_loader.py`): LLM profile management
- **LLMClient** (`tools/requirements_automation/llm.py`): OpenAI API wrapper
- **Parsing** (`tools/requirements_automation/parsing.py`): Document structure parsing
- **Validators** (`tools/requirements_automation/document_validator.py`, `structural_validator.py`): Validation logic

### Key Concepts

1. **Document-Driven Workflow**: Templates declare workflow order, not code
2. **Handler Registry**: YAML configuration maps `(doc_type, section_id)` → processing behavior
3. **Unified Processing Loop**: Single code path for all section types
4. **LLM Profiles**: Rules-based prompts (base policy + task style)
5. **Review Gates**: Quality assurance checkpoints in workflow

For detailed explanations, see:
- [Architecture Guide](../architecture/overview.md)
- [Handler Registry Guide](handler-registry-guide.md)
- [LLM Profiles Guide](llm-profiles-guide.md)

---

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- OpenAI API key

### Clone Repository

```bash
git clone https://github.com/Jmiracle76/orchestrator-agent.git
cd orchestrator-agent
```

### Install Dependencies

```bash
# If requirements.txt exists
pip install -r requirements.txt

# Or install manually
pip install openai pyyaml
```

### Set Environment Variables

```bash
export OPENAI_API_KEY="your-api-key-here"
```

Or add to `.env` file:

```bash
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

### Verify Setup

```bash
python -m tools.requirements_automation.cli --help
```

Should display CLI help without errors.

---

## Code Structure

```
orchestrator-agent/
├── tools/
│   ├── config/
│   │   └── handler_registry.yaml       # Section handler configurations
│   ├── profiles/
│   │   ├── base_policy.md              # Base LLM policy (always injected)
│   │   ├── requirements.md             # Requirements LLM profile
│   │   └── requirements_review.md      # Requirements review LLM profile
│   ├── agent-profiles/
│   │   ├── coding-agent.md             # Coding agent profile
│   │   ├── orchestration-agent.md      # Orchestration agent profile
│   │   └── ...                         # Other agent profiles
│   └── requirements_automation/
│       ├── cli.py                      # CLI entry point
│       ├── runner_v2.py                # WorkflowRunner (main orchestration)
│       ├── handler_registry.py         # Handler registry loader
│       ├── profile_loader.py           # LLM profile loader
│       ├── llm.py                      # LLM client (OpenAI wrapper)
│       ├── parsing.py                  # Document parsing
│       ├── models.py                   # Data models
│       ├── config.py                   # Configuration constants
│       ├── document_validator.py       # Completion validation
│       ├── structural_validator.py     # Structure validation
│       ├── editing.py                  # Document editing utilities
│       ├── sanitize.py                 # Output sanitization
│       ├── formatting.py               # Output formatting
│       ├── utils_io.py                 # File I/O utilities
│       ├── git_utils.py                # Git integration
│       └── phases/                     # Legacy phase-based code (deprecated)
├── docs/
│   ├── architecture/
│   │   └── overview.md                 # Architecture documentation
│   ├── developer/
│   │   ├── contributing.md             # This file
│   │   ├── handler-registry-guide.md   # Handler configuration guide
│   │   └── llm-profiles-guide.md       # LLM profiles guide
│   └── templates/                      # Document templates
│       └── requirements-template.md
├── test-scripts/
│   ├── test_integration.py         # Integration tests
│   ├── test_e2e_prior_context.py   # End-to-end tests
│   ├── test_cli_*.py               # CLI tests
│   └── validate_*.py               # Validation tests
├── test-archive/
│   ├── ARCHIVE_README.md           # Archive documentation
│   └── *.py                        # Archived unit tests
├── README.md                       # Main documentation
└── contributing.md                 # This file
```

---

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements

### 2. Make Changes

Follow these principles:
- **Minimal Changes**: Change as few lines as possible
- **Single Responsibility**: Each commit should address one thing
- **Configuration over Code**: Add behavior via YAML/markdown, not Python
- **Test First**: Write tests before implementing (when feasible)

### 3. Test Your Changes

```bash
# Run integration tests
python test-scripts/test_integration.py
python test-scripts/test_e2e_prior_context.py

# Run CLI tests
python test-scripts/test_cli_template_creation.py
python test-scripts/test_cli_validate.py

# Run acceptance criteria validation
python test-scripts/validate_acceptance_criteria.py
python test-scripts/validate_prior_context_acceptance_criteria.py
python test-scripts/validate_review_gate_acceptance_criteria.py
python test-scripts/validate_structural_validation_acceptance_criteria.py

# Test with real document (dry run)
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/test-requirements.md \
  --repo-root . \
  --dry-run
```

### 4. Commit Changes

```bash
git add .
git commit -m "Brief description of change

Detailed explanation if needed:
- What was changed
- Why it was changed
- Any breaking changes or migration notes"
```

Commit message format:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed explanation (wrap at 72 chars)
- Reference issues: "Fixes #123" or "Relates to #456"

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title describing the change
- Description explaining what and why
- Links to related issues
- Any breaking changes or migration notes

---

## Testing Guidelines

### Active Tests

The project maintains integration and validation tests in `test-scripts/`. Unit tests have been archived in `test-archive/` to focus on MVP delivery.

**Active Test Types**:
- **Integration Tests**: End-to-end workflow testing (`test_integration.py`, `test_e2e_prior_context.py`)
- **CLI Tests**: Command-line interface testing (`test_cli_*.py`)
- **Validation Tests**: Acceptance criteria validation (`validate_*.py`)

**Location**: `test-scripts/`

### Archived Unit Tests

Unit tests for individual components have been archived to `test-archive/` as part of focusing on integration and validation testing. See `test-archive/ARCHIVE_README.md` for details on archived tests.

### Integration Tests

**Purpose**: Test component interactions and end-to-end workflows.

**Location**: `test-scripts/test_integration.py`

**Example**:

```python
# test-scripts/test_integration.py

def test_workflow_runner_with_handler_registry():
    """Test WorkflowRunner using HandlerRegistry."""
    lines = load_test_document()
    llm = LLMClient()
    registry = HandlerRegistry("tools/config/handler_registry.yaml")
    
    runner = WorkflowRunner(lines, llm, "requirements", workflow_order, registry)
    result = runner.run_once(dry_run=True)
    
    assert result.outcome in ["blocked", "updated", "no-op"]
```

**Run**:

```bash
python test-scripts/test_integration.py
```

### Manual Testing

**Purpose**: Test with real documents and LLM calls.

**Steps**:

1. Create test document:
   ```bash
   cp docs/templates/requirements-template.md docs/test-requirements.md
   ```

2. Run workflow (dry run):
   ```bash
   python -m tools.requirements_automation.cli \
     --template docs/templates/requirements-template.md \
     --doc docs/test-requirements.md \
     --repo-root . \
     --dry-run
   ```

3. Review output:
   - Check logs for errors
   - Verify section content matches expectations
   - Ensure questions are appropriate
   - Validate integration quality

4. Run without dry-run:
   ```bash
   python -m tools.requirements_automation.cli \
     --template docs/templates/requirements-template.md \
     --doc docs/test-requirements.md \
     --repo-root . \
     --no-commit
   ```

5. Review changes:
   ```bash
   git diff docs/test-requirements.md
   ```

### Regression Testing

**Purpose**: Ensure changes don't break existing functionality.

**Steps**:

1. Run all tests:
   ```bash
   python test-scripts/test_integration.py
   python test-scripts/test_e2e_prior_context.py
   python test-scripts/test_cli_template_creation.py
   python test-scripts/test_cli_validate.py
   python test-scripts/validate_acceptance_criteria.py
   python test-scripts/validate_prior_context_acceptance_criteria.py
   python test-scripts/validate_review_gate_acceptance_criteria.py
   python test-scripts/validate_structural_validation_acceptance_criteria.py
   ```

2. Test with existing documents:
   ```bash
   python -m tools.requirements_automation.cli \
     --template docs/templates/requirements-template.md \
     --doc docs/requirements.md \
     --repo-root . \
     --validate
   ```

3. Check structure:
   ```bash
   python -m tools.requirements_automation.cli \
     --template docs/templates/requirements-template.md \
     --doc docs/requirements.md \
     --repo-root . \
     --validate-structure
   ```

---

## Code Style

### Python Style

- Follow PEP 8 style guide
- Use type hints where possible
- Write docstrings for public functions/classes
- Keep functions focused and small

**Example**:

```python
def get_handler(self, doc_type: str, section_id: str) -> HandlerConfig:
    """
    Get handler configuration for a specific (doc_type, section_id) pair.
    
    Args:
        doc_type: Document type (e.g., "requirements", "research")
        section_id: Section identifier (e.g., "problem_statement")
    
    Returns:
        HandlerConfig object with section processing configuration
    
    Raises:
        HandlerRegistryError: If configuration is invalid or missing
    """
    # Implementation
```

### YAML Style

- Use 2-space indentation
- Add comments explaining complex configurations
- Group related configurations
- Use consistent naming (snake_case)

**Example**:

```yaml
requirements:
  problem_statement:
    mode: integrate_then_questions
    output_format: prose
    llm_profile: requirements
    # Add other fields as needed
```

### Markdown Style

- Use ATX-style headers (`#`, `##`, `###`)
- Wrap prose at 100 characters
- Use fenced code blocks with language identifiers
- Use meaningful link text (not "click here")

**Example**:

```markdown
# Top-Level Header

Brief introduction paragraph that wraps at 100 characters for readability.

## Second-Level Header

Some content with a [meaningful link](../architecture/overview.md).

```python
# Code block with language identifier
def example():
    pass
```
```

---

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
2. **Test Manually**: Test with real documents
3. **Update Documentation**: Update relevant docs
4. **Check Style**: Follow code style guidelines
5. **Review Changes**: Use `git diff` to review all changes

### PR Description Template

```markdown
## Description
[Brief description of what this PR does]

## Motivation
[Why is this change needed? What problem does it solve?]

## Changes Made
- [Change 1]
- [Change 2]
- [Change 3]

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manually tested with real documents
- [ ] Regression testing completed

## Documentation
- [ ] README.md updated (if needed)
- [ ] Architecture docs updated (if needed)
- [ ] Handler/profile docs updated (if needed)
- [ ] Code comments added

## Breaking Changes
[List any breaking changes and migration notes, or "None"]

## Related Issues
Fixes #123
Relates to #456
```

### Review Process

1. **Automated Checks**: CI runs tests and linters
2. **Code Review**: Maintainer reviews code
3. **Feedback**: Address any review comments
4. **Approval**: Maintainer approves PR
5. **Merge**: PR is merged into main branch

---

## Common Tasks

### Adding a New Section Type

See [Handler Registry Guide](handler-registry-guide.md#adding-a-new-section-type) for step-by-step instructions.

**Quick Steps**:

1. Add section marker to template
2. Add to workflow order
3. Configure handler in `tools/config/handler_registry.yaml`
4. Test

### Adding a New Document Type

See [Handler Registry Guide](handler-registry-guide.md#adding-a-new-doc-type) for step-by-step instructions.

**Quick Steps**:

1. Create template with `doc_type` metadata
2. Add handler configurations to `tools/config/handler_registry.yaml`
3. Create LLM profile in `tools/profiles/`
4. Update `SUPPORTED_DOC_TYPES` in `config.py`
5. Test

### Adding a New LLM Profile

See [LLM Profiles Guide](llm-profiles-guide.md#adding-new-profiles) for step-by-step instructions.

**Quick Steps**:

1. Create markdown file in `tools/profiles/`
2. Write clear, concrete rules
3. Reference in handler configuration
4. Test with real documents
5. Iterate based on results

### Adding a New Handler Mode

**Steps**:

1. **Update Models**:
   ```python
   # tools/requirements_automation/models.py
   
   class HandlerConfig:
       mode: Literal["integrate_then_questions", "questions_then_integrate", "review_gate", "generate_only"]
   ```

2. **Add Handler Method**:
   ```python
   # tools/requirements_automation/runner_v2.py
   
   def _execute_generate_only(self, section_id: str, handler_config: HandlerConfig) -> RunResult:
       """Execute generate_only mode."""
       # Implementation
   ```

3. **Update run_once()**:
   ```python
   elif handler_config.mode == "generate_only":
       result = self._execute_generate_only(target, handler_config)
   ```

4. **Document**: Update Handler Registry Guide with new mode
5. **Test**: Add unit and integration tests

### Modifying Validation Rules

**Steps**:

1. **Update Validator**:
   ```python
   # tools/requirements_automation/structural_validator.py
   
   def validate_new_rule(self) -> List[ValidationError]:
       """Validate a new rule."""
       errors = []
       # Implementation
       return errors
   ```

2. **Call from validate_all()**:
   ```python
   def validate_all(self) -> List[ValidationError]:
       errors = []
       errors.extend(self.validate_markers())
       errors.extend(self.validate_new_rule())  # Add new rule
       return errors
   ```

3. **Test**: Add test cases for new validation
4. **Document**: Update documentation with new validation rule

### Debugging Issues

**Common debugging techniques**:

1. **Enable Debug Logging**:
   ```bash
   python -m tools.requirements_automation.cli \
     --log-level DEBUG \
     ...
   ```

2. **Use Dry Run**:
   ```bash
   python -m tools.requirements_automation.cli \
     --dry-run \
     ...
   ```

3. **Check Structure**:
   ```bash
   python -m tools.requirements_automation.cli \
     --validate-structure \
     ...
   ```

4. **Validate Completion**:
   ```bash
   python -m tools.requirements_automation.cli \
     --validate \
     ...
   ```

5. **Review Handler Config**:
   ```bash
   cat tools/config/handler_registry.yaml
   ```

6. **Check LLM Profile**:
   ```bash
   cat tools/profiles/requirements.md
   ```

---

## Getting Help

- **Documentation**: Start with [README.md](../../README.md) and [Architecture Guide](../architecture/overview.md)
- **Issues**: Check [GitHub Issues](https://github.com/Jmiracle76/orchestrator-agent/issues) for known problems
- **Questions**: Open a GitHub Discussion or create an issue with the "question" label

---

## License

[Specify license information here]

---

Thank you for contributing to the Orchestrator Agent project!