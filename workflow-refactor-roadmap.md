# Workflow Refactor & Integration Loop Roadmap

This document converts the proposed refactor and architecture changes into a concrete, reviewable set of GitHub Issues. Each issue is intentionally scoped, ordered, and phrased so it can be handed directly to Codex or a human contributor without ambiguity.

---

## Epic: Unified LLM Integration Workflow Engine

**Goal:** Replace phase-specific logic with a reusable, document-driven workflow engine that iterates sections deterministically using a single LLM integration loop.

**Out of scope (for this epic):** New content domains, advanced agents, UI, or multi-doc orchestration.

---

## Issue 1: Add `doc_type` Metadata Marker to Templates

**Type:** Enhancement

**Description:**
Introduce an explicit `doc_type` metadata marker in document templates to drive LLM reasoning style and handler selection.

**Acceptance Criteria:**

* Template includes a meta marker:

  ```md
  <!-- meta:doc_type -->
  - **Doc Type:** requirements
  ```
* Parser can reliably extract `doc_type`
* Filename is treated as fallback only
* Missing `doc_type` fails safely with a clear error

**Notes:**
This becomes the primary routing signal for LLM behavior profiles.

---

## Issue 2: Introduce Workflow Order Manifest in Templates

**Type:** Enhancement

**Description:**
Replace hard-coded phase sequencing with a template-declared workflow order.

**Implementation:**
Add a single ordered list marker in the template header:

```md
<!-- workflow:order
problem_statement
goals_objectives
stakeholders_users
assumptions
constraints
requirements
interfaces_integrations
data_considerations
risks_open_issues
review_gate:pre_approval
approval_record
-->
```

**Acceptance Criteria:**

* Parser extracts ordered workflow targets
* Runner respects declared order exactly
* Unknown section IDs produce a validation error

---

## Issue 3: Implement `WorkflowRunner` Core Loop

**Type:** Refactor

**Description:**
Create a single, reusable workflow runner that:

* Iterates workflow targets in order
* Executes only the *first incomplete* target per run
* Stops deterministically

**Acceptance Criteria:**

* No phase-specific branching remains in `main()`
* Runner accepts:

  * parsed workflow order
  * document state
  * handler registry
* Supports `--max-steps N` for batch execution (optional)

---

## Issue 4: Create Section Handler Registry

**Type:** Architecture

**Description:**
Introduce a registry that maps `(doc_type, section_id)` → handler configuration.

**Example Mapping:**

```yaml
requirements:
  assumptions:
    mode: integrate_then_questions
    output: bullets
    dedupe: true
  constraints:
    mode: integrate_then_questions
    output: subsections
    strict: true
  review_gate:pre_approval:
    mode: review_gate
    scope: all_prior_sections
```

**Acceptance Criteria:**

* Default handler exists
* Review-gate handler is supported
* Unknown sections fall back safely or error explicitly

---

## Issue 5: Refactor LLM Integration into a Single Reusable Loop

**Type:** Refactor

**Description:**
Unify all LLM interactions (questions, integration, review) behind a single execution loop driven by handler config.

**Acceptance Criteria:**

* Same loop used for all sections and future doc types
* LLM never edits document structure directly
* All outputs are JSON or sanitized data-plane text

---

## Issue 6: Introduce Minimal LLM Policy + Style Profiles

**Type:** Enhancement

**Description:**
Add lightweight, non-persona profiles injected into every LLM call.

**Structure:**

```
profiles/
  base_policy.md
  task_styles/
    requirements.md
    research.md
    planning.md
```

**Acceptance Criteria:**

* Base policy always injected
* Task style selected via `doc_type`
* Profiles contain rules, not prose

---

## Issue 7: Implement Review Gate Handler

**Type:** Feature

**Description:**
Support special workflow targets prefixed with `review_gate:`.

**Behavior:**

* LLM reviews all prior sections
* Returns JSON with:

  * pass/fail
  * issues
  * optional patch suggestions

**Acceptance Criteria:**

* Review gate cannot mutate doc directly
* Engine validates and optionally applies patches
* Review status is machine-verifiable

---

## Issue 8: Define Document Completion Criteria

**Type:** Enhancement

**Description:**
Formalize what "document complete" means.

**Completion Conditions:**

* No `<!-- PLACEHOLDER -->` in required sections
* No Open Questions remain `Open`
* All review gates pass or are explicitly waived
* Structural validators pass

**Acceptance Criteria:**

* Completion check is deterministic
* Used to block progression to downstream automation

---

## Issue 9: Harden Structural and Span Validation

**Type:** Hardening

**Description:**
Strengthen guardrails around section spans and patch application.

**Acceptance Criteria:**

* Patches rejected if span invalid or ambiguous
* Duplicate markers detected and blocked
* No silent corruption allowed

---

## Issue 10: Update Developer Documentation

**Type:** Docs

**Description:**
Document the new architecture so Codex and humans operate from the same mental model.

**Content to Include:**

* Workflow order concept
* Handler registry
* Review gates
* How to add a new doc type or section

---

## Notes for Iteration

* This file is intentionally editable and expandable.
* Expect additional issues for:

  * artifact pipelines (JSON-first requirements)
  * multi-document workflows
  * cross-doc review gates

---

*This plan favors mechanical determinism over cleverness. That’s a feature, not a limitation.*


## 2. Architectural Shift

### R-001 Section-Driven Workflow
- Replace phases with ordered section IDs defined in the document.

---

## 3. Unified Integration Loop

### R-010 Standard Loop
1. Extract section
2. Check questions
3. Generate or integrate
4. Sanitize
5. Resolve
6. Gate completion

---

## 4. Document Type Profiles

### R-020 Minimal Agent Profiles
- Driven by `doc_type` + `section_id`
- Declarative, not procedural

---

## 5. Review Gates

### R-030 Review Sections
- Special sections trigger review-only passes.

---

## 6. JSON-First Pipeline

### R-040 Structured Core
- JSON canonical form
- Markdown as render target

---

## 7. Migration Strategy
1. Freeze current behavior
2. Extract core loop
3. Add adapters
4. Maintain backward compatibility

---

## 8. Success Criteria
- New docs require no engine changes
- Phase logic removed
- Predictable LLM behavior
