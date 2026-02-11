# LLM Profiles

This directory contains LLM policy and style profiles that guide LLM behavior across the orchestrator-agent system.

## Profile Types

### Base Policy (`base_policy.md`)
The base policy is **always injected** into every LLM call. It defines core rules, forbidden actions, output format rules, and reasoning constraints that apply universally.

**When to update**: When you discover systematic LLM failure modes or want to add universal constraints.

### Task Style Profiles
Task style profiles are injected based on the `llm_profile` field in the handler configuration. They provide document-type-specific guidance for reasoning style and output expectations.

#### `requirements.md`
Used for requirements document sections. Defines:
- Language guidelines (RFC 2119 keywords, declarative style)
- Question generation guidelines
- Integration guidelines for Q&A

**When to use**: Set `llm_profile: requirements` in handler config for requirements sections.

#### `requirements_review.md`
Used for requirements review gates. Defines:
- Review criteria (completeness, consistency, clarity, feasibility)
- Output format for review results (pass/fail, issues, patches)
- Severity guidelines for issues

**When to use**: Set `llm_profile: requirements_review` in handler config for review gates.

## Profile Structure

Profiles are combined as:
```
{base_policy}

---

{task_style_profile}

---

{task-specific instructions from code}
```

The ProfileLoader class in `tools/requirements_automation/profile_loader.py` handles loading and caching profiles.

## Adding New Profiles

1. Create a new `.md` file in this directory (e.g., `research.md`, `planning.md`)
2. Follow the structure of existing profiles (use markdown headers, bullet lists)
3. Focus on rules and constraints, not personas or narrative prose
4. Update handler configuration to reference the new profile via `llm_profile` field
5. Test with real LLM calls to validate effectiveness

## Profile Maintenance

- Profiles are living documents—update as LLM behavior is refined
- Version control profiles alongside code (track changes in git)
- Document profile updates in changelog (impacts LLM output)
- Test before deploying profile changes to production

## Best Practices

- **Rules, not personas**: Avoid "You are an expert..." phrasing
- **Specific, not vague**: "Use RFC 2119 keywords" > "Be professional"
- **Constraints, not suggestions**: "Never invent facts" > "Try to be accurate"
- **Testable**: If you can't verify a rule is followed, it's not a good rule
