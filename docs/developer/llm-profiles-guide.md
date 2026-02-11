# LLM Profiles Guide

LLM profiles define how the AI assistant should reason, generate questions, and integrate content. This guide explains the profile system, how to use existing profiles, and how to create new ones.

## Table of Contents

1. [Overview](#overview)
2. [Profile Structure](#profile-structure)
3. [Existing Profiles](#existing-profiles)
4. [How Profiles Are Combined](#how-profiles-are-combined)
5. [Adding New Profiles](#adding-new-profiles)
6. [Profile Best Practices](#profile-best-practices)
7. [Testing Profiles](#testing-profiles)
8. [Troubleshooting](#troubleshooting)

---

## Overview

**Problem**: LLM behavior needs consistent guidance across tasks, but hardcoding prompts in code makes them difficult to maintain, version, and iterate on.

**Solution**: Store prompts as markdown files (profiles) that are loaded dynamically and injected into LLM calls. Profiles are version-controlled alongside code.

**Key Concepts**:

- **Base Policy**: Core rules applied to ALL LLM calls (forbidden actions, output format rules)
- **Task Style Profiles**: Document-type-specific guidance (e.g., requirements vs. research)
- **Task-Specific Instructions**: Generated dynamically by code (e.g., "Generate 3-5 questions about...")
- **Profile Combination**: Base + Task Style + Task Instructions = Full LLM Prompt

**File Location**: `profiles/`

**Loading**:

```python
from profile_loader import ProfileLoader

loader = ProfileLoader()
profile = loader.load_combined(
    llm_profile="requirements",  # From handler config
    task_instructions="Generate questions about security requirements"
)

response = llm.call(profile + context)
```

---

## Profile Structure

### Profile Format

Profiles are markdown files with clear section headers and rules:

```markdown
# Profile Title

## Section 1: Purpose or Guidelines
- Rule 1
- Rule 2

## Section 2: Constraints or Examples
- Constraint 1
- Constraint 2

## Section 3: Output Format
- Format rule 1
- Format rule 2
```

### Design Principles

1. **Rules, Not Personas**: Avoid narrative prompts like "You are an expert requirements analyst." Use concrete rules: "Use RFC 2119 keywords (SHALL, MUST, MAY)."

2. **Specific, Not Vague**: "Output valid JSON with keys: pass, issues, patches" is better than "Be structured."

3. **Constraints, Not Suggestions**: "Never invent facts not provided in context" is better than "Try to be accurate."

4. **Testable**: If you can't verify a rule is followed, rewrite it to be verifiable.

5. **Minimal Duplication**: Don't repeat base policy rules in task profiles.

### Profile Types

#### Base Policy (`profiles/base_policy.md`)

**Purpose**: Universal rules applied to ALL LLM calls.

**Content**:
- Core reasoning rules (never invent facts, flag conflicts)
- Forbidden actions (don't create section markers, don't assume capabilities)
- Output format rules (valid JSON, markdown-formatted prose)
- General reasoning constraints (clarity over cleverness, explicit over implicit)

**When to Update**: When you discover systematic LLM failure modes that apply across all tasks.

**Example**:

```markdown
# Base LLM Policy

## Core Rules
1. Never invent facts, data, or technical details not provided in context
2. Never output document structure markers (<section>, </section>, etc.)
3. Always output valid JSON when JSON is requested
4. Flag conflicts or ambiguities; do not resolve them silently
5. Use crisp, technical language (no marketing speak or filler)

## Forbidden Actions
- Do not create or modify section markers
- Do not assume capabilities not explicitly stated
- Do not combine conflicting requirements without flagging
```

#### Task Style Profiles

**Purpose**: Document-type-specific guidance for reasoning style and output expectations.

**Examples**:
- `requirements.md`: For requirements document sections
- `requirements_review.md`: For requirements review gates
- `research.md`: For research document sections (if created)
- `planning.md`: For planning document sections (if created)

**Content**:
- Language guidelines (tense, keywords, tone)
- Question generation guidelines (what to ask, what to avoid)
- Integration guidelines (how to organize content)
- Output format specifics

**When to Update**: When LLM consistently makes doc-type-specific mistakes or when requirements for a doc type change.

---

## Existing Profiles

### `base_policy.md`

**Purpose**: Universal rules for all LLM calls.

**Key Rules**:

1. **Core Rules**:
   - Never invent facts
   - Never output document structure markers
   - Always output valid JSON when JSON is requested
   - Flag conflicts or ambiguities
   - Use crisp, technical language

2. **Forbidden Actions**:
   - Do not create or modify section markers
   - Do not create or modify table schemas
   - Do not assume capabilities not explicitly stated
   - Do not combine conflicting requirements without flagging

3. **Output Format Rules**:
   - JSON outputs: strictly valid JSON, no markdown wrappers
   - Prose outputs: markdown-formatted text, no HTML
   - Bullet outputs: dash-prefixed lists, one item per line

4. **Reasoning Constraints**:
   - Prioritize clarity over cleverness
   - Prefer explicit over implicit
   - Avoid redundancy within a single section
   - Preserve user's original phrasing when incorporating answers

**Usage**: Automatically injected into every LLM call by `ProfileLoader`.

**File**: `profiles/base_policy.md`

### `requirements.md`

**Purpose**: Style profile for requirements document sections.

**Key Guidelines**:

1. **Language Guidelines**:
   - Use present tense declarative statements ("The system SHALL...")
   - Avoid conditionals ("might", "could", "possibly")
   - Be specific and measurable where possible
   - Use RFC 2119 keywords: SHALL, SHALL NOT, MUST, MUST NOT, SHOULD, SHOULD NOT, MAY, OPTIONAL

2. **Question Generation Guidelines**:
   - Ask about missing critical requirements (security, performance, data)
   - Ask about ambiguous scope boundaries
   - Ask about stakeholder priorities or constraints
   - Do NOT ask questions answerable from existing context
   - Target questions to specific sections (use section_target field)

3. **Integration Guidelines**:
   - Convert answers into requirement-style statements
   - Organize content logically (general → specific)
   - Remove placeholder wording ("TBD", "to be determined")
   - Preserve traceability to original questions where reasonable
   - For assumptions: use bullet format, one assumption per line
   - For constraints: organize under Technical/Operational/Resource subsections

**Usage**: Set in handler configuration:

```yaml
requirements:
  problem_statement:
    llm_profile: requirements
```

**File**: `profiles/requirements.md`

### `requirements_review.md`

**Purpose**: Style profile for requirements review gates.

**Key Guidelines**:

1. **Review Objective**:
   - Validate completeness, consistency, and quality of requirements sections

2. **Review Criteria**:
   - **Completeness**: Are critical requirements areas covered?
   - **Consistency**: Do sections contradict each other?
   - **Clarity**: Are requirements unambiguous and testable?
   - **Feasibility**: Are there obvious impossibilities or conflicts?

3. **Output Format**:
   - Return JSON with:
     - `pass`: boolean (true if no blocking issues)
     - `issues`: array of `{"severity": "blocker|warning", "section": "...", "description": "..."}`
     - `patches`: array of `{"section": "...", "suggestion": "...", "rationale": "..."}` (optional)

4. **Issue Severity Guidelines**:
   - **Blocker**: Missing critical sections, contradictory requirements, impossible constraints
   - **Warning**: Ambiguous wording, missing details, inconsistent formatting

5. **Patching Guidelines**:
   - Only suggest patches for objective errors (typos, formatting, obvious omissions)
   - Do not suggest patches for subjective improvements
   - Patches must be unambiguous and mechanically applicable

**Usage**: Set in review gate handler configuration:

```yaml
requirements:
  review_gate:coherence_check:
    mode: review_gate
    llm_profile: requirements_review
```

**File**: `profiles/requirements_review.md`

---

## How Profiles Are Combined

Profiles are combined in a specific order to create the full LLM prompt:

### Combination Order

```
1. Base Policy (profiles/base_policy.md)
   ↓ Always injected first
   
2. Task Style Profile (e.g., profiles/requirements.md)
   ↓ Selected based on handler config llm_profile field
   
3. Task-Specific Instructions
   ↓ Generated dynamically by code
   
4. Context
   ↓ Section content, questions, related sections
   
= Full LLM Prompt
```

### Example: Integration Task

**Handler Configuration**:

```yaml
requirements:
  problem_statement:
    mode: integrate_then_questions
    llm_profile: requirements
```

**Code**:

```python
task_instructions = """
Integrate the following answered questions into the problem_statement section.
Output the integrated content as flowing prose paragraphs.
"""

profile = loader.load_combined(
    llm_profile="requirements",
    task_instructions=task_instructions
)
```

**Resulting Prompt**:

```
# Base LLM Policy

## Core Rules
1. Never invent facts, data, or technical details not provided in context
2. Never output document structure markers (<section>, </section>, etc.)
...

---

# Requirements Document Style

## Language Guidelines
- Use present tense declarative statements ("The system SHALL...")
- Use RFC 2119 keywords appropriately: SHALL, MUST, MAY
...

---

Integrate the following answered questions into the problem_statement section.
Output the integrated content as flowing prose paragraphs.

---

# Context

## Current Section Content
[Current problem_statement content]

## Answered Questions
Q: What problem does this solve?
A: Users cannot easily track project dependencies...

Q: Who is affected by this problem?
A: Development teams managing multiple microservices...
```

### Example: Review Gate Task

**Handler Configuration**:

```yaml
requirements:
  review_gate:coherence_check:
    mode: review_gate
    llm_profile: requirements_review
```

**Code**:

```python
task_instructions = """
Review all prior sections for coherence and consistency.
Check for contradictions, missing critical sections, and inconsistent terminology.
Return JSON with: pass (bool), issues (array), patches (array).
"""

profile = loader.load_combined(
    llm_profile="requirements_review",
    task_instructions=task_instructions
)
```

**Resulting Prompt**:

```
# Base LLM Policy
[Base policy content]

---

# Requirements Review Style

## Review Criteria
- Completeness: Are critical requirements areas covered?
- Consistency: Do sections contradict each other?
...

---

Review all prior sections for coherence and consistency.
Check for contradictions, missing critical sections, and inconsistent terminology.
Return JSON with: pass (bool), issues (array), patches (array).

---

# Context

## Prior Sections
[All completed sections before this review gate]
```

### Code Implementation

The `ProfileLoader` class handles combination:

```python
# tools/requirements_automation/profile_loader.py

class ProfileLoader:
    def load_combined(self, llm_profile: str, task_instructions: str) -> str:
        """Combine base policy, task profile, and task instructions."""
        base_policy = self.load_base_policy()
        task_profile = self.load_task_profile(llm_profile)
        
        combined = f"{base_policy}\n\n---\n\n{task_profile}\n\n---\n\n{task_instructions}"
        return combined
```

---

## Adding New Profiles

Follow these steps to add a new task style profile.

### Step 1: Identify the Need

**When to add a new profile**:
- Creating a new document type (research, planning, test specs)
- Existing profile doesn't fit the doc type's requirements
- Need fundamentally different LLM behavior (e.g., creative vs. analytical)

**When NOT to add a new profile**:
- Minor variations (adjust existing profile instead)
- Section-specific tweaks (use task instructions in code)
- Temporary experiments (test with modified prompts first)

### Step 2: Create Profile File

Create a new markdown file in `profiles/` directory:

```bash
touch profiles/research.md
```

### Step 3: Write Profile Content

Follow the profile structure and design principles:

```markdown
# Research Task Profile

## Document Purpose
This is a research document for exploring topics, reviewing literature, and documenting findings.

## Language Guidelines
- Use present tense for current state of research
- Use past tense for prior work and findings
- Use future tense for planned research activities
- Cite sources when referencing prior work (format: [Author, Year])

## Question Generation Guidelines
- Ask about research scope and boundaries
- Ask about data sources and methodology
- Ask about expected outcomes and success criteria
- Ask about resources and constraints
- Do NOT ask questions answerable from context

## Integration Guidelines
- Organize literature review by topic or chronology
- Clearly attribute findings to sources
- Distinguish between established facts and interpretations
- Use evidence-based reasoning
- Cite sources consistently

## Output Constraints
- Use academic tone (no marketing language)
- Be precise with terminology
- Flag gaps or limitations in research
- Avoid speculation without evidence
```

### Step 4: Update Handler Registry

Add handler configurations that use the new profile:

```yaml
research:
  literature_review:
    mode: integrate_then_questions
    output_format: prose
    llm_profile: research  # Reference new profile
```

### Step 5: Test Profile

Test with a real document:

```bash
python -m tools.requirements_automation.cli \
  --template docs/templates/research-template.md \
  --doc docs/test-research.md \
  --repo-root . \
  --dry-run
```

Review LLM output to ensure:
- Language guidelines are followed
- Questions are appropriate
- Integration style matches expectations

### Step 6: Iterate

Based on testing:
1. Adjust profile rules
2. Add missing guidelines
3. Remove ineffective rules
4. Test again

### Step 7: Document

Update this guide with:
- New profile description
- Usage examples
- Handler configuration examples

---

## Profile Best Practices

### 1. Be Specific and Concrete

❌ **Bad**: "Be professional and accurate"  
✅ **Good**: "Use RFC 2119 keywords (SHALL, MUST, MAY) for requirements"

❌ **Bad**: "Output should be structured"  
✅ **Good**: "Output JSON with keys: pass (bool), issues (array), patches (array)"

### 2. Use Examples Where Helpful

When rules are complex, provide examples:

```markdown
## Integration Guidelines
- Convert Q&A into declarative statements

Example:
Q: What is the maximum response time?
A: 500ms for API calls, 2s for complex queries

Integrated:
"The system SHALL respond to API calls within 500ms. Complex queries SHALL complete within 2 seconds."
```

### 3. Avoid Redundancy

Don't repeat base policy rules in task profiles:

❌ **Bad**:
```markdown
# Research Profile
- Never invent facts (already in base policy)
```

✅ **Good**:
```markdown
# Research Profile
- Cite sources in format: [Author, Year] (research-specific)
```

### 4. Focus on Behavior, Not Identity

❌ **Bad**: "You are an expert requirements analyst with 10 years of experience"  
✅ **Good**: "Use RFC 2119 keywords and ensure requirements are testable"

### 5. Make Rules Verifiable

Can you check if the rule was followed? If not, rewrite it.

❌ **Bad**: "Be thoughtful about edge cases"  
✅ **Good**: "Identify at least 3 potential edge cases and document handling"

### 6. Use Imperative Language

❌ **Bad**: "It would be good to use bullets"  
✅ **Good**: "Use bullet format, one item per line"

### 7. Organize Logically

Group related rules under clear headers:

```markdown
## Language Guidelines
[Rules about tense, keywords, tone]

## Question Generation Guidelines
[Rules about what to ask, what to avoid]

## Integration Guidelines
[Rules about organizing content, formatting]

## Output Constraints
[Rules about output format, structure]
```

### 8. Test with Real Data

Don't assume rules work—test with actual documents:

1. Create test document
2. Run workflow with profile
3. Review LLM output
4. Adjust profile based on results
5. Repeat

### 9. Version Control Profiles

Treat profiles like code:

```bash
git add profiles/research.md
git commit -m "Add research document profile

- Define citation format
- Add literature review guidelines
- Specify academic tone requirements"
```

### 10. Document Rationale

Add comments explaining why rules exist:

```markdown
## Question Generation Guidelines
- Do NOT ask questions answerable from existing context
  <!-- Rationale: Reduces user burden and avoids redundant questions -->
```

---

## Testing Profiles

### Unit Testing

Test individual rules in isolation:

```python
# test-scripts/test_profiles.py

def test_requirements_profile_loaded():
    loader = ProfileLoader()
    profile = loader.load_task_profile("requirements")
    assert "RFC 2119" in profile
    assert "SHALL" in profile
```

### Integration Testing

Test profile combination:

```python
def test_profile_combination():
    loader = ProfileLoader()
    combined = loader.load_combined(
        llm_profile="requirements",
        task_instructions="Generate questions"
    )
    
    # Should include base policy
    assert "Never invent facts" in combined
    
    # Should include task profile
    assert "RFC 2119" in combined
    
    # Should include task instructions
    assert "Generate questions" in combined
```

### Manual Testing

Test with real LLM calls:

```bash
# Test integration task
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/test-requirements.md \
  --repo-root . \
  --dry-run

# Review output for:
# - Correct language style (tense, keywords)
# - Appropriate question quality
# - Proper content organization
```

### A/B Testing

Compare two profile versions:

1. Save current profile: `cp profiles/requirements.md profiles/requirements_v1.md`
2. Modify profile: `vim profiles/requirements.md`
3. Test both versions on same document
4. Compare outputs and choose better version
5. Document changes: `git commit -m "Improve requirements profile: ..."`

### Regression Testing

Ensure profile changes don't break existing behavior:

```bash
# Run full test suite
python test-scripts/test_integration.py
python test-scripts/test_e2e_prior_context.py
python test-scripts/validate_acceptance_criteria.py

# Process existing documents
python -m tools.requirements_automation.cli \
  --template docs/templates/requirements-template.md \
  --doc docs/requirements.md \
  --repo-root . \
  --validate
```

---

## Troubleshooting

### Issue: LLM ignores profile rules

**Symptoms**: LLM output doesn't follow profile guidelines.

**Possible Causes**:
1. Rule is too vague or abstract
2. Rule conflicts with other rules
3. Task instructions override profile
4. Context is too noisy

**Solutions**:
1. Make rule more specific and concrete
2. Review all rules for conflicts
3. Adjust task instructions in code
4. Simplify context or add examples to profile

**Example**:

❌ **Vague Rule**: "Be clear"  
✅ **Specific Rule**: "Use one sentence per requirement. Each requirement SHALL include a measurable success criterion."

### Issue: Profile too long, LLM confused

**Symptoms**: LLM output quality degrades with complex profiles.

**Possible Causes**:
1. Profile has too many rules
2. Rules are verbose or repetitive
3. Examples are too long

**Solutions**:
1. Prioritize: Keep only most important rules
2. Be concise: One rule per line, short sentences
3. Shorten examples: Use minimal illustrative cases

**Guideline**: Aim for profiles under 50 lines.

### Issue: Different outputs for same input

**Symptoms**: Running same task twice produces different results.

**Possible Causes**:
1. LLM temperature set too high
2. Profile rules not deterministic enough
3. Context includes timestamps or random data

**Solutions**:
1. Lower temperature in LLMClient: `temperature=0.3`
2. Add deterministic constraints to profile
3. Remove non-deterministic data from context

**Example**:

Add to profile:
```markdown
## Output Constraints
- Generate exactly 5 questions (not "3-5" or "up to 5")
- Order requirements alphabetically by category
- Use consistent formatting (no variation)
```

### Issue: Profile changes don't apply

**Symptoms**: Modified profile doesn't affect LLM output.

**Possible Causes**:
1. Profile file not saved
2. Wrong profile referenced in handler config
3. Profile cache not refreshed
4. Handler config not reloaded

**Solutions**:
1. Verify file saved: `cat profiles/requirements.md`
2. Check handler config: `llm_profile: requirements`
3. Restart CLI process (profiles loaded at startup)
4. Check handler registry loaded correctly

### Issue: Profile works for some sections, not others

**Symptoms**: Profile guidelines followed in some sections but not others.

**Possible Causes**:
1. Different handler configs for different sections
2. Task instructions override profile
3. Section-specific context affects LLM behavior

**Solutions**:
1. Check handler configs: ensure same `llm_profile` used
2. Review task instructions in code for overrides
3. Adjust profile to handle different contexts

---

## Summary

LLM profiles guide AI behavior through rules-based prompts:

- **Base Policy**: Universal rules for all tasks
- **Task Style Profiles**: Document-type-specific guidance
- **Task Instructions**: Dynamically generated by code
- **Combination**: Base + Task + Instructions = Full Prompt

**Key Principles**:
- Rules, not personas
- Specific, not vague
- Constraints, not suggestions
- Testable and verifiable

**Workflow**:
1. Identify need for new profile
2. Create markdown file in `profiles/`
3. Write clear, concrete rules
4. Reference in handler configuration
5. Test with real documents
6. Iterate based on results

**Best Practices**:
- Be specific and concrete
- Avoid redundancy with base policy
- Focus on behavior, not identity
- Test with real data
- Version control everything

For more information:
- [Architecture Guide](architecture.md) - Core concepts and design
- [Handler Registry Guide](handler-registry-guide.md) - Configuration details
- [Contributing Guide](contributing.md) - Development workflow

**Next Steps**:
- Review existing profiles in `profiles/` directory
- Experiment with profile modifications using `--dry-run`
- Create a custom profile for a new document type
- Test profile effectiveness with A/B comparisons
