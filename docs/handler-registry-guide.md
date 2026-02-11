# Handler Registry Guide

The handler registry is the central configuration system that maps `(doc_type, section_id)` → processing behavior. This guide explains how to configure handlers, understand handler modes, and extend the system with new sections and document types.

## Table of Contents

1. [Overview](#overview)
2. [Configuration Schema](#configuration-schema)
3. [Handler Modes](#handler-modes)
4. [Output Formats](#output-formats)
5. [Adding a New Section Type](#adding-a-new-section-type)
6. [Adding a New Doc Type](#adding-a-new-doc-type)
7. [Examples](#examples)
8. [Best Practices](#best-practices)

---

## Overview

The handler registry decouples section processing logic from code. Instead of hardcoding behavior in Python functions, we declare it in a YAML configuration file.

**File Location**: `config/handler_registry.yaml`

**Purpose**:
- Define how each section should be processed
- Specify LLM behavior profiles
- Configure output formatting
- Enable review gates and quality checks

**Structure**:

```yaml
doc_type:              # e.g., requirements, research, planning
  section_id:          # e.g., problem_statement, goals_objectives
    mode: ...          # Handler mode (see below)
    output_format: ... # Output format (prose, bullets, subsections)
    llm_profile: ...   # LLM profile to use
    # ... other config fields
```

**Loading**:

```python
from handler_registry import HandlerRegistry

registry = HandlerRegistry("config/handler_registry.yaml")
config = registry.get_handler("requirements", "problem_statement")
```

**Fallback**: If a specific `(doc_type, section_id)` is not found, the registry falls back to `_default.requirements` configuration.

---

## Configuration Schema

### Complete Schema

```yaml
doc_type:
  section_id:
    # REQUIRED FIELDS
    mode: integrate_then_questions | questions_then_integrate | review_gate
    output_format: prose | bullets | subsections
    llm_profile: string  # Profile name (e.g., requirements, requirements_review)
    
    # OPTIONAL FIELDS
    subsections: boolean              # Support subsection headers (default: false)
    dedupe: boolean                   # Remove duplicate lines (default: false)
    preserve_headers: list[string]    # Headers to preserve during sanitization (default: [])
    sanitize_remove: list[string]     # Patterns to remove (default: [])
    auto_apply_patches: never | always | if_validation_passes  # Patch application policy (default: never)
    scope: current_section | all_prior_sections  # Processing scope (default: current_section)
    validation_rules: list[string]    # Validation rules to apply (default: [])
```

### Field Descriptions

#### `mode` (required)

Defines how the section is processed. See [Handler Modes](#handler-modes) for details.

**Values**:
- `integrate_then_questions`: Integrate answers first, generate questions if still blank
- `questions_then_integrate`: Generate questions first (single-pass)
- `review_gate`: Review prior sections for quality assurance

**Example**:
```yaml
mode: integrate_then_questions
```

#### `output_format` (required)

Defines the expected output format from the LLM.

**Values**:
- `prose`: Flowing paragraphs
- `bullets`: Dash-prefixed lists (`- Item 1`, `- Item 2`)
- `subsections`: Content organized under `###` headers

**Example**:
```yaml
output_format: bullets
```

#### `llm_profile` (required)

Specifies which LLM profile to use. Profiles are stored in the `profiles/` directory.

**Values**:
- `requirements`: For requirements document sections
- `requirements_review`: For requirements review gates
- `research`: For research document sections (if defined)
- `planning`: For planning document sections (if defined)

**Example**:
```yaml
llm_profile: requirements
```

#### `subsections` (optional, default: `false`)

Whether the section supports subsection headers (e.g., `### Primary Goals`, `### Secondary Goals`).

**When to use**: Section contains logically grouped content that should be organized under subsection headers.

**Example**:
```yaml
subsections: true  # Enables ### Primary Goals, ### Secondary Goals, etc.
```

#### `dedupe` (optional, default: `false`)

Whether to remove duplicate lines after LLM integration.

**When to use**: Section is prone to duplication (e.g., assumptions from multiple sources).

**Example**:
```yaml
dedupe: true  # Remove duplicate assumption lines
```

#### `preserve_headers` (optional, default: `[]`)

List of headers to preserve during sanitization.

**When to use**: Section has required subsection structure that must not be removed.

**Example**:
```yaml
preserve_headers:
  - "### Technical Constraints"
  - "### Operational Constraints"
  - "### Resource Constraints"
```

#### `sanitize_remove` (optional, default: `[]`)

List of patterns to remove from LLM output.

**When to use**: LLM tends to add unwanted markers or phrasing.

**Example**:
```yaml
sanitize_remove:
  - "constraint classification headers"  # Remove classification notes
```

#### `auto_apply_patches` (optional, default: `never`)

Policy for automatically applying patches suggested by review gates.

**Values**:
- `never`: Patches are suggested but not applied (manual review required)
- `always`: Patches are automatically applied
- `if_validation_passes`: Patches are applied only if they pass validation

**When to use**: Review gates that produce safe, predictable patches.

**Example**:
```yaml
auto_apply_patches: never  # Require manual review
```

#### `scope` (optional, default: `current_section`)

Defines the scope of processing or review.

**Values**:
- `current_section`: Process/review only the current section
- `all_prior_sections`: Review all sections before this one (for review gates)

**When to use**: Review gates that need to check consistency across multiple sections.

**Example**:
```yaml
scope: all_prior_sections  # Review all prior sections for coherence
```

#### `validation_rules` (optional, default: `[]`)

List of validation rules to apply during review.

**Values** (examples):
- `no_contradictions`: Check for contradictory statements
- `no_missing_critical_sections`: Ensure critical sections are present
- `consistent_terminology`: Verify consistent use of terms

**When to use**: Review gates that enforce specific quality criteria.

**Example**:
```yaml
validation_rules:
  - no_contradictions
  - consistent_terminology
```

---

## Handler Modes

Handler modes define the processing logic for sections.

### `integrate_then_questions` (Default)

**Purpose**: Iterative refinement through question-and-answer cycles.

**Behavior**:

1. **If section has answered questions**:
   - Integrate answers into section content via LLM
   - Update section with integrated content
   - Remove integrated questions

2. **If section is still blank after integration**:
   - Generate new questions to gather more information
   - Add questions to question block

3. **If section has open questions but no answers**:
   - Skip (blocked, waiting for answers)

**When to use**:
- Section requires iterative refinement
- Need multiple rounds of questions to gather complete information
- Content evolves as more details are provided

**Example Workflow**:

```
Initial: [Blank section]
  ↓
Round 1: Generate questions (What is the problem? Who is affected?)
  ↓
User provides answers
  ↓
Round 2: Integrate answers → "The problem is X affecting users Y..."
  ↓
If still incomplete: Generate follow-up questions (What are the constraints?)
  ↓
User provides more answers
  ↓
Round 3: Integrate additional answers → "The problem is X... constrained by Z..."
  ↓
Section complete
```

**Configuration Example**:

```yaml
requirements:
  problem_statement:
    mode: integrate_then_questions
    output_format: prose
    llm_profile: requirements
```

### `questions_then_integrate` (Single-Pass)

**Purpose**: Single-pass question generation and integration.

**Behavior**:

1. **If section is blank and no questions exist**:
   - Generate questions once
   - Add questions to question block

2. **If section has answered questions**:
   - Integrate answers into section content via LLM
   - Update section with integrated content
   - Remove integrated questions
   - **Do not generate new questions** (single pass complete)

3. **If section has open questions but no answers**:
   - Skip (blocked, waiting for answers)

**When to use**:
- Single round of questions is sufficient
- Section structure is well-defined and predictable
- Avoid iterative cycles for simple sections

**Example Workflow**:

```
Initial: [Blank section]
  ↓
Round 1: Generate questions (all questions at once)
  ↓
User provides answers
  ↓
Round 2: Integrate answers → Section complete (no further questions)
```

**Configuration Example**:

```yaml
research:
  research_questions:
    mode: questions_then_integrate
    output_format: bullets
    llm_profile: research
```

### `review_gate` (Quality Assurance)

**Purpose**: Quality assurance checkpoint that reviews prior sections.

**Behavior**:

1. **Gather scope**:
   - If `scope: current_section`: Review only the current section
   - If `scope: all_prior_sections`: Review all sections before this gate

2. **LLM Review**:
   - Call LLM with review profile (e.g., `requirements_review`)
   - LLM checks for issues based on `validation_rules`

3. **Structured Result**:
   - `pass`: Boolean (true if no issues)
   - `issues`: List of issue descriptions
   - `patches`: List of suggested fixes

4. **Store Result**:
   - Write issues and patches to gate section
   - Mark gate as passed/failed

5. **Apply Patches** (optional):
   - Based on `auto_apply_patches` policy

**When to use**:
- Quality checkpoint needed in workflow
- Check consistency across multiple sections
- Enforce specific quality criteria

**Example Workflow**:

```
Prior sections complete
  ↓
Review Gate: coherence_check
  ↓
LLM reviews all prior sections
  ↓
Issues found:
  1. Contradiction between section 3 and section 5
  2. Missing critical section: Security Requirements
  ↓
Patches suggested:
  1. Clarify constraint in section 3
  2. Add Security Requirements section
  ↓
Store issues/patches in gate section
  ↓
If auto_apply_patches: never → Manual review required
If auto_apply_patches: always → Apply patches automatically
```

**Configuration Example**:

```yaml
requirements:
  review_gate:coherence_check:
    mode: review_gate
    output_format: prose
    llm_profile: requirements_review
    scope: all_prior_sections
    auto_apply_patches: never
    validation_rules:
      - no_contradictions
      - no_missing_critical_sections
      - consistent_terminology
```

**Review Result Format**:

```json
{
  "pass": false,
  "issues": [
    {
      "severity": "high",
      "description": "Contradiction between constraints and requirements",
      "location": "section 3.2, section 5.1"
    }
  ],
  "patches": [
    {
      "section_id": "constraints",
      "description": "Clarify technical constraint wording",
      "diff": "..."
    }
  ]
}
```

---

## Output Formats

### `prose`

**Description**: Flowing paragraphs of text.

**When to use**: Narrative sections (problem statement, description, rationale).

**Example Output**:

```markdown
The system must support user authentication via OAuth 2.0. Users will
authenticate using their corporate credentials, and sessions will be
maintained for 8 hours. After session expiry, users must re-authenticate.
```

**LLM Instruction** (automatically injected):
> Output as flowing prose paragraphs. Do not use bullet points or numbered lists.

### `bullets`

**Description**: Dash-prefixed list items.

**When to use**: Lists of items (goals, assumptions, success criteria).

**Example Output**:

```markdown
- Users can log in with corporate credentials
- Sessions expire after 8 hours of inactivity
- Multi-factor authentication is available for sensitive operations
- Password reset functionality is accessible without login
```

**LLM Instruction** (automatically injected):
> Output as a dash-prefixed bullet list. Each item should be a single line starting with `- `.

### `subsections`

**Description**: Content organized under `###` subsection headers.

**When to use**: Sections with logical groupings (constraints with technical/operational/resource subsections).

**Example Output**:

```markdown
### Technical Constraints
- System must run on AWS infrastructure
- Database must be PostgreSQL 14+

### Operational Constraints
- Deployment windows limited to weekends
- Zero downtime requirement

### Resource Constraints
- Team size limited to 5 developers
- Budget capped at $100K
```

**LLM Instruction** (automatically injected):
> Organize content under `###` subsection headers. Each subsection should contain relevant bullet points or prose.

---

## Adding a New Section Type

Follow these steps to add a new section to an existing document type.

### Step 1: Add Section Marker to Template

Edit the document template (e.g., `docs/templates/requirements-template.md`):

```markdown
<!-- section:security_requirements -->
## Security Requirements

<!-- This section details security-specific requirements -->

<!-- Content will be generated here -->
```

### Step 2: Add to Workflow Order

Update the `workflow:order` metadata in the template:

```markdown
<!-- workflow:order
problem_statement
goals_objectives
security_requirements    ← Add new section here
approval_record
-->
```

### Step 3: Configure Handler

Add configuration to `config/handler_registry.yaml`:

```yaml
requirements:
  # ... existing sections ...
  
  security_requirements:
    mode: integrate_then_questions
    output_format: bullets
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: requirements
    auto_apply_patches: never
    scope: current_section
```

### Step 4: Test

Run the CLI to verify:

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/test-requirements.md \
  --repo-root . \
  --validate-structure
```

Should output: `✅ Document structure valid`

### Step 5: Process Section

Run normal workflow:

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/test-requirements.md \
  --repo-root .
```

The system will process `security_requirements` when it's next in the workflow order.

---

## Adding a New Doc Type

Follow these steps to add a completely new document type (e.g., research notes, planning docs).

### Step 1: Create Template

Create a new template file (e.g., `docs/templates/research-template.md`):

```markdown
<!-- meta:doc_type value="research" -->
<!-- meta:doc_format value="markdown" version="1.0" -->

<!-- workflow:order
research_questions
literature_review
methodology
findings
conclusions
-->

# Research Notes

<!-- meta:project_name -->
- **Project:** [Project Name]

<!-- meta:status -->
- **Status:** Draft

---

<!-- section:research_questions -->
## Research Questions

<!-- Define the research questions to investigate -->

<!-- section:literature_review -->
## Literature Review

<!-- Review existing literature and prior art -->

<!-- section:methodology -->
## Methodology

<!-- Describe research methodology -->

<!-- section:findings -->
## Findings

<!-- Document research findings -->

<!-- section:conclusions -->
## Conclusions

<!-- Summarize conclusions and next steps -->
```

### Step 2: Add Handler Configurations

Add configurations to `config/handler_registry.yaml`:

```yaml
# ... existing doc types ...

research:
  research_questions:
    mode: questions_then_integrate  # Single-pass for research questions
    output_format: bullets
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: research
    auto_apply_patches: never
    scope: current_section
  
  literature_review:
    mode: integrate_then_questions  # Iterative for literature review
    output_format: prose
    subsections: true  # Enable subsections for different topics
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: research
    auto_apply_patches: never
    scope: current_section
  
  methodology:
    mode: integrate_then_questions
    output_format: prose
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: research
    auto_apply_patches: never
    scope: current_section
  
  findings:
    mode: integrate_then_questions
    output_format: subsections  # Organize findings by category
    subsections: true
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: research
    auto_apply_patches: never
    scope: current_section
  
  conclusions:
    mode: integrate_then_questions
    output_format: prose
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: research
    auto_apply_patches: never
    scope: current_section
```

### Step 3: Create LLM Profile

Create a new LLM profile (e.g., `profiles/research.md`):

```markdown
# Research Task Profile

## Language Guidelines
- Use present tense for current state of research
- Use past tense for prior work and findings
- Use future tense for planned research activities
- Cite sources when referencing prior work

## Question Generation Guidelines
- Generate questions that clarify research scope
- Ask about data sources and methodology
- Inquire about expected outcomes and success criteria

## Integration Guidelines
- Organize literature review by topic or chronology
- Clearly attribute findings to sources
- Distinguish between established facts and interpretations
- Use evidence-based reasoning

## Output Constraints
- Cite sources in format: [Author, Year]
- Use academic tone (no marketing language)
- Be precise with terminology
- Flag gaps or limitations in research
```

### Step 4: Update Supported Doc Types

Edit `tools/requirements_automation/config.py`:

```python
SUPPORTED_DOC_TYPES = ["requirements", "research", "planning"]  # Add "research"
```

### Step 5: Test New Doc Type

Create a test document:

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/research-template.md \
  --doc docs/my-research.md \
  --repo-root .
```

Verify structure:

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/research-template.md \
  --doc docs/my-research.md \
  --repo-root . \
  --validate-structure
```

Process workflow:

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/research-template.md \
  --doc docs/my-research.md \
  --repo-root . \
  --max-steps 5
```

### Step 6: Document

Add documentation for the new doc type:
- Update README.md with example usage
- Add section to this guide explaining handler choices
- Document any special considerations

---

## Examples

### Example 1: Standard Section

**Use Case**: Simple section with prose output.

```yaml
requirements:
  problem_statement:
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

### Example 2: Section with Subsections

**Use Case**: Goals section with primary/secondary/non-goals subsections.

```yaml
requirements:
  goals_objectives:
    mode: integrate_then_questions
    output_format: bullets
    subsections: true  # Enable ### Primary Goals, ### Secondary Goals
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: requirements
    auto_apply_patches: never
    scope: current_section
```

### Example 3: Section with Deduplication

**Use Case**: Assumptions section prone to duplication.

```yaml
requirements:
  assumptions:
    mode: integrate_then_questions
    output_format: bullets
    subsections: false
    dedupe: true  # Remove duplicate assumptions
    preserve_headers: []
    sanitize_remove:
      - "constraint classification headers"
    llm_profile: requirements
    auto_apply_patches: never
    scope: current_section
```

### Example 4: Section with Preserved Headers

**Use Case**: Constraints section with required subsection structure.

```yaml
requirements:
  constraints:
    mode: integrate_then_questions
    output_format: subsections
    subsections: false
    dedupe: false
    preserve_headers:  # These headers must not be removed
      - "### Technical Constraints"
      - "### Operational Constraints"
      - "### Resource Constraints"
    sanitize_remove: []
    llm_profile: requirements
    auto_apply_patches: never
    scope: current_section
```

### Example 5: Review Gate

**Use Case**: Coherence check reviewing all prior sections.

```yaml
requirements:
  review_gate:coherence_check:
    mode: review_gate
    output_format: prose
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: requirements_review
    auto_apply_patches: never  # Require manual review
    scope: all_prior_sections  # Review all prior sections
    validation_rules:
      - no_contradictions
      - no_missing_critical_sections
      - consistent_terminology
```

### Example 6: Single-Pass Section

**Use Case**: Research questions that don't need iteration.

```yaml
research:
  research_questions:
    mode: questions_then_integrate  # Single-pass mode
    output_format: bullets
    subsections: false
    dedupe: false
    preserve_headers: []
    sanitize_remove: []
    llm_profile: research
    auto_apply_patches: never
    scope: current_section
```

---

## Best Practices

### 1. Choose the Right Handler Mode

- **`integrate_then_questions`**: Default choice for most sections. Use when iterative refinement is beneficial.
- **`questions_then_integrate`**: Use for simple, well-defined sections where one round of questions is sufficient.
- **`review_gate`**: Use for quality checkpoints that review multiple sections.

### 2. Match Output Format to Content

- **`prose`**: Narrative sections (problem statement, rationale, descriptions)
- **`bullets`**: Lists of items (goals, assumptions, risks)
- **`subsections`**: Sections with logical groupings (constraints by type, goals by priority)

### 3. Use Subsections Judiciously

- Enable `subsections: true` only when content naturally groups into subsections
- Provide `preserve_headers` if subsection structure is required
- Document expected subsection headers in template comments

### 4. Dedupe Only When Necessary

- Enable `dedupe: true` only for sections prone to duplication
- Be aware that deduplication is line-based (identical lines are removed)
- Test to ensure important variations are not accidentally removed

### 5. Configure Review Gates Carefully

- Set `scope: all_prior_sections` for cross-section consistency checks
- Set `scope: current_section` for single-section quality checks
- Use `auto_apply_patches: never` initially, move to `always` only after testing
- Define clear `validation_rules` so reviewers know what to check

### 6. Keep Profiles Focused

- Each LLM profile should target a specific doc type or task
- Don't duplicate base policy rules in task profiles
- Use profiles for rules and constraints, not narrative prompts

### 7. Test Configurations Incrementally

- Add one section at a time
- Test with `--validate-structure` before processing
- Use `--dry-run` to preview changes
- Verify output before committing

### 8. Document Custom Configurations

- Add comments to handler registry explaining unusual configurations
- Update this guide when adding new handler modes or fields
- Keep examples up-to-date with actual configurations

### 9. Version Control Everything

- Commit handler registry changes with clear messages
- Tag stable configurations for easy rollback
- Document breaking changes in commit messages

### 10. Monitor LLM Output Quality

- Review LLM outputs regularly to catch quality issues
- Update profiles if LLM consistently makes the same mistakes
- Adjust `sanitize_remove` patterns based on observed LLM behavior
- Iterate on validation rules as quality expectations evolve

---

## Troubleshooting

### Issue: Section not processing

**Symptoms**: Section remains blank despite running CLI.

**Possible Causes**:
1. Section not in workflow order
2. Handler configuration missing or invalid
3. Prior sections blocking workflow

**Solutions**:
1. Check `workflow:order` in template includes section
2. Verify handler exists in `config/handler_registry.yaml`
3. Use `--validate` to check completion status

### Issue: Wrong output format

**Symptoms**: LLM produces bullets when prose expected (or vice versa).

**Possible Causes**:
1. `output_format` not set correctly
2. LLM profile conflicts with output format
3. Sanitization removing formatting

**Solutions**:
1. Check `output_format` in handler config
2. Review LLM profile for conflicting instructions
3. Disable sanitization temporarily to check

### Issue: Questions not generated

**Symptoms**: Section stays blank, no questions appear.

**Possible Causes**:
1. Handler mode is `questions_then_integrate` but questions already generated (single-pass complete)
2. Section has open questions (blocked waiting for answers)
3. LLM error (check logs)

**Solutions**:
1. Check mode in handler config
2. Look for existing questions in document
3. Run with `--log-level DEBUG` for details

### Issue: Review gate always fails

**Symptoms**: Review gate always finds issues, workflow never progresses.

**Possible Causes**:
1. Validation rules too strict
2. LLM profile for review too aggressive
3. Prior sections incomplete

**Solutions**:
1. Review `validation_rules` in handler config
2. Adjust review profile (`profiles/requirements_review.md`)
3. Ensure prior sections are complete and valid

---

## Summary

The handler registry is the central configuration system for section processing:

- **Maps** `(doc_type, section_id)` → processing behavior
- **Enables** adding new sections and doc types without code changes
- **Configures** handler modes, output formats, LLM profiles, and validation
- **Supports** iterative workflows, single-pass processing, and review gates

For more information:
- [Architecture Guide](architecture.md) - Core concepts and design
- [LLM Profiles Guide](llm-profiles-guide.md) - Profile structure and best practices
- [Contributing Guide](../contributing.md) - Development workflow

**Next Steps**:
- Review example configurations in `config/handler_registry.yaml`
- Try adding a new section to an existing document type
- Experiment with handler modes to understand behavior differences
- Create a custom LLM profile for a new document type
