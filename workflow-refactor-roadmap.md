# Workflow Refactor & Integration Loop Roadmap

## Purpose
Defines planned architectural changes and future capabilities.

This document is aspirational.

---

## 1. Problem Statement
Current implementation is correct but tightly coupled to phases and document semantics.

---

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
