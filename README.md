# Orchestrator Agent

A document-driven workflow automation system for creating and maintaining requirements documents through LLM-powered interactive workflows.

## Overview

The Orchestrator Agent is a workflow engine that processes structured markdown documents (requirements, research notes, planning docs) by iteratively gathering information through question-and-answer cycles and integrating responses via LLM reasoning. The system uses a **document-driven workflow model** where the processing order is declared in the document template itself, not hardcoded in the application.

### Key Features

- **Document-Driven Workflows**: Workflow order defined in document templates, not code
- **Handler Registry**: YAML-based configuration mapping `(doc_type, section_id)` → processing behavior
- **Unified Processing Loop**: Single code path for all section types, configured via handler registry
- **LLM Profiles**: Rules-based reasoning policies (base policy + task style = full profile)
- **Review Gates**: Quality assurance checkpoints with LLM-powered review and patch suggestions
- **Incremental Processing**: Resume workflows from where they left off
- **Validation Framework**: Structure validation and completion checking

## Quick Start

### Prerequisites

- Python 3.8+
- Git
- OpenAI API key (set via `OPENAI_API_KEY` environment variable)

### Installation

```bash
# Clone the repository
git clone https://github.com/Jmiracle76/orchestrator-agent.git
cd orchestrator-agent

# Install dependencies (if any)
pip install -r requirements.txt  # if requirements.txt exists
```

### Common Use Cases

#### 1. Create a New Requirements Document

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/my-requirements.md \
  --repo-root .
```

This will:
- Create `docs/my-requirements.md` from the template (if it doesn't exist)
- Process the next incomplete section in the workflow
- Generate questions or integrate answers based on handler configuration
- Commit changes automatically

#### 2. Process Multiple Steps at Once

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --max-steps 5
```

Processes up to 5 workflow steps in a single run, stopping if blocked.

#### 3. Validate Document Completion

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --validate
```

Checks if all required sections are complete without processing. Returns JSON status.

#### 4. Strict Validation (Include Optional Sections)

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --validate \
  --strict
```

#### 5. Validate Document Structure Only

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --validate-structure
```

Checks for malformed section markers, corrupted tables, or invalid metadata without processing.

#### 6. Dry Run (No File Changes)

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --dry-run
```

Simulates processing without modifying files or committing changes.

#### 7. Custom Handler Configuration

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --handler-config /path/to/custom/handler_registry.yaml
```

Use a custom handler registry for specialized section behaviors.

## Architecture Overview

The system is built around several core concepts:

### Document-Driven Workflow

Workflows are defined in document templates via metadata markers:

```markdown
<!-- workflow:order
problem_statement
goals_objectives
stakeholders_users
review_gate:coherence_check
approval_record
-->
```

The engine processes sections in the declared order, not in a hardcoded sequence.

### Handler Registry

Maps `(doc_type, section_id)` → processing configuration:

```yaml
requirements:
  problem_statement:
    mode: integrate_then_questions
    output_format: prose
    llm_profile: requirements
```

See [Handler Registry Guide](docs/handler-registry-guide.md) for details.

### Unified Processing Loop

Single `WorkflowRunner` processes all section types:

1. Choose next target from workflow order
2. Load handler configuration for `(doc_type, section_id)`
3. Execute handler mode (integrate answers, generate questions, or review)
4. Sanitize and validate output
5. Update document
6. Repeat

### LLM Profiles

Profiles define LLM reasoning rules:

- **Base Policy** (`profiles/base_policy.md`): Always injected, defines core rules
- **Task Style Profiles** (`profiles/requirements.md`, etc.): Document-type-specific guidance

See [LLM Profiles Guide](docs/llm-profiles-guide.md) for details.

### Review Gates

Special workflow targets that review prior sections:

```markdown
<!-- section:review_gate:coherence_check -->
## Review Gate: Coherence Check
```

Handler configuration:

```yaml
review_gate:coherence_check:
  mode: review_gate
  scope: all_prior_sections
  llm_profile: requirements_review
```

See [Architecture Guide](docs/architecture.md) for comprehensive details.

## CLI Reference

### Required Arguments

- `--template PATH`: Path to document template
- `--doc PATH`: Path to document to process
- `--repo-root PATH`: Repository root directory

### Optional Arguments

- `--dry-run`: Simulate processing without file changes
- `--no-commit`: Skip automatic git commit/push
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--max-steps N`: Process up to N workflow steps (default: 1)
- `--handler-config PATH`: Custom handler registry YAML (default: `config/handler_registry.yaml`)
- `--validate`: Validate document completion without processing
- `--strict`: Enable strict completion checking (includes optional sections)
- `--validate-structure`: Check document structure without processing

### Exit Codes

- `0`: Success (workflow progressed or is complete)
- `1`: Blocked (waiting for user input or validation failed)
- `2`: Error (invalid configuration, corrupted document, etc.)

## Migration from Phase-Based System

**Legacy System (Phases):**

```python
# Old: Hardcoded phase order in config.py
PHASES = {
    "phase1": ["problem_statement", "goals_objectives", ...],
    "phase2": ["stakeholders_users", ...]
}
PHASE_ORDER = ["phase1", "phase2", "phase3"]
```

**New System (Workflow Order):**

```markdown
<!-- In document template -->
<!-- workflow:order
problem_statement
goals_objectives
stakeholders_users
-->
```

**What Changed:**

1. **Workflow order** is now declared in templates, not code
2. **Handler modes** replace phase-specific logic
3. **Review gates** are first-class workflow targets
4. **Single runner** (`WorkflowRunner`) replaces multiple phase functions
5. **LLM profiles** are explicitly configured, not implicitly tied to phases

**Migration Steps:**

1. Add `doc_type` and `workflow:order` metadata to templates
2. Configure handlers in `config/handler_registry.yaml`
3. Use `WorkflowRunner` instead of `run_phase()`
4. Update CLI calls to use new flags (`--max-steps`, `--validate`, etc.)

**Backward Compatibility:**

- Legacy documents without metadata markers still work (use `DEFAULT_DOC_TYPE` fallback)
- Old phase-based logic exists but is deprecated
- Add metadata markers to existing documents when convenient

## Documentation

- **[Architecture Guide](docs/architecture.md)**: Core concepts, component interactions, data flow
- **[Handler Registry Guide](docs/handler-registry-guide.md)**: Configuration schema, handler modes, adding new sections/doc types
- **[LLM Profiles Guide](docs/llm-profiles-guide.md)**: Profile structure, adding new profiles, best practices
- **[Contributing Guide](contributing.md)**: Development workflow, testing guidelines

## Project Structure

```
orchestrator-agent/
├── config/
│   └── handler_registry.yaml       # Section handler configurations
├── docs/
│   ├── architecture.md             # Architecture documentation
│   ├── handler-registry-guide.md   # Handler registry guide
│   ├── llm-profiles-guide.md       # LLM profiles guide
│   ├── templates/
│   │   └── requirements-template.md # Requirements document template
│   └── requirements.md              # Example requirements document
├── profiles/
│   ├── base_policy.md              # Base LLM policy (always injected)
│   ├── requirements.md             # Requirements document LLM profile
│   └── requirements_review.md      # Requirements review LLM profile
├── tools/
│   └── requirements_automation/
│       ├── cli.py                  # Command-line interface
│       ├── runner_v2.py            # WorkflowRunner implementation
│       ├── handler_registry.py     # Handler registry loader
│       ├── profile_loader.py       # LLM profile loader
│       ├── parsing.py              # Document parsing utilities
│       ├── document_validator.py   # Completion validation
│       └── structural_validator.py # Structure validation
├── test-scripts/
│   ├── test_integration.py         # Integration tests
│   ├── test_e2e_prior_context.py   # End-to-end tests
│   ├── test_cli_*.py               # CLI tests
│   └── validate_*.py               # Validation tests
└── test-archive/
    ├── ARCHIVE_README.md           # Archive documentation
    └── *.py                        # Archived unit tests
```

## Development

### Running Tests

The project maintains integration and validation tests in `test-scripts/`. Archived unit tests can be found in `test-archive/`.

```bash
# Run integration tests
python test-scripts/test_integration.py
python test-scripts/test_e2e_prior_context.py

# Run CLI tests
python test-scripts/test_cli_template_creation.py
python test-scripts/test_cli_validate.py

# Validate acceptance criteria
python test-scripts/validate_acceptance_criteria.py
python test-scripts/validate_prior_context_acceptance_criteria.py
python test-scripts/validate_review_gate_acceptance_criteria.py
python test-scripts/validate_structural_validation_acceptance_criteria.py
```

See `test-archive/ARCHIVE_README.md` for information about archived unit tests.

### Adding a New Document Type

1. Create a new template with `doc_type` metadata
2. Add handler configurations to `config/handler_registry.yaml`
3. Create an LLM profile in `profiles/`
4. Update `SUPPORTED_DOC_TYPES` in `config.py`

See [Handler Registry Guide](docs/handler-registry-guide.md) for step-by-step instructions.

### Adding a New Section Type

1. Add section to template with `<!-- section:section_id -->` marker
2. Add to `<!-- workflow:order -->` manifest
3. Configure handler in `config/handler_registry.yaml`

See [Handler Registry Guide](docs/handler-registry-guide.md) for examples.

## License

[Specify your license here]

## Contributing

See [contributing.md](contributing.md) for development guidelines and architecture details.
