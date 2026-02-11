# Orchestrator Agent Architecture Overview

This document provides a comprehensive overview of the Orchestrator Agent architecture, including system design, core concepts, component interactions, and operational constraints.

## Table of Contents

1. [System Purpose & Design Philosophy](#system-purpose--design-philosophy)
2. [Core Concepts](#core-concepts)
3. [Workflow Execution Model](#workflow-execution-model)
4. [Document Structure & Enforcement](#document-structure--enforcement)
5. [Processing Pipeline](#processing-pipeline)
6. [Component Architecture](#component-architecture)
7. [Data Flow & Processing](#data-flow--processing)
8. [Git Integration & Persistence](#git-integration--persistence)
9. [Extension Points](#extension-points)
10. [Execution Guarantees & Constraints](#execution-guarantees--constraints)
11. [CLI Reference](#cli-reference)
12. [Design Rationale](#design-rationale)

---

## System Purpose & Design Philosophy

The Orchestrator Agent is a document-driven workflow automation system for creating and maintaining requirements documents through LLM-powered interactive workflows. The system processes structured markdown documents by iteratively gathering information through question-and-answer cycles and integrating responses via LLM reasoning.

### Design Principles

1. **Configuration over Code**: Behavior defined in YAML/markdown, not Python
2. **Document-Driven**: Templates declare workflow order, not hardcoded logic
3. **Single Responsibility**: Components have clear, focused purposes
4. **Extensibility**: New document types and sections without engine changes
5. **Transparency**: Processing steps are visible and auditable
6. **Safety**: Changes are atomic with backups and git integration

### Explicit Non-Goals

The following are NOT supported by the system and should not be implemented without explicit design review:

- Autonomous approvals or sign-offs
- Code generation or execution
- Repo-wide changes or multi-file modifications
- Version tracking or semantic versioning
- Role-based access control or permission enforcement
- Real-time collaboration or multi-user editing
- Custom markdown extensions or preprocessing

---

## Core Concepts

### Document-Driven Workflow

**Problem**: Traditional workflow engines hardcode processing sequences in application code, making it difficult to add new document types or change workflow order without code modifications.

**Solution**: The workflow order is declared in the document template itself using metadata markers. The engine reads and executes the declared sequence.

**Example**:

```markdown
<!-- workflow:order
problem_statement
goals_objectives
stakeholders_users
review_gate:coherence_check
approval_record
-->
```

**Benefits**:
- **No Code Changes**: Add new document types by creating templates
- **Flexible Ordering**: Different doc types can have different workflows
- **Explicit Dependencies**: Workflow order is visible in the template
- **Version Control**: Workflow changes are tracked with templates

**How It Works**:

1. CLI reads document and extracts `workflow:order` metadata
2. `WorkflowRunner` receives workflow order as a parameter
3. Runner iterates through workflow order, processing each target sequentially
4. Special targets (like `review_gate:*`) are recognized and handled differently

### Handler Registry

**Problem**: Section-specific processing logic was scattered across multiple phase functions, making it hard to understand or customize behavior for specific sections.

**Solution**: A centralized YAML configuration file maps `(doc_type, section_id)` → processing configuration. All section behaviors are declared in one place.

**Schema**:

```yaml
requirements:                    # doc_type
  problem_statement:             # section_id
    mode: integrate_then_questions
    output_format: prose
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: requirements
    auto_apply_patches: never
    scope: current_section
```

**Handler Modes**:

1. **`integrate_then_questions`** (Default)
   - If section has answered questions → integrate answers via LLM
   - If section still blank after integration → generate new questions
   - If section has open questions but no answers → skip (blocked)
   - **Use when**: Iterative refinement needed

2. **`questions_then_integrate`** (Single-Pass)
   - If section blank and no questions → generate questions
   - If section has answered questions → integrate answers
   - Never generate questions after integration
   - **Use when**: Single-pass workflow desired

3. **`review_gate`** (Quality Assurance)
   - LLM reviews specified scope (prior sections or current)
   - Returns pass/fail + optional patches
   - No direct document mutation
   - **Use when**: Quality checkpoint needed

**Output Formats**:

- **`prose`**: Flowing paragraphs (default)
- **`bullets`**: Dash-prefixed lists
- **`subsections`**: Organized under `###` headers

**Scope Values**:

- **`current_section`**: Process/review only the current section
- **`all_prior_sections`**: Review all sections before this gate (for review_gate mode)

See the [Handler Registry Guide](../developer/handler-registry-guide.md) for complete configuration details.

### Unified Processing Loop

**Problem**: Legacy phase-based system had separate functions for each phase, leading to code duplication and inconsistent behavior.

**Solution**: A single `WorkflowRunner.run_once()` method processes all section types. Handler configuration determines the behavior for each section.

**Benefits**:
- **Single Code Path**: All sections use the same processing logic
- **Consistent Behavior**: No phase-specific edge cases
- **Easier Testing**: One function to test, not multiple phase functions
- **Simpler Maintenance**: Changes apply to all sections uniformly

**Processing Steps**:

1. Choose next target from workflow order
2. Load handler configuration for `(doc_type, section_id)`
3. Check section completion status
4. Execute handler mode (integrate, questions, or review)
5. Sanitize and validate LLM output
6. Update document in-memory
7. Return result (updated/blocked/no-op)

### LLM Profiles

**Problem**: LLM prompts were embedded in code, making it difficult to adjust reasoning rules without code changes.

**Solution**: Profiles are separate markdown files that define reasoning rules. Profiles are composed at runtime.

**Profile Types**:

1. **Base Policy** (`tools/profiles/base_policy.md`): Always injected, defines core rules
2. **Task Style Profiles** (`tools/profiles/requirements.md`, etc.): Document-type-specific guidance

**Composition**:

```python
full_prompt = base_policy + task_style_profile + section_context + instruction
```

**Benefits**:
- **No Code Changes**: Update reasoning rules by editing markdown
- **Reusability**: Same profile used across all sections of a doc type
- **Transparency**: Reasoning rules are explicit and version-controlled
- **Testing**: Profiles can be tested independently

See the [LLM Profiles Guide](../developer/llm-profiles-guide.md) for profile structure and best practices.

### Review Gates

**Problem**: No systematic way to ensure quality before proceeding to later sections.

**Solution**: Special workflow targets that review prior sections using LLM reasoning.

**Example**:

```markdown
<!-- section:review_gate:coherence_check -->
## Review Gate: Coherence Check
```

**Handler Configuration**:

```yaml
review_gate:coherence_check:
  mode: review_gate
  scope: all_prior_sections
  llm_profile: requirements_review
```

**Behavior**:

1. LLM reviews all sections in scope
2. Returns pass/fail + review comments
3. Optionally provides patch suggestions
4. Gate remains blocked until issues resolved or user overrides

**Use Cases**:
- Coherence checking (do sections align?)
- Completeness validation (all requirements present?)
- Quality assurance (meets standards?)

---

## Workflow Execution Model

### Phased Workflow

The system processes requirements documents in sequential phases:

- **Phase 1 (Intent & Scope)**: problem_statement, goals_objectives, stakeholders_users, success_criteria
- **Phase 2 (Assumptions & Constraints)**: assumptions, constraints
- **Future Phases**: Phase 3+ (Requirements Details, Interfaces, Data, Risks, Approval Record) - placeholders only

Phases must complete sequentially; Phase 2 only runs after Phase 1 is complete.

### Phase 1: Intent & Scope

**Sections**: problem_statement, goals_objectives, stakeholders_users, success_criteria

**Behavior**:
- If section is locked (`lock=true`): Skip processing
- If section is blank and has no open questions: Generate clarifying questions
- If section is blank and has open questions: Wait for answers
- If section has answered questions: Integrate answers into section via LLM, mark questions resolved
- After integration, check if section is still blank; if so, generate follow-up questions

**Subsection Support**: Phase 1 sections may contain subsections (e.g., primary_goals, secondary_goals). Answers can target subsections; integrations honor subsection boundaries.

### Phase 2: Assumptions & Constraints

**Sections**: assumptions, constraints

**Behavior**:
- Validate both sections have markers before proceeding (error if missing)
- If section is locked: Skip processing
- If section has answered questions: Integrate answers, mark resolved
- If section is blank and has no unanswered questions: Generate clarifying questions
- If section is blank and has unanswered questions: Wait for answers

**No Subsections**: Phase 2 sections do not support subsection targeting (questions target the section ID directly).

### Deterministic Operation

Given the same document state and inputs, the script produces deterministic results. No probabilistic edits occur outside of LLM-generated section content.

### Single-Document Scope

The system modifies only the target document (e.g., `docs/requirements.md`). No other repository files are created, modified, or deleted by automation. Backup files are stored outside the git repository (system temp directory).

### Safe File Operations

- Before writing changes, a backup copy is created in the system temp directory
- Documents are read entirely into memory before processing
- All modifications are made in-memory; disk writes are atomic
- Either all changes for a phase are applied, or none are (no partial writes)

---

## Document Structure & Enforcement

### Section Markers

Sections are identified by `<!-- section:<section_id> -->` markers.

**Rules**:
- Section markers are immutable during processing; never deleted, moved, or modified
- Sections are scoped from marker to marker (or end of document if last section)
- Missing section markers for required sections cause processing to halt with an error

**Example**:

```markdown
<!-- section:problem_statement -->
## Problem Statement

[Content goes here]

<!-- section:goals_objectives -->
## Goals and Objectives

[Content goes here]
```

### Section Headers

Sections may contain markdown headers (`##` or `###`); these are preserved during rewrites. Only the body content (excluding markers, headers, locks, dividers) is replaced during integration.

### Section Locking

Sections marked with `<!-- section_lock:<section_id> lock=true -->` are never modified.

**Rules**:
- The lock marker itself is preserved; only body content would be replaced if lock were false
- The most recent lock marker in a section determines its lock state
- Locked sections are skipped during workflow processing

**Example**:

```markdown
<!-- section:problem_statement -->
<!-- section_lock:problem_statement lock=true -->
## Problem Statement

This content is locked and will not be modified by automation.
```

### Placeholder Token

Blank sections contain `<!-- PLACEHOLDER -->` to indicate they need content.

**Rules**:
- The placeholder is removed when real content is written
- A section with a placeholder token is considered "blank" for workflow purposes

### Section Dividers

Sections may have a trailing divider line (`---`); dividers are preserved during rewrites.

---

## Processing Pipeline

### Open Questions Management

#### Table Schema

The Open Questions table has a fixed schema:

| Question ID | Question | Date | Answer | Section Target | Resolution Status |

**Rules**:
- Table location is identified by `<!-- table:open_questions -->` marker
- The table header and separator rows are validated on each run; mismatches cause errors
- Table structure must be preserved exactly as specified

#### Question Generation

When a blank section has no open questions, the LLM is prompted to generate clarifying questions.

**Generated Question Format**:
- Question text
- Target section ID (may differ from current section)
- Rationale

**Constraints**:
- Phase 1: Generated questions are constrained to Phase 1 section IDs only
- Phase 2: Generated questions can target Phase 2 section IDs

#### Question Deduplication

New questions are compared against existing questions using normalized text (case/space-insensitive) + section target. Duplicate questions are not inserted.

#### Question Insertion

- New questions are assigned sequential IDs (Q-001, Q-002, ... based on highest existing ID)
- Questions are inserted with default status "Open" and empty answer field
- Questions are added to the table end (before trailing divider, if present)

#### Question Resolution

After LLM integrates answers into a section, the corresponding questions are marked "Resolved" in the table.

**Resolution Criteria**:
- Questions must have a non-empty Answer field
- Questions must have status "Open" or "Deferred"
- Questions with status "Pending", empty answer, or "-" are not considered answered

#### Question Status Values

- **Open**: Question is awaiting an answer
- **Deferred**: Question is acknowledged but intentionally deferred
- **Resolved**: Question has been answered and integrated into requirements

**Phase-Specific Requirements**:
- Phase 1: Only requires Open questions to be resolved
- Phase 2: Requires both Open and Deferred questions to be resolved

### LLM Integration

#### Model Configuration

- Uses Claude (Sonnet 4.5) by default for question generation and answer integration
- Model and max token limits are configurable in config.py
- Requires ANTHROPIC_API_KEY environment variable to be set

#### Question Generation Prompts

- LLM is prompted with section context (current body text) and asked to generate clarifying questions
- Prompts are constrained to ensure JSON output with expected keys: question, section_target, rationale
- LLM output is parsed for JSON; if JSON is not extracted, generation fails

#### Answer Integration Prompts

- LLM is provided the current section text and a list of answered questions
- LLM is prompted to rewrite the section incorporating answers in requirements-style language
- LLM is instructed to: keep language crisp, remove placeholder wording, flag conflicts rather than guess
- Output is treated as untrusted; any remaining markers or improper structure are removed

#### Sanitization of LLM Output

LLM output is sanitized before insertion into the document.

**General Sanitization**:
- Removes: accidental markers (section, lock, table), comments, markdown headers, empty lines beyond singles

**Section-Specific Rules**:
- **assumptions**: Removes constraint classification lines; deduplicates similar assumptions
- **constraints**: Preserves only "### Technical/Operational/Resource Constraints" subsection headers

---

## Component Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                             CLI                              │
│                  (cli.py - Entry Point)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      WorkflowRunner                          │
│              (runner_v2.py - Orchestration)                  │
│                                                              │
│  • Reads workflow order from document                        │
│  • Iterates through targets sequentially                     │
│  • Loads handler config for each section                     │
│  • Executes handler mode (integrate/questions/review)        │
│  • Sanitizes and validates LLM output                        │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ↓          ↓          ↓          ↓          ↓
┌──────┐  ┌────────┐ ┌────────┐ ┌──────┐  ┌──────────┐
│Handler│  │Profile │ │LLMClient│ │Parsing│ │Validators│
│Registry│ │Loader  │ │         │ │       │ │          │
└──────┘  └────────┘ └────────┘ └──────┘  └──────────┘
```

### CLI (cli.py)

**Responsibilities**:
- Parse command-line arguments
- Load and validate configuration files
- Bootstrap document from template if needed
- Invoke WorkflowRunner with appropriate parameters
- Handle git operations (commit/push)
- Format and return results

**Key Functions**:
- `main()`: Entry point, orchestrates CLI flow
- `bootstrap_document()`: Create document from template
- `validate_structure()`: Check document structure
- `validate_completion()`: Check workflow completion

### WorkflowRunner (runner_v2.py)

**Responsibilities**:
- Main workflow orchestration
- Section processing for all handler modes
- LLM call coordination
- Output sanitization and validation
- State management (track completed sections)

**Key Methods**:
- `run_once()`: Execute one workflow step
- `_execute_integrate_then_questions()`: Handle integration mode
- `_execute_questions_then_integrate()`: Handle questions mode
- `_execute_review_gate()`: Handle review gate mode
- `_integrate_answers()`: Integrate answered questions via LLM
- `_generate_questions()`: Generate new questions via LLM
- `_sanitize_llm_output()`: Clean LLM output before insertion

### HandlerRegistry (handler_registry.py)

**Responsibilities**:
- Load handler configurations from YAML
- Validate configuration schema
- Provide handler lookup by (doc_type, section_id)
- Apply defaults for missing fields

**Key Methods**:
- `load()`: Load registry from YAML file
- `get_handler()`: Retrieve handler config for section
- `validate()`: Check configuration validity

### ProfileLoader (profile_loader.py)

**Responsibilities**:
- Load LLM profiles from markdown files
- Compose profiles (base policy + task style)
- Cache loaded profiles for performance

**Key Methods**:
- `load_profile()`: Load and compose profile
- `get_base_policy()`: Get base policy content
- `get_task_style()`: Get task-specific profile

### LLMClient (llm.py)

**Responsibilities**:
- Wrap OpenAI/Anthropic API calls
- Handle retry logic and error handling
- Format prompts and parse responses
- Track token usage and costs

**Key Methods**:
- `generate()`: Make LLM generation call
- `parse_json_response()`: Extract JSON from LLM output
- `estimate_tokens()`: Estimate token count for prompt

### Parsing (parsing.py)

**Responsibilities**:
- Parse document structure (sections, markers, metadata)
- Extract workflow order and doc_type
- Parse open questions table
- Handle subsection detection

**Key Functions**:
- `parse_sections()`: Extract all sections from document
- `parse_workflow_order()`: Get workflow order from metadata
- `parse_questions_table()`: Parse open questions table
- `extract_metadata()`: Extract doc_type and other metadata

### Validators

#### DocumentValidator (document_validator.py)

**Responsibilities**:
- Validate workflow completion
- Check section completion status
- Enforce phase prerequisites

**Key Methods**:
- `validate_completion()`: Check if document is complete
- `is_section_complete()`: Check if section has content
- `check_prerequisites()`: Verify phase dependencies

#### StructuralValidator (structural_validator.py)

**Responsibilities**:
- Validate document structure
- Check marker syntax
- Validate table schema
- Detect corruption or malformation

**Key Methods**:
- `validate_all()`: Run all structural checks
- `validate_markers()`: Check section markers
- `validate_tables()`: Check table structure
- `validate_metadata()`: Check metadata syntax

---

## Data Flow & Processing

### Document Processing Flow

```
1. CLI reads document and template
           ↓
2. Extract metadata (doc_type, workflow:order)
           ↓
3. Validate document structure
           ↓
4. Initialize WorkflowRunner with:
   - Document lines
   - LLMClient
   - doc_type
   - workflow_order
   - HandlerRegistry
           ↓
5. WorkflowRunner.run_once():
   a. Find next incomplete target in workflow_order
   b. Load handler config for (doc_type, target)
   c. Check if section is locked or complete
   d. Execute handler mode:
      - integrate_then_questions: integrate → check → questions
      - questions_then_integrate: questions → integrate
      - review_gate: review prior sections
   e. Sanitize LLM output
   f. Update document lines in-memory
           ↓
6. CLI writes updated document to disk
           ↓
7. CLI commits and pushes changes (if enabled)
```

### LLM Call Flow

```
1. WorkflowRunner determines LLM operation needed:
   - Generate questions
   - Integrate answers
   - Review sections
           ↓
2. Load LLM profile via ProfileLoader:
   - Load base_policy.md
   - Load task-specific profile (e.g., requirements.md)
   - Compose: base + task + context
           ↓
3. Format prompt with:
   - Profile rules
   - Section context
   - Specific instruction (generate/integrate/review)
           ↓
4. LLMClient.generate():
   - Add system prompt from profile
   - Add user prompt with context
   - Call OpenAI/Anthropic API
   - Parse response
   - Extract JSON if needed
           ↓
5. Return to WorkflowRunner:
   - Questions: List of {question, section_target, rationale}
   - Integration: New section content
   - Review: {status, comments, patches}
           ↓
6. Sanitize output:
   - Remove markers and comments
   - Apply section-specific sanitization
   - Validate structure
           ↓
7. Insert into document:
   - Update section content
   - Mark questions resolved
   - Update review gate status
```

---

## Git Integration & Persistence

### Pre-Flight Check

Before processing, the system checks if the git working tree is clean.

**Rules**:
- If uncommitted changes exist and `--no-commit` is not set, processing halts with an error
- `--no-commit` flag allows processing without requiring a clean tree
- Ensures safety by preventing accidental loss of uncommitted work

### Commit & Push

After processing, if changes were made and `--dry-run` is not set:

1. Changes are committed with message: `"requirements: automation pass (<phase>)"`
2. Only the target document is committed; unexpected modified files will stop the commit
3. Changes are pushed to origin if commit succeeds

**Safety Checks**:
- Verify only expected files are modified
- Halt if unexpected changes detected
- Provide clear error messages

### Backup Files

Before writing updates, a backup copy is created in the system temp directory.

**Backup Strategy**:
- Location: `/tmp/requirements_automation_backups/` (or equivalent temp directory)
- Filename format: `requirements.md.<YYYYMMDD_HHMMSS>.bak`
- Backup files are not deleted by the system; they accumulate over time
- Provides manual recovery option if needed

---

## Extension Points

### Adding a New Document Type

**Steps**:

1. **Create Template**:
   ```markdown
   <!-- doc_type:research -->
   <!-- workflow:order
   research_question
   methodology
   findings
   -->
   ```

2. **Add Handler Configuration**:
   ```yaml
   research:
     research_question:
       mode: integrate_then_questions
       output_format: prose
       llm_profile: research
   ```

3. **Create LLM Profile**:
   ```markdown
   # Research Document Profile
   
   You are helping create a research document...
   ```

4. **Update Configuration**:
   ```python
   # config.py
   SUPPORTED_DOC_TYPES = ["requirements", "research"]
   ```

5. **Test**:
   ```bash
   python -m tools.requirements_automation.cli \
     --template docs/templates/research-template.md \
     --doc docs/research.md \
     --repo-root . \
     --dry-run
   ```

See the [Handler Registry Guide](../developer/handler-registry-guide.md) for detailed instructions.

### Adding a New Section Type

**Steps**:

1. **Add Section Marker to Template**:
   ```markdown
   <!-- section:new_section_id -->
   ## New Section
   
   <!-- PLACEHOLDER -->
   ```

2. **Add to Workflow Order**:
   ```markdown
   <!-- workflow:order
   problem_statement
   new_section_id
   goals_objectives
   -->
   ```

3. **Configure Handler**:
   ```yaml
   requirements:
     new_section_id:
       mode: integrate_then_questions
       output_format: prose
       llm_profile: requirements
   ```

4. **Test**:
   ```bash
   python -m tools.requirements_automation.cli \
     --template docs/templates/requirements-template.md \
     --doc docs/test-requirements.md \
     --repo-root . \
     --dry-run
   ```

### Adding a New Handler Mode

**Steps**:

1. **Update Models**:
   ```python
   # models.py
   class HandlerConfig:
       mode: Literal["integrate_then_questions", "questions_then_integrate", 
                     "review_gate", "generate_only"]
   ```

2. **Add Handler Method**:
   ```python
   # runner_v2.py
   def _execute_generate_only(self, section_id: str, 
                              handler_config: HandlerConfig) -> RunResult:
       """Execute generate_only mode."""
       # Implementation
   ```

3. **Update run_once()**:
   ```python
   elif handler_config.mode == "generate_only":
       result = self._execute_generate_only(target, handler_config)
   ```

4. **Document and Test**

### Adding a New LLM Profile

**Steps**:

1. **Create Profile File**:
   ```bash
   # tools/profiles/research.md
   ```

2. **Write Clear Rules**:
   ```markdown
   # Research Document Profile
   
   ## Core Principles
   - Evidence-based reasoning
   - Cite sources explicitly
   - Distinguish facts from interpretations
   
   ## Output Format
   - Use academic tone
   - Structure findings clearly
   - Highlight limitations
   ```

3. **Reference in Handler Config**:
   ```yaml
   research:
     findings:
       llm_profile: research
   ```

4. **Test with Real Documents**

See the [LLM Profiles Guide](../developer/llm-profiles-guide.md) for detailed instructions.

### Adding Validation Rules

**Steps**:

1. **Update Validator**:
   ```python
   # structural_validator.py
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
       errors.extend(self.validate_new_rule())
       return errors
   ```

3. **Test and Document**

### Adding Sanitization Rules

**Steps**:

1. **Update Sanitizer**:
   ```python
   # sanitize.py
   def sanitize_section_specific(content: str, section_id: str) -> str:
       if section_id == "new_section":
           # Apply section-specific sanitization
           content = remove_unwanted_patterns(content)
       return content
   ```

2. **Test and Document**

---

## Execution Guarantees & Constraints

### No Partial Writes

Either all changes for a workflow step are applied, or none are.

**Rules**:
- If an error occurs mid-processing, the on-disk document is not modified
- All changes are made in-memory before writing
- Disk writes are atomic

### No Side Effects

Processing does not modify or create files outside of:
- Backup copies (created in temp directory)
- Git repository state (commits only target document)

**Rules**:
- No creation of log files in repository
- No modification of configuration files
- No changes to other documents

### Idempotency

Running the same workflow step twice on an unchanged document produces the same result.

**Caveats**:
- If document changes between runs, the step may produce different results (e.g., if questions were answered)
- LLM output may vary slightly due to non-determinism in generation

### Open Implementation Gaps

The following exist in the system but are incomplete or aspirational:

- **Phase 3+ (Requirements Details)**: Placeholder only; not implemented
- **Phase 4+ (Interfaces, Data, Risks)**: Placeholder only; not implemented
- **Phase 5+ (Approval Record)**: Placeholder only; not implemented
- **Version tracking**: Not implemented; no version history or increment logic in code
- **Multi-section processing per run**: Current design processes one phase per run (though `--max-steps` allows multiple steps)

---

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
- `--handler-config PATH`: Custom handler registry YAML (default: `tools/config/handler_registry.yaml`)
- `--validate`: Validate document completion without processing
- `--strict`: Enable strict completion checking (includes optional sections)
- `--validate-structure`: Check document structure without processing

### Exit Codes

- `0`: Success (workflow progressed or is complete)
- `1`: Blocked (waiting for user input or validation failed)
- `2`: Error (invalid configuration, corrupted document, etc.)

### Output Format

Exit code determines status. JSON result printed to stdout with keys:
- `outcome`: "updated" | "blocked" | "no-op" | "error"
- `changed`: boolean
- `blocked_reasons`: list of reasons if blocked

**Example**:

```json
{
  "outcome": "blocked",
  "changed": false,
  "blocked_reasons": ["waiting for answers to open questions in section: problem_statement"]
}
```

---

## Design Rationale

### Why Document-Driven Workflows?

**Problem**: Hardcoded workflows require code changes for new document types.

**Solution**: Declare workflow order in templates using metadata markers.

**Benefits**:
- Add new document types without code changes
- Workflow order is explicit and version-controlled
- Different doc types can have different workflows
- Dependencies are visible in template

**Trade-offs**:
- Requires metadata parsing
- Workflow errors only detected at runtime (not compile-time)

**Decision**: Worth the trade-off for flexibility and extensibility.

### Why Handler Registry?

**Problem**: Section-specific logic scattered across multiple phase functions.

**Solution**: Centralized YAML configuration mapping `(doc_type, section_id)` → behavior.

**Benefits**:
- All section behaviors defined in one place
- No code changes for new sections
- Configuration is declarative and reviewable
- Easy to understand section processing at a glance

**Trade-offs**:
- Configuration file can grow large
- Requires YAML parsing and validation
- Behavior not discoverable from code alone

**Decision**: Worth the trade-off for maintainability and extensibility.

### Why LLM Profiles?

**Problem**: Prompts embedded in code make it hard to adjust reasoning rules.

**Solution**: Profiles are separate markdown files composed at runtime.

**Benefits**:
- Update reasoning without code changes
- Profiles are explicit and version-controlled
- Same profile reused across all sections
- Easy to test and iterate on prompts

**Trade-offs**:
- Profile changes affect all sections using that profile
- Reasoning rules not co-located with code
- Requires profile loading infrastructure

**Decision**: Worth the trade-off for transparency and iteration speed.

### Why Review Gates?

**Problem**: No systematic quality assurance before proceeding to later sections.

**Solution**: Special workflow targets that review prior sections using LLM.

**Benefits**:
- Catch issues early before propagating
- Explicit quality checkpoints in workflow
- LLM-powered suggestions for improvements
- Optional patch application

**Trade-offs**:
- Adds processing time
- May block workflow if review fails
- Requires separate review profile

**Decision**: Worth the trade-off for quality assurance.

### Why Single Processing Loop?

**Problem**: Legacy phase-based system had duplicate logic across phase functions.

**Solution**: Single `run_once()` method processes all section types via handler config.

**Benefits**:
- No code duplication
- Consistent behavior across all sections
- Easier to test and maintain
- Clearer code structure

**Trade-offs**:
- Handler config must be comprehensive
- Edge cases must be handled generically
- May be less intuitive than separate functions

**Decision**: Worth the trade-off for code quality and maintainability.

---

## Summary

The Orchestrator Agent architecture is built around five core principles:

1. **Configuration over Code**: Define behavior in YAML/markdown, not Python
2. **Document-Driven**: Templates declare workflow order
3. **Single Responsibility**: Each component has a focused purpose
4. **Extensibility**: Add document types and sections without engine changes
5. **Transparency**: Processing is visible, auditable, and version-controlled

The system prioritizes:
- **Safety**: Atomic operations, backups, git integration
- **Flexibility**: Handler registry and profiles enable customization
- **Maintainability**: Single processing loop, clear component boundaries
- **Quality**: Review gates and validation at multiple levels

For detailed implementation guidance, see:
- [Handler Registry Guide](../developer/handler-registry-guide.md)
- [LLM Profiles Guide](../developer/llm-profiles-guide.md)
- [Contributing Guide](../developer/contributing.md)

---

*This document consolidates information from the original architecture.md and system-capabilities.md files to provide a comprehensive architectural overview.*
