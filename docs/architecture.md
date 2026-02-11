# Architecture Guide

This document provides a comprehensive overview of the Orchestrator Agent architecture, core concepts, component interactions, and extension points.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Extension Points](#extension-points)
5. [Design Rationale](#design-rationale)

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

**Benefits**:
- **Centralized Configuration**: All section behaviors in one file
- **No Code Changes**: Modify behavior by editing YAML
- **Consistency**: Same configuration schema across all sections
- **Discoverability**: New developers can understand behavior by reading config

### Unified Processing Loop

**Problem**: Old phase-based system had separate code paths for each phase, leading to duplication and inconsistency.

**Solution**: Single `WorkflowRunner` class with one processing loop configured by handler registry.

**Processing Steps**:

```
1. Choose Next Target
   ↓
2. Load Handler Config (doc_type, section_id) → HandlerConfig
   ↓
3. Execute Handler Mode
   ├─ integrate_then_questions: Integrate → Generate Questions
   ├─ questions_then_integrate: Generate Questions → Integrate
   └─ review_gate: Review → Return Issues/Patches
   ↓
4. Sanitize Output
   ├─ Remove duplicate lines (if dedupe=true)
   ├─ Remove specified markers (sanitize_remove)
   └─ Preserve headers (preserve_headers)
   ↓
5. Validate Output
   ├─ Check structure integrity
   └─ Verify section boundaries
   ↓
6. Update Document
   ↓
7. Return Result (changed, blocked, reasons)
```

**Key Code**:

```python
class WorkflowRunner:
    def run_once(self, dry_run: bool) -> RunResult:
        target = self._choose_next_target()
        handler_config = self.handler_registry.get_handler(self.doc_type, target)
        
        if handler_config.mode == "review_gate":
            result = self._execute_review_gate(target, handler_config)
        elif handler_config.mode == "integrate_then_questions":
            result = self._execute_integrate_then_questions(target, handler_config)
        elif handler_config.mode == "questions_then_integrate":
            result = self._execute_questions_then_integrate(target, handler_config)
        
        return result
```

**Benefits**:
- **Single Code Path**: All sections processed the same way
- **Consistent Behavior**: Same validation, sanitization for all sections
- **Easier Testing**: Test one loop with different configurations
- **Maintainability**: Changes to processing logic apply everywhere

### LLM Profiles

**Problem**: LLM behavior needs to be guided with rules and constraints, but hardcoding prompts in code makes them hard to maintain and version.

**Solution**: Rules-based profiles stored as markdown files, loaded dynamically and injected into LLM calls.

**Profile Structure**:

```
Base Policy (profiles/base_policy.md)
    ↓ Always Injected
    
Task Style Profile (profiles/requirements.md, etc.)
    ↓ Injected based on handler config
    
Task-Specific Instructions (from code)
    ↓ Generated dynamically
    
= Full LLM Prompt
```

**Example**:

```python
from profile_loader import ProfileLoader

loader = ProfileLoader()
profile = loader.load_combined(
    llm_profile="requirements",  # from handler config
    task_instructions="Generate 3-5 questions..."  # from code
)

response = llm.call(profile + context)
```

**Base Policy** (`profiles/base_policy.md`):
- Core rules (never invent facts, output valid JSON, etc.)
- Forbidden actions (don't create section markers, etc.)
- Output format rules (JSON, prose, bullets)
- Reasoning constraints (clarity over cleverness, etc.)

**Task Style Profiles**:
- `requirements.md`: Requirements-specific rules (RFC 2119 keywords, declarative style)
- `requirements_review.md`: Review criteria (completeness, consistency, clarity)

**Benefits**:
- **Version Control**: Track profile changes in git
- **Rapid Iteration**: Modify profiles without code changes
- **Reusable**: Same base policy across all tasks
- **Testable**: A/B test different profile versions

### Review Gates

**Problem**: Need quality assurance checkpoints in workflow without hardcoding review logic.

**Solution**: Review gates are first-class workflow targets configured via handler registry.

**How Review Gates Work**:

1. **Declaration** (in template):
```markdown
<!-- section:review_gate:coherence_check -->
## Review Gate: Coherence Check
```

2. **Configuration** (in handler registry):
```yaml
review_gate:coherence_check:
  mode: review_gate
  output_format: prose
  llm_profile: requirements_review
  auto_apply_patches: never
  scope: all_prior_sections
  validation_rules:
    - no_contradictions
    - no_missing_critical_sections
    - consistent_terminology
```

3. **Execution**:
- LLM reviews specified scope (all prior sections or current section)
- Returns structured result: `{ "pass": bool, "issues": [...], "patches": [...] }`
- Issues are logged and stored in document
- Patches are suggested but not auto-applied (configurable)

4. **Output** (stored in document):
```markdown
<!-- section:review_gate:coherence_check -->
## Review Gate: Coherence Check

**Status**: ❌ Issues Found

**Issues**:
1. Contradiction between section 3.2 and 5.1...
2. Missing critical section: Security Requirements

**Patches Suggested**:
- Patch 1: Clarify constraint in section 3.2
- Patch 2: Add Security Requirements section

<!-- questions:review_gate:coherence_check -->
Q: Should we apply suggested patches automatically?
```

**Benefits**:
- **Configurable**: Quality checks defined in YAML
- **Consistent**: Same review process for all sections
- **Traceable**: Review results stored in document
- **Flexible**: Choose auto-apply vs. manual review

---

## Component Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                        │
│  - Parse arguments                                          │
│  - Load document & template                                 │
│  - Initialize components                                    │
│  - Execute workflow                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  WorkflowRunner (runner_v2.py)              │
│  - Choose next target from workflow order                   │
│  - Load handler configuration                               │
│  - Execute handler mode                                     │
│  - Update document                                          │
└─────────────────┬───────────────────────────────────────────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Handler  │ │ Profile  │ │  LLM Client  │
│ Registry │ │ Loader   │ │  (llm.py)    │
└──────────┘ └──────────┘ └──────────────┘
      │           │              │
      └───────────┴──────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   Document (in memory)                      │
│  - Parsed sections                                          │
│  - Metadata markers                                         │
│  - Question blocks                                          │
└─────────────────────────────────────────────────────────────┘
```

### Component Details

#### CLI (cli.py)

**Responsibilities**:
- Parse command-line arguments
- Load and validate document/template
- Initialize `WorkflowRunner`, `HandlerRegistry`, `LLMClient`
- Execute workflow (single-step or batch)
- Persist changes and commit to git

**Key Functions**:
```python
def main(argv: List[str] | None = None) -> int
```

**Inputs**: Command-line arguments  
**Outputs**: Exit code (0=success, 1=blocked, 2=error)

#### WorkflowRunner (runner_v2.py)

**Responsibilities**:
- Choose next workflow target based on completion status
- Load handler configuration from registry
- Execute handler mode (integrate, generate questions, review)
- Update document sections
- Return result (changed, blocked, reasons)

**Key Methods**:
```python
def run_once(self, dry_run: bool) -> RunResult
def run_until_blocked(self, dry_run: bool, max_steps: int) -> List[RunResult]
def _choose_next_target(self) -> str
def _execute_integrate_then_questions(self, section_id: str, handler_config: HandlerConfig) -> RunResult
def _execute_review_gate(self, gate_id: str, handler_config: HandlerConfig) -> RunResult
```

**State**: Document lines (mutable), workflow order, handler registry

#### HandlerRegistry (handler_registry.py)

**Responsibilities**:
- Load handler configurations from YAML file
- Provide handler config for `(doc_type, section_id)` pairs
- Fall back to `_default` configuration if specific handler not found
- Validate configuration schema

**Key Methods**:
```python
def get_handler(self, doc_type: str, section_id: str) -> HandlerConfig
def supports_doc_type(self, doc_type: str) -> bool
```

**Data**: Dictionary of `{doc_type: {section_id: HandlerConfig}}`

#### ProfileLoader (profile_loader.py)

**Responsibilities**:
- Load base policy and task style profiles from markdown files
- Combine profiles into full LLM prompt
- Cache loaded profiles for performance

**Key Methods**:
```python
def load_base_policy(self) -> str
def load_task_profile(self, profile_name: str) -> str
def load_combined(self, llm_profile: str, task_instructions: str) -> str
```

**Data**: Profile cache, profiles directory path

#### LLMClient (llm.py)

**Responsibilities**:
- Abstract OpenAI API calls
- Inject profiles into prompts
- Handle rate limiting and retries
- Parse structured responses (JSON)

**Key Methods**:
```python
def call(self, prompt: str, **kwargs) -> str
def call_json(self, prompt: str, **kwargs) -> Dict
```

**Configuration**: OpenAI API key, model selection, temperature, etc.

#### Parsing (parsing.py)

**Responsibilities**:
- Extract metadata from documents (doc_type, workflow order, etc.)
- Find and parse section boundaries
- Extract question blocks
- Parse tables

**Key Functions**:
```python
def extract_metadata(lines: List[str]) -> Dict[str, str]
def extract_workflow_order(lines: List[str]) -> List[str]
def find_sections(lines: List[str]) -> List[SectionPointer]
def extract_questions(lines: List[str], section_id: str) -> List[Question]
```

**Data Structures**: `SectionPointer`, `Question`, metadata dicts

#### DocumentValidator (document_validator.py)

**Responsibilities**:
- Validate document completion (all required sections filled)
- Check optional sections (strict mode)
- Generate completion reports

**Key Methods**:
```python
def validate_completion(self, strict: bool = False) -> CompletionStatus
```

**Output**: `CompletionStatus` (complete, missing sections, etc.)

#### StructuralValidator (structural_validator.py)

**Responsibilities**:
- Validate document structure integrity
- Check for malformed section markers
- Verify table structure
- Detect corrupted metadata

**Key Methods**:
```python
def validate_all(self) -> List[ValidationError]
```

**Output**: List of validation errors (empty if valid)

---

## Data Flow

### Document Processing Flow

```
┌──────────────┐
│   Template   │ (defines workflow order, section structure)
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  Parser (parsing.py)                     │
│  - Extract metadata (doc_type)           │
│  - Extract workflow order                │
│  - Find sections                         │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  Validator (structural_validator.py)     │
│  - Check structure integrity             │
│  - Verify section markers                │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  WorkflowRunner (runner_v2.py)           │
│  - Choose next target                    │
│  - Load handler config                   │
│  - Execute handler mode                  │
└──────┬───────────────────────────────────┘
       │
       ├─ Handler Mode: integrate_then_questions ─┐
       │                                          │
       │  ┌───────────────────────────────────────▼───────┐
       │  │  1. Extract answered questions                │
       │  │  2. Load LLM profile                          │
       │  │  3. Call LLM to integrate answers             │
       │  │  4. Update section content                    │
       │  │  5. If still blank, generate new questions    │
       │  └───────────────────────────────────────────────┘
       │
       ├─ Handler Mode: review_gate ──────────────┐
       │                                          │
       │  ┌───────────────────────────────────────▼───────┐
       │  │  1. Gather scope (prior sections)             │
       │  │  2. Load review profile                       │
       │  │  3. Call LLM to review                        │
       │  │  4. Parse structured result                   │
       │  │  5. Store issues/patches in document          │
       │  └───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  Sanitizer (sanitize.py)                 │
│  - Remove duplicates (if dedupe=true)    │
│  - Strip unwanted markers                │
│  - Preserve headers                      │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  Updated Document (in memory)            │
│  - Modified section content              │
│  - New questions (if applicable)         │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  File I/O (utils_io.py)                  │
│  - Backup original                       │
│  - Write updated document                │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  Git (git_utils.py)                      │
│  - Commit changes                        │
│  - Push to remote                        │
└──────────────────────────────────────────┘
```

### LLM Call Flow

```
┌────────────────────────────────────────────────┐
│  WorkflowRunner                                │
│  - Prepare task instructions                   │
│  - Load handler config                         │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│  ProfileLoader                                 │
│  - Load base_policy.md                         │
│  - Load task profile (e.g., requirements.md)   │
│  - Combine: base + task + instructions         │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│  Full LLM Prompt                               │
│                                                │
│  # Base LLM Policy                             │
│  - Core rules                                  │
│  - Forbidden actions                           │
│  - Output format rules                         │
│                                                │
│  ---                                           │
│                                                │
│  # Requirements Task Profile                   │
│  - RFC 2119 keywords                           │
│  - Declarative style                           │
│  - Question generation guidelines              │
│                                                │
│  ---                                           │
│                                                │
│  # Task-Specific Instructions                  │
│  - Integrate these answered questions...       │
│  - Generate 3-5 questions about...             │
│                                                │
│  ---                                           │
│                                                │
│  # Context                                     │
│  - Section content                             │
│  - Answered questions                          │
│  - Related sections                            │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│  LLMClient                                     │
│  - Call OpenAI API                             │
│  - Handle rate limiting                        │
│  - Parse response                              │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│  LLM Response                                  │
│  - Section content (prose, bullets, etc.)      │
│  - OR Questions (JSON array)                   │
│  - OR Review result (JSON object)              │
└────────────────────────────────────────────────┘
```

---

## Extension Points

The architecture is designed for extensibility without requiring core engine changes.

### 1. Adding a New Document Type

**Steps**:

1. **Create Template**:
   ```markdown
   <!-- meta:doc_type value="research" -->
   <!-- workflow:order
   research_questions
   literature_review
   findings
   -->
   ```

2. **Add Handler Configurations**:
   ```yaml
   research:
     research_questions:
       mode: questions_then_integrate
       output_format: bullets
       llm_profile: research
   ```

3. **Create LLM Profile**:
   ```markdown
   # Research Task Profile
   - Focus on evidence-based reasoning
   - Cite sources when available
   - Use academic tone
   ```

4. **Update Config**:
   ```python
   SUPPORTED_DOC_TYPES = ["requirements", "research", "planning"]
   ```

**No changes needed to**: CLI, WorkflowRunner, parsing logic, or validation.

### 2. Adding a New Section Type

**Steps**:

1. **Add to Template**:
   ```markdown
   <!-- section:security_requirements -->
   ## Security Requirements
   ```

2. **Add to Workflow Order**:
   ```markdown
   <!-- workflow:order
   requirements
   security_requirements
   approval_record
   -->
   ```

3. **Configure Handler**:
   ```yaml
   requirements:
     security_requirements:
       mode: integrate_then_questions
       output_format: bullets
       llm_profile: requirements
   ```

**No changes needed to**: CLI, WorkflowRunner, or core processing logic.

### 3. Adding a New Handler Mode

**Example**: Add `generate_only` mode that only generates questions, never integrates.

**Steps**:

1. **Update HandlerConfig**:
   ```python
   class HandlerConfig:
       mode: Literal["integrate_then_questions", "questions_then_integrate", "review_gate", "generate_only"]
   ```

2. **Add Handler Method**:
   ```python
   def _execute_generate_only(self, section_id: str, handler_config: HandlerConfig) -> RunResult:
       # Implementation
   ```

3. **Update run_once()**:
   ```python
   elif handler_config.mode == "generate_only":
       result = self._execute_generate_only(target, handler_config)
   ```

4. **Document Mode** in handler registry YAML comments.

### 4. Adding a New LLM Profile

**Steps**:

1. **Create Profile File**: `profiles/planning.md`
   ```markdown
   # Planning Task Profile
   - Use future tense for planned actions
   - Include estimated effort for tasks
   - Identify dependencies explicitly
   ```

2. **Configure Handler** to use new profile:
   ```yaml
   planning:
     milestones:
       llm_profile: planning
   ```

**No changes needed to**: ProfileLoader (automatically discovers new files).

### 5. Adding Custom Validation Rules

**Example**: Add rule to check for specific section completeness.

**Steps**:

1. **Extend StructuralValidator**:
   ```python
   def validate_required_subsections(self, section_id: str, required_subsections: List[str]) -> List[ValidationError]:
       # Implementation
   ```

2. **Call from validate_all()**:
   ```python
   errors.extend(self.validate_required_subsections("goals_objectives", ["Primary Goals", "Secondary Goals"]))
   ```

3. **Configure in handler registry** (if needed):
   ```yaml
   goals_objectives:
     validation_rules:
       - required_subsections: ["Primary Goals", "Secondary Goals"]
   ```

### 6. Adding Custom Sanitization Rules

**Example**: Add sanitizer to remove specific patterns.

**Steps**:

1. **Update sanitize.py**:
   ```python
   def sanitize_remove_patterns(content: str, patterns: List[str]) -> str:
       for pattern in patterns:
           content = re.sub(pattern, '', content)
       return content
   ```

2. **Configure in handler**:
   ```yaml
   constraints:
     sanitize_remove:
       - "constraint classification headers"
       - "TODO markers"
   ```

3. **Call from WorkflowRunner** after LLM response.

---

## Design Rationale

### Why Document-Driven Workflows?

**Traditional Approach**: Hardcode workflow order in application code.

**Problems**:
- Adding new document types requires code changes
- Workflow order is not visible in templates
- Difficult to customize order for different use cases

**Our Approach**: Declare workflow order in template metadata.

**Benefits**:
- Templates are self-documenting
- No code changes for new doc types
- Workflow order is version-controlled with templates
- Easy to experiment with different orderings

**Tradeoff**: Workflow order validation happens at runtime, not compile time.

### Why Handler Registry?

**Traditional Approach**: Phase-specific functions with hardcoded logic.

**Problems**:
- Duplication across phases (each phase has its own integration logic)
- Hard to understand behavior for specific sections
- Inconsistent sanitization/validation

**Our Approach**: YAML-based configuration for all sections.

**Benefits**:
- Single source of truth for section behaviors
- Discoverable (new developers can read config)
- Testable (test handler with different configs)
- No code changes for behavior tweaks

**Tradeoff**: Configuration is less type-safe than code (validated at runtime).

### Why LLM Profiles?

**Traditional Approach**: Hardcode prompts in code.

**Problems**:
- Prompts are scattered across codebase
- Hard to version and review prompt changes
- Difficult to A/B test different prompts

**Our Approach**: Rules-based profiles in markdown files.

**Benefits**:
- Version-controlled prompts
- Reusable base policy across all tasks
- Easy to iterate on prompts without deploying code
- Testable (test with different profile versions)

**Tradeoff**: Profiles are less dynamic (can't easily generate prompts based on complex runtime logic).

### Why Review Gates?

**Traditional Approach**: Manual review or separate QA scripts.

**Problems**:
- Quality checks happen outside workflow
- Inconsistent review criteria
- Hard to track review history

**Our Approach**: Review gates as first-class workflow targets.

**Benefits**:
- Quality checks integrated into workflow
- Consistent review process
- Review results stored in document
- Configurable (adjust criteria without code changes)

**Tradeoff**: LLM reviews may not catch all issues (still need human review for critical decisions).

### Why Single Processing Loop?

**Traditional Approach**: Separate functions for each phase.

**Problems**:
- Code duplication (each phase has similar integration logic)
- Inconsistent behavior across phases
- Hard to maintain (changes need to be applied to all phases)

**Our Approach**: Single `WorkflowRunner` configured by handler registry.

**Benefits**:
- Single code path for all sections
- Consistent behavior (validation, sanitization)
- Easier to test and maintain
- Behavior customization via configuration, not code

**Tradeoff**: Handler modes must be general enough to cover all use cases (may require more complex configuration).

---

## Summary

The Orchestrator Agent architecture is designed for:

1. **Flexibility**: Add new document types, sections, and behaviors without code changes
2. **Consistency**: Single processing loop ensures uniform behavior
3. **Discoverability**: Configuration-driven design makes behavior explicit
4. **Testability**: Components are loosely coupled and testable in isolation
5. **Maintainability**: Centralized configuration and version-controlled profiles

**Key Design Principles**:

- **Configuration over Code**: Behavior defined in YAML/markdown, not Python
- **Convention over Configuration**: Sensible defaults for common cases
- **Fail Fast**: Validate early and provide clear error messages
- **Explicit over Implicit**: No magic behavior, everything is traceable
- **Version Control Everything**: Templates, profiles, and configurations in git

For more details on specific components:

- [Handler Registry Guide](handler-registry-guide.md)
- [LLM Profiles Guide](llm-profiles-guide.md)
- [Contributing Guide](../contributing.md)
