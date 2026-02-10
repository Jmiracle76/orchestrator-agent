# Requirements Automation – System Capabilities (Source of Truth)

## Purpose
This document defines the authoritative functional capabilities of the requirements automation system **as it exists today** (February 2026).
Anything listed here is intentional behavior and must not regress without an explicit change decision.

This document is descriptive, not aspirational.

---

## 1. Core Execution Model

### C-001 Phased Workflow
- The system processes requirements documents in sequential phases.
- Each run executes one phase: Phase 1 (Intent/Scope) → Phase 2 (Assumptions/Constraints) → Future phases (placeholders).
- Phases must complete sequentially; Phase 2 only runs after Phase 1 is complete.

### C-002 Deterministic Operation
- Given the same document state and inputs, the script produces deterministic results.
- No probabilistic edits occur outside of LLM-generated section content.

### C-003 Single-Document Scope
- The system modifies only `docs/requirements.md`.
- No other repository files are created, modified, or deleted by automation.
- Backup files are stored outside the git repository (system temp directory).

### C-004 Safe File Operations
- Before writing changes, a backup copy is created in the system temp directory.
- Documents are read entirely into memory before processing.
- All modifications are made in-memory; disk writes are atomic.

---

## 2. Workflow Phases

### C-010 Phase 1: Intent & Scope (Complete)
**Sections**: problem_statement, goals_objectives, stakeholders_users, success_criteria

**Behavior**:
- If section is locked (`lock=true`): Skip processing.
- If section is blank and has no open questions: Generate clarifying questions.
- If section is blank and has open questions: Wait for answers.
- If section has answered questions: Integrate answers into section via LLM, mark questions resolved.
- After integration, check if section is still blank; if so, generate follow-up questions.

**Subsection Support**: Phase 1 sections may contain subsections (e.g., primary_goals, secondary_goals). Answers can target subsections; integrations honor subsection boundaries.

### C-011 Phase 2: Assumptions & Constraints (Complete)
**Sections**: assumptions, constraints

**Behavior**:
- Validate both sections have markers before proceeding (error if missing).
- If section is locked: Skip processing.
- If section has answered questions: Integrate answers, mark resolved.
- If section is blank and has no unanswered questions: Generate clarifying questions.
- If section is blank and has unanswered questions: Wait for answers.

**No Subsections**: Phase 2 sections do not support subsection targeting (questions target the section ID directly).

### C-012 Phase 3+ (Placeholders)
- Phases 3–5 are not yet implemented.
- Running against a partially-complete Phase 2 document will return these phases as "not implemented yet."

---

## 3. Document Structure Enforcement

### C-020 Section Markers
- Sections are identified by `<!-- section:<section_id> -->` markers.
- Section markers are immutable during processing; never deleted, moved, or modified.
- Sections are scoped from marker to marker (or end of document if last section).

### C-021 Section Headers
- Sections may contain markdown headers (`##` or `###`); these are preserved during rewrites.
- Only the body content (excluding markers, headers, locks, dividers) is replaced.

### C-022 Section Locking
- Sections marked with `<!-- section_lock:<section_id> lock=true -->` are never modified.
- The lock marker itself is preserved; only body content would be replaced if lock were false.
- The most recent lock marker in a section determines its lock state.

### C-023 Placeholder Token
- Blank sections contain `<!-- PLACEHOLDER -->` to indicate they need content.
- The placeholder is removed when real content is written.
- A section with a placeholder token is considered "blank" for workflow purposes.

### C-024 Section Dividers
- Sections may have a trailing divider line (`---`); dividers are preserved during rewrites.

---

## 4. Open Questions Management

### C-030 Table Schema
- The Open Questions table has a fixed schema: Question ID | Question | Date | Answer | Section Target | Resolution Status.
- Table location is identified by `<!-- table:open_questions -->` marker.
- The table header and separator rows are validated on each run; mismatches cause errors.

### C-031 Question Generation
- When a blank section has no open questions, the LLM is prompted to generate clarifying questions.
- Generated questions include: question text, target section ID (may differ from current section), and rationale.
- If Phase 1: Generated questions are constrained to Phase 1 section IDs only.
- If Phase 2: Generated questions can target Phase 2 section IDs.

### C-032 Question Deduplication
- New questions are compared against existing questions using normalized text (case/space-insensitive) + section target.
- Duplicate questions are not inserted.

### C-033 Question Insertion
- New questions are assigned sequential IDs (Q-001, Q-002,... based on highest existing ID).
- Questions are inserted with default status "Open" and empty answer field.
- Questions are added to the table end (before trailing divider, if present).

### C-034 Question Resolution
- After LLM integrates answers into a section, the corresponding questions are marked "Resolved" in the table.
- Questions must have a non-empty Answer field and status "Open" or "Deferred" to be considered "answered."
- Questions with status "Pending", empty answer, or "-" are not considered answered.

### C-035 Question Status Values
- **Open**: Question is awaiting an answer.
- **Deferred**: Question is acknowledged but intentionally deferred.
- **Resolved**: Question has been answered and integrated into requirements.
- Phase 1 only requires Open questions to be resolved; Phase 2 requires both Open and Deferred to be resolved.

---

## 5. LLM Integration

### C-040 LLM Model Configuration
- Uses Claude (Sonnet 4.5) by default for question generation and answer integration.
- Model and max token limits are configurable in config.py.
- Requires ANTHROPIC_API_KEY environment variable to be set.

### C-041 Question Generation Prompts
- LLM is prompted with section context (current body text) and asked to generate clarifying questions.
- Prompts are constrained to ensure JSON output with expected keys: question, section_target, rationale.
- LLM output is parsed for JSON; if JSON is not extracted, generation fails.

### C-042 Answer Integration Prompts
- LLM is provided the current section text and a list of answered questions.
- LLM is prompted to rewrite the section incorporating answers in requirements-style language.
- LLM is instructed to: keep language crisp, remove placeholder wording, flag conflicts rather than guess.
- Output is treated as untrusted; any remaining markers or improper structure are removed.

### C-043 Sanitization of LLM Output
- LLM output is sanitized before insertion into the document.
- Sanitization removes: accidental markers (section, lock, table), comments, markdown headers, empty lines beyond singles.
- Section-specific rules apply:
  - **assumptions**: Removes constraint classification lines; deduplicates similar assumptions.
  - **constraints**: Preserves only "### Technical/Operational/Resource Constraints" subsection headers.

---

## 6. Git Integration

### C-050 Pre-Flight Check
- Before processing, the system checks if the git working tree is clean.
- If uncommitted changes exist and `--no-commit` is not set, processing halts with an error.
- `--no-commit` flag allows processing without requiring a clean tree.

### C-051 Commit & Push
- After processing, if changes were made and `--dry-run` is not set:
  - Changes are committed with message: `"requirements: automation pass (<phase>)"`.
  - Only `docs/requirements.md` is committed; unexpected modified files will stop the commit.
  - Changes are pushed to origin if commit succeeds.

### C-052 Backup Files
- Before writing updates, a backup copy is created in the system temp directory (`/tmp/requirements_automation_backups/` or equivalent).
- Backup filename: `requirements.md.<YYYYMMDD_HHMMSS>.bak`.
- Backup files are not deleted by the system; they accumulate over time.

---

## 7. CLI & Execution

### C-060 Command-Line Interface
- Accepts arguments: `--template`, `--doc`, `--repo-root`, `--dry-run`, `--no-commit`, `--log-level`.
- `--template`: Path to template file (used to create doc if missing).
- `--doc`: Path to requirements document to process.
- `--repo-root`: Repository root for git operations.
- `--dry-run`: Process without writing to disk or committing.
- `--no-commit`: Write to disk but don't commit/push.
- `--log-level`: Logging verbosity (DEBUG, INFO, WARNING, ERROR).

### C-061 Bootstrap from Template
- If the requirements document does not exist, it is automatically created by copying the template file.
- Template file must exist; missing template raises an error.
- Bootstrap occurs before phase processing.

### C-062 Output Format
- Exit code 0: Success (no-op or updated).
- Exit code 1: Blocked (human intervention required).
- Exit code 2: Error (file not found, git issues, etc.).
- JSON result printed to stdout with keys: outcome, changed, blocked_reasons.

---

## 8. Execution Guarantees

### C-070 No Partial Writes
- Either all changes for a phase are applied, or none are.
- If an error occurs mid-processing, the on-disk document is not modified.

### C-071 No Side Effects
- Processing does not modify or create files outside of:
  - Backup copies (created in temp directory).
  - Git repository state (commits only `docs/requirements.md`).

### C-072 Idempotency
- Running the same phase twice on an unchanged document produces the same result.
- If document changes between runs, the phase may produce different results (e.g., if questions were answered).

---

## 9. Explicit Non-Goals
The following are NOT supported by the system and should not be implemented without explicit design review:
- Autonomous approvals or sign-offs.
- Code generation or execution.
- Repo-wide changes or multi-file modifications.
- Version tracking or semantic versioning.
- Role-based access control or permission enforcement.
- Real-time collaboration or multi-user editing.
- Custom markdown extensions or preprocessing.

---

## 10. Open Implementation Gaps
The following exist in requirements-automation.py but are incomplete or aspirational:
- Phase 3+ (Requirements Details): Placeholder only; not implemented.
- Phase 4+ (Interfaces, Data, Risks): Placeholder only; not implemented.
- Phase 5+ (Approval Record): Placeholder only; not implemented.
- Version tracking: Not implemented; no version history or increment logic in code.
- Multi-section processing per run: Current design processes one phase per run.

---

## Change Policy
This document is the authoritative source of truth for system capabilities.
Updates require explicit review and documentation of intent.
