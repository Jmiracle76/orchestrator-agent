# Requirements Document

<!-- ============================================================================ -->
<!-- TEMPLATE BASELINE - Reusable Requirements Template                          -->
<!-- ============================================================================ -->
<!-- This is a clean, canonical template for requirements documentation          -->
<!-- To use: Copy this file to your project and replace placeholder content      -->
<!-- For agents: This is a "Template Baseline" - see special rules below         -->
<!-- ============================================================================ -->

<!-- This document is authored by humans and reviewed by the Requirements Agent -->
<!-- It serves as the single source of truth for what the project must deliver -->
<!-- Status values: Draft | Under Review | Approved -->

**Project:** [Project Name - Replace with your project name]  
**Version:** 0.0  
**Status:** Draft  
**Last Updated:** [Date]  
**Approved By:** Pending  
**Approval Date:** Pending

---

## 1. Document Control

<!-- This section tracks the lifecycle of this requirements document -->

| Field | Value |
|-------|-------|
| Document Status | Draft |
| Current Version | 0.0 |
| Last Modified | [Date] |
| Modified By | [Author] |
| Approval Status | Draft |
| Approved By | Pending |
| Approval Date | Pending |

### Version History

<!-- Requirements Agent updates this section when integrating answers in integrate_answers mode -->
<!-- Each integration must document: which Question IDs were integrated, which sections were updated, and nature of changes -->

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.0 | [Date] | Template | Template baseline - clean reusable starting point |

---

## 2. Problem Statement

<!-- Describe the problem being solved, not the solution -->
<!-- Must be specific, observable, and defensible -->
<!-- Focus on: What is broken? What pain exists? What is the measurable impact? -->

[Describe the problem your project addresses. Focus on the observable problem and measurable impact, not the solution. What is currently broken or missing? What pain does it cause? Who is affected?]

---

## 3. Goals and Objectives

### Primary Goals

<!-- What must this project achieve to be considered successful? -->
<!-- Each goal should be specific and measurable -->

1. [Primary goal 1 - must be specific and measurable]
2. [Primary goal 2]

### Secondary Goals

<!-- What would be nice to achieve but is not critical? -->
<!-- These may be deferred if constraints require -->

1. [Secondary goal 1 - nice to have but not critical]
2. [Secondary goal 2]

---

## 4. Non-Goals

<!-- Explicitly state what this project will NOT do -->
<!-- These are binding exclusions to prevent scope creep -->
<!-- Be specific to avoid ambiguity -->

1. [Non-goal 1 - what this project explicitly will NOT do]
2. [Non-goal 2]

---

## 5. Stakeholders and Users

<!-- Identify all stakeholders and their roles/interests -->

### Primary Stakeholders

| Stakeholder | Role | Interest/Need | Contact |
|-------------|------|---------------|---------|
| [Stakeholder name] | [Role] | [Their interest/need] | [Contact info] |

### End Users

| User Type | Characteristics | Needs | Use Cases |
|-----------|----------------|-------|-----------|
| [User type] | [Key characteristics] | [Primary needs] | [Main use cases] |

---

## 6. Assumptions

<!-- Testable or falsifiable statements assumed to be true -->
<!-- Each assumption should be validated before or during implementation -->

1. [Assumption 1 - testable statement assumed to be true]
2. [Assumption 2]

---

## 7. Constraints

### Technical Constraints

<!-- List technical limitations, platform requirements, compatibility needs -->

- [Technical constraint 1]
- [Technical constraint 2]

### Business Constraints

<!-- List budget, timeline, regulatory, or organizational constraints -->

- [Business constraint 1]
- [Business constraint 2]

### Resource Constraints

<!-- List limitations on people, time, budget, or infrastructure -->

- [Resource constraint 1]
- [Resource constraint 2]

---

## 8. Functional Requirements

<!-- Define what the system must DO -->
<!-- Each requirement should be specific, testable, and trace to a goal -->
<!-- Use format: FR-XXX: [Requirement Name] -->

### FR-001: [Requirement Name]

**Description:** [Clear description of what the system must do]  
**Priority:** [High | Medium | Low]  
**Source:** [Stakeholder or document reference]

**Acceptance Criteria:**
- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]

<!-- Add additional functional requirements as FR-002, FR-003, etc. -->

---

## 9. Non-Functional Requirements

<!-- Define how the system must perform -->
<!-- Must include measurable targets or acceptance criteria -->
<!-- Use format: NFR-XXX: [Category] - [Requirement Name] -->

### NFR-001: [Category] - [Requirement Name]

**Description:** [Clear description of the quality attribute or constraint]  
**Priority:** [High | Medium | Low]  
**Measurement Criteria:** [How this will be measured or validated]

**Acceptance Criteria:**
- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]

<!-- Add additional non-functional requirements as NFR-002, NFR-003, etc. -->
<!-- Common categories: Reliability, Performance, Security, Usability, Maintainability, Scalability -->

---

## 10. Interfaces and Integrations

### External Systems

<!-- List all external systems this project integrates with -->

| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|
| [System name] | [Why integration needed] | [API, File, DB, etc.] | [What must be available] |

### Data Exchange

<!-- Describe data flows between systems -->

| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|
| [Integration name] | [In/Out/Both] | [JSON, XML, CSV, etc.] | [Real-time, Batch, etc.] |

---

## 11. Data Considerations

### Data Requirements

<!-- List data entities and their attributes -->

- [Data entity 1: description, type, format, precision]
- [Data entity 2: description, type, format, precision]

### Privacy & Security

<!-- Address data privacy and security requirements -->

- [Privacy consideration 1]
- [Security consideration 1]

### Data Retention

<!-- Define how long data is kept and where -->

- [Retention policy 1: what data, how long, where stored]
- [Retention policy 2]

---

## 12. Risks and Open Issues

### Identified Risks

<!-- Requirements Agent updates this section during review -->
<!-- Risks should identify quality gaps, ambiguities, or potential project obstacles -->
<!-- Do NOT delete resolved risks - update their mitigation status -->

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| R-001 | [Initial template state - no risks identified yet] | Low | Low | Risks will be identified by Requirements Agent during first review | Requirements Agent |

### Open Questions

<!-- ANSWER INTEGRATION WORKFLOW -->
<!-- This section captures questions that require clarification before approval -->
<!-- 
HUMAN WORKFLOW:
1. Requirements Agent identifies questions during review and adds them to this table with empty Answer field
2. Human (Product Owner or stakeholder) provides answer by filling in the Answer field
3. Human invokes Requirements Agent: tools/invoke_requirements_agent.py
4. Script automatically detects answered-but-unintegrated questions and runs in integrate_answers mode
5. Agent integrates the answer into appropriate section(s) and marks question as "Resolved"
6. Agent updates Revision History to document the integration

MODE DETECTION (Automatic):
- Script scans this table for questions with:
  * Non-empty Answer field (human has provided answer)
  * Resolution Status is NOT "Resolved" (not yet integrated)
- If such questions exist → integrate_answers mode
- Otherwise → review_only mode
- No manual mode selection required

AGENT WORKFLOW (integrate_answers mode only):
- Scan for questions with non-empty Answer fields and non-Resolved status
- Integrate answer content into appropriate sections (Sections 2-11, 13-14)
- Add source traceability reference (e.g., "Source: Product Owner (Answer to Q-003)")
- Mark question as "Resolved" with integration reference
- Update Revision History to document integration activity
- Downgrade (not delete) mitigated risks, add new risks if answers introduce them

APPROVAL GATE:
- This table must be empty OR all questions must have "Resolved" status before document can be approved
- Requirements Agent will recommend "Pending - Revisions Required" if any questions remain "Open"

CANONICAL TABLE SCHEMA (IMMUTABLE):
- The Open Questions table MUST always use this exact schema with columns in this order:
  | Question ID | Question | Asked By | Date | Answer | Resolution Status |
- All six columns are REQUIRED and MUST be present
- The Answer column may be empty for new/unanswered questions
- The Resolution Status must be one of: "Open", "Resolved", or "Deferred"
- Column order MUST NOT be changed
- Columns MUST NOT be removed, renamed, or replaced
- The invocation script will detect and auto-repair schema violations before agent execution
- Any schema repairs are logged in git diff and Revision History
-->

| Question ID | Question | Asked By | Date | Answer | Resolution Status |
|-------------|----------|----------|------|--------|-------------------|
| - | No questions yet - Requirements Agent will populate this during first review | - | - | - | - |

---

## 13. Success Criteria and Acceptance

<!-- This section defines measurable success criteria for the project -->
<!-- Must be specific, measurable, achievable, relevant, and time-bound (SMART) -->
<!-- This section MUST be populated before document can be approved -->

### Project Success Criteria

<!-- Define the overall measures of project success -->

1. [Success criterion 1 - must be specific, measurable, and define what "done" means]
2. [Success criterion 2]

### Acceptance Criteria

<!-- These are the criteria that must be met for the project to be considered complete -->

- [ ] [Acceptance criterion 1 - specific and measurable]
- [ ] [Acceptance criterion 2]
- [ ] All functional requirements have passing acceptance tests
- [ ] All non-functional requirements meet specified measurement criteria
- [ ] Product Owner has validated system behavior meets expectations
- [ ] No High or Medium severity defects remain open
- [ ] Documentation is complete

---

## 14. Out of Scope

<!-- Explicitly state what will NOT be delivered in this project -->
<!-- These are binding exclusions documented to prevent scope creep -->

The following items are explicitly OUT OF SCOPE for this project:

1. [Out of scope item 1 - be specific about what will NOT be delivered]
2. [Out of scope item 2]

---

## 15. Approval Record

<!-- This section tracks approval workflow and status -->
<!-- Only the Product Owner can set status to "Approved" -->
<!-- Requirements Agent can only recommend "Ready for Approval" or "Pending - Revisions Required" -->

| Field | Value |
|-------|-------|
| Current Status | Draft |
| Recommended By | Pending |
| Recommendation Date | Pending |
| Approved By | Pending |
| Approval Date | Pending |
| Review Notes | Template baseline - not ready for approval until populated with project-specific content |

### Approval Status Definitions

- **Draft:** Initial authoring in progress, not ready for review
- **Ready for Approval:** Requirements Agent has validated all quality criteria are met, all open questions resolved, no High/Medium risks remain, Success Criteria populated - awaiting Product Owner approval
- **Approved:** Product Owner has approved requirements as complete and accurate - triggers handoff to Planning Agent
- **Pending - Revisions Required:** Quality issues, open questions, or unmitigated risks prevent approval recommendation

### Approval Criteria

For the Requirements Agent to recommend "Ready for Approval", ALL of the following must be true:

1. [ ] All 15 sections are present and populated with project-specific content
2. [ ] All Open Questions are marked "Resolved" (or Open Questions table is empty)
3. [ ] No High or Medium severity risks remain unmitigated
4. [ ] Success Criteria section (Section 13) is populated with measurable criteria
5. [ ] All functional requirements have testable acceptance criteria
6. [ ] All non-functional requirements have measurable targets
7. [ ] No contradictory requirements exist
8. [ ] Document is internally consistent

### Template Baseline Safeguards

**IMPORTANT:** This document is identified as a "Template Baseline" (Version 0.0).

Requirements Agent special rules for Template Baseline documents (HARD, NOT ADVISORY):
- **Mode is EXTERNALLY ENFORCED:** Template Baseline detection triggers `template_baseline_review` mode automatically
- **First agent interaction** with a Template Baseline MUST be in `template_baseline_review` mode
- **Read-only except Risks and Open Questions:** ALL content sections (2-14) must remain as placeholders
- **No deletions allowed:** Template structure and placeholders MUST be preserved
- **Cannot recommend approval:** Template Baselines CANNOT be recommended for approval
- **Structural preservation is mandatory:** Any deviation is a SYSTEM ERROR, not an agent choice
- **Approval gates are INACTIVE** until at least ONE of the following occurs:
  - At least one Open Question exists (indicating human engagement)
  - At least one requirement is defined (indicating project-specific content)
  - Version number advances beyond 0.0 (indicating active development)
- Template Baselines are intended for reuse and must not progress to approval without project-specific content

**CRITICAL:** Any attempt to modify content sections, delete placeholders, or recommend approval for a Template Baseline will be blocked by the invocation script's structural validation.

---

**END OF REQUIREMENTS DOCUMENT**
