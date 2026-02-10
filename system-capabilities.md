# Requirements Automation – System Capabilities (Source of Truth)

## Purpose
This document defines the authoritative functional capabilities of the requirements automation system **as it exists today**.
Anything listed here is intentional behavior and must not regress without an explicit change decision.

This document is descriptive, not aspirational.

---

## 1. Core Execution Model

### C-001 Deterministic Operation
- Given the same document state and inputs, the script produces deterministic results.
- No probabilistic edits are allowed outside explicitly generated section content.

### C-002 Single-Document Ownership
- The system modifies only `docs/requirements.md`.
- No other repository files may be created, modified, or deleted.
- Temporary and backup files are stored outside the git repository.

### C-003 Safe Failure Behavior
- On error:
  - No partial writes occur
  - The document remains unchanged
  - Clear errors are emitted

---

## 2. Document Structure Enforcement

### C-010 Section Marker Integrity
- All edits are scoped strictly to `<!-- section:<id> -->` spans.
- Section markers are never deleted or moved.

### C-011 Placeholder Preservation
- `<!-- PLACEHOLDER -->` remains until real content is written.

### C-012 Section Lock Enforcement
- Locked sections are never modified.

---

## 3. Open Questions Management

### C-020 Table Ownership
- Open Questions table schema is immutable and automation-owned.

### C-021 Question Generation
- Blank sections with no open questions trigger question generation.

### C-022 Deduplication
- Questions are deduped by normalized text + target.

### C-023 Resolution
- Integrated answers mark questions resolved atomically.

---

## 4. Section Processing

### C-030 Ordered Processing
- Sections are processed in document order.
- One section per run.

### C-031 Phase 1 (Complete)
- Intent & scope sections fully supported.

### C-032 Phase 2 (Near Complete)
- Assumptions & constraints supported.

---

## 5. LLM Interaction

### C-040 Sanitized Output
- All LLM output is treated as untrusted input.

### C-041 Scoped Context
- LLM only sees the active section context.

---

## 6. Metadata & Versioning

### C-050 Version Control
- Version increments only on section completion.

### C-051 Version History
- Every content change is logged.

### C-052 Bootstrap Support
- Explicit bootstrap flags only.

---

## 7. Explicit Non-Goals
- No autonomous approvals
- No code execution
- No repo-wide changes

---

## 8. Change Policy
This document is the source of truth.
