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

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

#### Create a New Requirements Document

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

#### Process Multiple Steps at Once

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --max-steps 5
```

Processes up to 5 workflow steps in a single run, stopping if blocked.

#### Validate Document Completion

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --validate
```

Checks if all required sections are complete without processing. Returns JSON status.

For more usage examples and detailed CLI reference, see the [Architecture Overview](docs/architecture/overview.md#cli-reference).

## Documentation

### For Users

- **[Quick Start Guide](docs/architecture/overview.md#quick-start)** - Get started quickly with common workflows
- **[CLI Reference](docs/architecture/overview.md#cli-reference)** - Complete command-line interface documentation

### For Developers

- **[Architecture Overview](docs/architecture/overview.md)** - Comprehensive system design and core concepts
- **[Contributing Guide](docs/developer/contributing.md)** - Development workflow and coding guidelines
- **[Handler Registry Guide](docs/developer/handler-registry-guide.md)** - Configure section behaviors and add new document types
- **[LLM Profiles Guide](docs/developer/llm-profiles-guide.md)** - Create and customize LLM reasoning profiles

### Additional Resources

- **[Implementation Notes](docs/developer/implementation-notes.md)** - Technical implementation details
- **[Test Specifications](docs/developer/test-spec.md)** - Testing guidelines and acceptance criteria

## Project Structure

```
orchestrator-agent/
├── config/
│   └── handler_registry.yaml       # Section handler configurations
├── docs/
│   ├── architecture/
│   │   └── overview.md             # Complete architecture documentation
│   ├── developer/
│   │   ├── contributing.md         # Development guidelines
│   │   ├── handler-registry-guide.md
│   │   └── llm-profiles-guide.md
│   ├── templates/
│   │   └── requirements-template.md
│   └── requirements.md             # Example requirements document
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
│       └── ...                     # Additional modules
└── test-scripts/
    ├── test_integration.py         # Integration tests
    └── ...                         # Additional tests
```

## Core Concepts

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

See the [Handler Registry Guide](docs/developer/handler-registry-guide.md) for details.

### LLM Profiles

Profiles define LLM reasoning rules:

- **Base Policy** (`profiles/base_policy.md`): Always injected, defines core rules
- **Task Style Profiles** (`profiles/requirements.md`, etc.): Document-type-specific guidance

See the [LLM Profiles Guide](docs/developer/llm-profiles-guide.md) for details.

## Development

### Running Tests

```bash
# Run integration tests
python test-scripts/test_integration.py
python test-scripts/test_e2e_prior_context.py

# Run CLI tests
python test-scripts/test_cli_template_creation.py
python test-scripts/test_cli_validate.py

# Validate acceptance criteria
python test-scripts/validate_acceptance_criteria.py
```

See the [Contributing Guide](docs/developer/contributing.md) for detailed development guidelines.

### Adding Extensions

- **New Document Type**: See [Handler Registry Guide](docs/developer/handler-registry-guide.md#adding-a-new-document-type)
- **New Section Type**: See [Handler Registry Guide](docs/developer/handler-registry-guide.md#adding-a-new-section-type)
- **New LLM Profile**: See [LLM Profiles Guide](docs/developer/llm-profiles-guide.md#adding-new-profiles)

## License

[Specify your license here]

## Contributing

Contributions are welcome! Please see the [Contributing Guide](docs/developer/contributing.md) for details on:
- Development setup
- Code style guidelines
- Testing requirements
- Pull request process
