# Workflow Refactor & Integration Loop Roadmap

This document converts the proposed refactor and architecture changes into a concrete, reviewable set of GitHub Issues. Each issue is intentionally scoped, ordered, and phrased so it can be handed directly to Codex or a human contributor without ambiguity.

---

## Epic: Unified LLM Integration Workflow Engine

**Goal:** Replace phase-specific logic with a reusable, document-driven workflow engine that iterates sections deterministically using a single LLM integration loop.

**Out of scope (for this epic):** New content domains, advanced agents, UI, or multi-doc orchestration.

---

## Issue 1: Add `doc_type` Metadata Marker to Templates

**Type:** Enhancement  
**Priority:** High (Foundation)  
**Estimated Effort:** 4-6 hours  

**Description:**
Introduce an explicit `doc_type` metadata marker in document templates to drive LLM reasoning style and handler selection. This replaces implicit filename-based detection and enables the same engine to process multiple document types (requirements, research, planning, test specs) with different LLM behavior profiles.

**Current State:**
- No explicit document type metadata exists
- Document type is implicitly assumed based on filename or hardcoded phase logic
- `config.py` has `PHASES` dict mapping phase names to section lists, but no doc_type concept

**Implementation Plan:**

1. **Update Template Format** (`docs/templates/requirements-template.md`)
   - Add metadata header at top of template:
     ```md
     <!-- meta:doc_type value="requirements" -->
     <!-- meta:doc_format value="markdown" version="1.0" -->
     ```
   - Place metadata block before existing content
   - Document metadata fields in template README

2. **Add Metadata Parser** (new function in `parsing.py`)
   - Create `extract_metadata(lines: List[str]) -> Dict[str, str]`
   - Parse `<!-- meta:<key> value="<val>" -->` or `<!-- meta:<key> -->\n- **<Key>:** <value>` formats
   - Return dict with keys: `doc_type`, `doc_format`, `version`
   - Handle missing or malformed metadata gracefully

3. **Update config.py**
   - Add `SUPPORTED_DOC_TYPES = ["requirements", "research", "planning"]`
   - Add `DEFAULT_DOC_TYPE = "requirements"` (fallback for legacy docs)
   - Add metadata marker regex: `META_MARKER_RE = re.compile(r"<!--\s*meta:(?P<key>[a-z_]+)(?:\s+value=\"(?P<value>[^\"]+)\")?\s*-->")`

4. **Update CLI** (`cli.py`)
   - Extract metadata early: `metadata = extract_metadata(lines)` after reading doc
   - Validate doc_type: `doc_type = metadata.get("doc_type", DEFAULT_DOC_TYPE)`
   - If doc_type not in `SUPPORTED_DOC_TYPES`, fail with clear error
   - Pass `doc_type` to runner: `run_phase(phase, lines, llm, args.dry_run, doc_type=doc_type)`

5. **Backward Compatibility**
   - If no metadata marker found, use `DEFAULT_DOC_TYPE` and log warning
   - Existing `docs/requirements.md` continues to work (uses fallback)
   - Migration: add metadata marker to existing docs manually or via script

**Acceptance Criteria:**

* ✅ Template includes well-formed meta marker with `doc_type` field
* ✅ Parser function `extract_metadata()` reliably extracts doc_type from marker
* ✅ Parser handles both inline (`value="..."`) and block (`- **Key:** value`) formats
* ✅ CLI validates doc_type against `SUPPORTED_DOC_TYPES` list
* ✅ Missing or invalid `doc_type` produces clear error with suggested values
* ✅ Legacy documents without metadata marker continue working (use default fallback)
* ✅ Metadata extraction tested with unit tests (valid, missing, malformed cases)

**Dependencies:**
- None (foundation issue)

**Breaking Changes:**
- None in this issue (fallback preserves compatibility)
- Future issues will require templates to include metadata

**Testing:**
- Unit tests for `extract_metadata()` with various inputs
- Integration test: template with metadata → parser extracts correctly
- Integration test: legacy doc without metadata → uses fallback, logs warning

**Notes:**
- This becomes the primary routing signal for LLM behavior profiles (Issue 6)
- Enables future doc types without engine changes (research notes, test specs, etc.)
- Metadata version field supports future format migrations

---

## Issue 2: Introduce Workflow Order Manifest in Templates

**Type:** Enhancement  
**Priority:** High (Foundation)  
**Estimated Effort:** 6-8 hours  

**Description:**
Replace hard-coded phase sequencing (`PHASE_ORDER` and `PHASES` in `config.py`) with a template-declared workflow order. This allows different document types to define their own progression order without code changes. The workflow order becomes the single source of truth for section processing sequence.

**Current State:**
- Section order is hardcoded in `config.py`: `PHASES` dict maps phase names to section lists
- `PHASE_ORDER` list defines phase sequence: `["phase_1_intent_scope", "phase_2_assumptions_constraints", ...]`
- `runner.choose_phase()` iterates `PHASE_ORDER` and uses phase-specific validators
- Adding new sections or reordering requires code changes
- Different doc types cannot have different workflows

**Implementation Plan:**

1. **Template Format Definition**
   - Add workflow order block to template header (after metadata):
     ```md
     <!-- workflow:order
     problem_statement
     goals_objectives
     stakeholders_users
     success_criteria
     assumptions
     constraints
     requirements
     interfaces_integrations
     data_considerations
     risks_open_issues
     review_gate:coherence_check
     approval_record
     -->
     ```
   - One section ID per line (whitespace-trimmed)
   - Support special targets: `review_gate:<name>` for review-only passes
   - Empty lines and `#` comments ignored

2. **Add Workflow Parser** (new function in `parsing.py`)
   - Create `extract_workflow_order(lines: List[str]) -> List[str]`
   - Find `<!-- workflow:order` marker, extract section IDs until `-->`
   - Return ordered list of section IDs
   - Validate: no duplicates, no empty IDs, proper format

3. **Update config.py**
   - Keep `PHASES` dict for reference but mark as deprecated
   - Add `SPECIAL_WORKFLOW_PREFIXES = ["review_gate:"]` (for validation)
   - Document migration: old phase-based → new section-based workflow

4. **Update Validators** (`validators.py`)
   - Deprecate `validate_phase_1_complete()` and `validate_phase_2_complete()`
   - Add new `validate_section_complete(section_id: str, lines: List[str]) -> Tuple[bool, List[str]]`
     - Check if section exists
     - Check if locked (skip if locked)
     - Check if has PLACEHOLDER token (incomplete if present)
     - Check if has open questions in "Open" status (incomplete if questions exist)
     - Return (complete: bool, reasons: List[str])

5. **Update Runner** (`runner.py`)
   - Modify `choose_phase()` → `choose_next_target(lines: List[str], workflow_order: List[str]) -> Tuple[str, bool]`
   - Iterate `workflow_order` instead of `PHASE_ORDER`
   - Use new `validate_section_complete()` instead of phase-specific validators
   - Return first incomplete section ID, or last ID if all complete
   - Special handling: if target starts with `review_gate:`, mark as special

6. **Update CLI** (`cli.py`)
   - Extract workflow order: `workflow_order = extract_workflow_order(lines)`
   - Validate workflow order references only existing section IDs (or review gates)
   - Pass workflow_order to runner: `next_target, all_complete = choose_next_target(lines, workflow_order)`
   - Use `next_target` instead of `phase` throughout

7. **Validation & Error Handling**
   - Missing workflow marker: Error with clear message (no fallback)
   - Unknown section ID in workflow: Error listing valid sections found in doc
   - Duplicate section IDs in workflow: Error
   - Malformed workflow block: Error with line number

**Acceptance Criteria:**

* ✅ Template includes well-formed `<!-- workflow:order -->` block
* ✅ Parser function `extract_workflow_order()` extracts ordered section ID list
* ✅ Parser handles comments (`#`) and empty lines gracefully
* ✅ `choose_next_target()` respects declared order exactly (no reordering or phase logic)
* ✅ Unknown section IDs in workflow produce validation error listing valid sections
* ✅ Duplicate section IDs produce clear error
* ✅ Special targets (`review_gate:*`) are recognized and not validated as regular sections
* ✅ `validate_section_complete()` correctly identifies incomplete sections (PLACEHOLDER, open questions, missing)
* ✅ Locked sections are skipped (marked complete) during iteration
* ✅ Missing workflow order marker produces clear error (breaking change, no fallback)

**Dependencies:**
- Issue 1 (doc_type metadata) - should be completed first for consistency

**Breaking Changes:**
- ⚠️ **BREAKING**: Templates without `<!-- workflow:order -->` will fail validation
- ⚠️ **BREAKING**: `choose_phase()` replaced with `choose_next_target()` (different signature)
- Migration required: add workflow block to all existing templates and documents

**Testing:**
- Unit tests for `extract_workflow_order()`: valid, missing, malformed, duplicates
- Unit tests for `validate_section_complete()`: locked, placeholder, open questions, complete
- Integration test: document with workflow order → correct section selected
- Integration test: all sections complete → returns last section
- Integration test: missing workflow order → clear error

**Migration Support:**
- Create migration script: `tools/migrate_workflow_order.py`
  - Reads existing doc
  - Infers workflow order from current `PHASES` mapping for doc_type="requirements"
  - Inserts workflow block after metadata
  - Validates result
- Document migration steps in `docs/migration-guide.md`

**Notes:**
- This decouples workflow logic from code, enabling new doc types without engine changes
- Review gates become first-class workflow targets (Issue 7)
- Future: support conditional workflows (if/else based on section state) - out of scope for this issue

---

## Issue 3: Implement `WorkflowRunner` Core Loop

**Type:** Refactor  
**Priority:** Critical (Core Architecture)  
**Estimated Effort:** 8-12 hours  

**Description:**
Create a single, reusable workflow runner that replaces phase-specific branching logic. The `WorkflowRunner` iterates workflow targets in template-declared order, executes only the first incomplete target per run, and stops deterministically. This is the central orchestration component that eliminates hardcoded phase logic.

**Current State:**
- `runner.py` has two functions: `choose_phase()` and `run_phase()`
- `choose_phase()` iterates `PHASE_ORDER` via hardcoded phase-specific validators
- `run_phase()` dispatches to phase-specific processors: `process_phase_1()`, `process_phase_2()`, or `process_placeholder_phase()`
- `cli.py` orchestrates: calls `choose_phase()`, then `run_phase()`, then handles results
- No abstraction layer; each phase has unique logic in `phases/phase1.py` and `phases/phase2.py`

**Implementation Plan:**

1. **Create WorkflowRunner Class** (new file: `runner_v2.py`)
   ```python
   class WorkflowRunner:
       def __init__(self, lines: List[str], llm: LLMClient, doc_type: str, workflow_order: List[str], handler_registry: HandlerRegistry):
           # Store document state, LLM client, workflow config
       
       def run_once(self, dry_run: bool) -> WorkflowResult:
           # Execute first incomplete workflow target, return result
       
       def run_until_blocked(self, dry_run: bool, max_steps: int = 10) -> List[WorkflowResult]:
           # Execute workflow targets until blocked or complete (--max-steps N support)
   ```

2. **Define WorkflowResult Model** (`models.py`)
   ```python
   @dataclass(frozen=True)
   class WorkflowResult:
       target_id: str              # Section or review gate ID processed
       action_taken: str           # "question_gen", "integration", "review", "skip_locked", "no_action"
       changed: bool               # Document modified?
       blocked: bool               # Needs human intervention?
       blocked_reasons: List[str]  # Why blocked (e.g., "unanswered questions")
       summaries: List[str]        # Human-readable action descriptions
       questions_generated: int    # Count of new questions
       questions_resolved: int     # Count of resolved questions
   ```

3. **Implement Core Loop Logic**
   - `run_once()` algorithm:
     1. Iterate workflow_order from start
     2. For each target_id:
        - Get section state (locked, placeholder, has_questions, has_answers)
        - If locked → skip, continue to next
        - If review_gate → call review handler (Issue 7), return result
        - If complete (no placeholder, no open questions) → skip, continue
        - If incomplete → call section handler, return result
     3. If all targets complete → return result with target_id=workflow_order[-1], action="complete"

4. **Section State Analysis** (helper method)
   ```python
   def _get_section_state(self, target_id: str) -> SectionState:
       # Extract section span, lock state, placeholder presence, questions
       # Return structured state object for handler decision-making
   ```

5. **Handler Dispatch** (placeholder for Issue 4)
   ```python
   def _execute_section(self, target_id: str, state: SectionState) -> WorkflowResult:
       # Get handler config from registry (Issue 4)
       # For now: call temporary adapter to old phase logic
       # Future: unified handler (Issue 5)
   ```

6. **Update CLI Integration** (`cli.py`)
   - Replace `choose_phase()` and `run_phase()` with WorkflowRunner:
     ```python
     runner = WorkflowRunner(lines, llm, doc_type, workflow_order, handler_registry=None)  # registry added in Issue 4
     result = runner.run_once(args.dry_run)
     ```
   - Update result handling to use `WorkflowResult` instead of tuple return
   - Keep git commit message: use `result.target_id` instead of `phase`

7. **Temporary Adapter to Old Phase Logic** (for gradual migration)
   - Keep `phases/phase1.py` and `phases/phase2.py` temporarily
   - WorkflowRunner dispatches to old phase processors based on target_id mapping
   - Map section IDs → phases: `{"problem_statement": "phase_1_intent_scope", ...}`
   - Call old `process_phase_1(lines, llm, dry_run)`, adapt result to `WorkflowResult`

8. **Support --max-steps Flag** (optional batch execution)
   - Add `--max-steps N` CLI argument
   - `run_until_blocked()` loops up to N times or until blocked/complete
   - Useful for automated CI pipelines processing multiple sections

**Acceptance Criteria:**

* ✅ `WorkflowRunner` class exists in `runner_v2.py` with `run_once()` method
* ✅ `WorkflowResult` dataclass defined with all required fields
* ✅ Runner iterates workflow_order from start, processes first incomplete section
* ✅ Locked sections are skipped (not counted as incomplete)
* ✅ Completed sections (no placeholder, no open questions) are skipped
* ✅ Runner stops after processing one section (deterministic single-step execution)
* ✅ No phase-specific branching in `main()` or runner core loop
* ✅ Runner accepts: parsed workflow order, document state (lines), handler registry (stub for now)
* ✅ `--max-steps N` flag supported for batch execution (optional enhancement)
* ✅ Temporary adapter successfully calls old phase logic for backward compatibility
* ✅ CLI updated to use WorkflowRunner; existing workflows continue working
* ✅ Git commit messages use target_id instead of phase name

**Dependencies:**
- Issue 2 (workflow order manifest) - required for workflow_order input
- Issue 1 (doc_type metadata) - required for doc_type parameter

**Breaking Changes:**
- ⚠️ **BREAKING**: `runner.py` functions `choose_phase()` and `run_phase()` deprecated (but kept for adapter)
- Internal API change: CLI uses WorkflowRunner instead of direct function calls
- External behavior unchanged (adapter maintains compatibility)

**Testing:**
- Unit test: empty workflow → result with action="complete"
- Unit test: workflow with one incomplete section → processes that section
- Unit test: workflow with locked section → skips locked, processes next
- Unit test: all sections complete → returns last target, action="complete"
- Unit test: `run_until_blocked()` with max_steps=3 → stops after 3 iterations or blocked
- Integration test: existing requirements.md document → processes correctly via adapter
- Integration test: git commit message uses target_id instead of phase

**Refactoring Note:**
- This issue introduces the new architecture but temporarily adapts to old phase logic
- Issues 4-5 will replace the adapter with true unified handlers
- Old phase files (`phase1.py`, `phase2.py`) marked deprecated, removed after Issue 5

**Performance:**
- Runner re-iterates workflow_order from start each run (simple, deterministic)
- For long workflows (>50 sections), consider caching section states (future optimization)
- Current design optimizes for correctness over speed (acceptable for human-in-loop workflows)

**Notes:**
- Single-step execution maintains determinism and debuggability
- `--max-steps` enables batch mode without losing auditability
- Review gates become first-class targets (handled via registry in Issue 7)
- Future: support workflow checkpoints/resume (out of scope)

---

## Issue 4: Create Section Handler Registry

**Type:** Architecture  
**Priority:** High (Enables Flexibility)  
**Estimated Effort:** 10-14 hours  

**Description:**
Introduce a registry that maps `(doc_type, section_id)` → handler configuration. This decouples section processing logic from code, allowing new document types and section behaviors to be defined via YAML configuration files without engine changes. Handlers define how sections are processed (LLM interaction mode, output format, validation rules).

**Current State:**
- Section processing logic is hardcoded in phase-specific processors (`phase1.py`, `phase2.py`)
- Different sections have different behaviors but no unified configuration:
  - `assumptions`: deduplication + bullet formatting
  - `constraints`: subsection headers preserved
  - `goals_objectives`: subsection support
- No abstraction for "how to process a section" vs "section identity"
- Adding new section types requires code changes

**Implementation Plan:**

1. **Define Handler Config Schema** (YAML format)
   - Create `tools/config/handler_registry.yaml`:
     ```yaml
     # Handler definitions by doc_type and section_id
     requirements:
       problem_statement:
         mode: integrate_then_questions
         output_format: prose
         subsections: false
         dedupe: false
         llm_profile: requirements  # references profiles/ directory
         
       goals_objectives:
         mode: integrate_then_questions
         output_format: bullets
         subsections: true  # supports primary_goals, secondary_goals, non_goals
         dedupe: false
         llm_profile: requirements
         
       assumptions:
         mode: integrate_then_questions
         output_format: bullets
         subsections: false
         dedupe: true  # remove duplicate assumptions after integration
         sanitize_remove: ["constraint classification headers"]
         llm_profile: requirements
         
       constraints:
         mode: integrate_then_questions
         output_format: subsections  # preserve ### Technical/Operational/Resource Constraints
         subsections: false
         dedupe: false
         preserve_headers: ["### Technical Constraints", "### Operational Constraints", "### Resource Constraints"]
         llm_profile: requirements
         
       review_gate:coherence_check:
         mode: review_gate
         scope: all_prior_sections  # review all sections before this gate
         auto_apply_patches: false  # configurable per gate (Issue 7)
         llm_profile: requirements_review
         
     # Default handler for unknown sections
     _default:
       requirements:
         mode: integrate_then_questions
         output_format: prose
         subsections: false
         dedupe: false
         llm_profile: requirements
     ```

2. **Create HandlerRegistry Class** (new file: `handler_registry.py`)
   ```python
   class HandlerRegistry:
       def __init__(self, config_path: Path):
           self.config = self._load_yaml(config_path)  # Parse YAML
           self._validate_schema()  # Ensure required keys present
       
       def get_handler_config(self, doc_type: str, section_id: str) -> HandlerConfig:
           # Lookup (doc_type, section_id) in registry
           # Fall back to _default if not found
           # Return HandlerConfig dataclass
       
       def supports_doc_type(self, doc_type: str) -> bool:
           # Check if doc_type has entries in registry
   ```

3. **Define HandlerConfig Model** (`models.py`)
   ```python
   @dataclass(frozen=True)
   class HandlerConfig:
       section_id: str
       mode: str  # "integrate_then_questions", "questions_then_integrate", "review_gate"
       output_format: str  # "prose", "bullets", "subsections"
       subsections: bool  # allow subsection targeting?
       dedupe: bool  # deduplicate similar content?
       preserve_headers: List[str]  # headers to preserve during rewrite
       sanitize_remove: List[str]  # patterns to remove from LLM output
       llm_profile: str  # profile name (references profiles/ directory, Issue 6)
       auto_apply_patches: bool  # for review gates only
       scope: str  # for review gates: "all_prior_sections", "current_section"
   ```

4. **Handler Modes Defined**
   - **integrate_then_questions**: Default mode (current phase1/phase2 behavior)
     1. If section has answered questions → integrate answers via LLM
     2. If section still blank after integration → generate new questions
     3. If section has open questions but no answers → skip (blocked)
   - **questions_then_integrate**: Alternative mode (future use)
     1. If section blank and no questions → generate questions
     2. If section has answered questions → integrate answers
     3. Never generate questions after integration (single pass)
   - **review_gate**: Special mode (Issue 7)
     1. LLM reviews specified scope (prior sections or current)
     2. Returns pass/fail + optional patches
     3. No direct document mutation

5. **Update WorkflowRunner Integration** (modify `runner_v2.py`)
   - Constructor accepts `handler_registry: HandlerRegistry`
   - `_execute_section()` gets handler config: `config = self.registry.get_handler_config(self.doc_type, target_id)`
   - Dispatch based on `config.mode`:
     - `integrate_then_questions` → call unified integration loop (Issue 5)
     - `review_gate` → call review gate handler (Issue 7)
   - Pass `config` to handler functions for behavior customization

6. **CLI Integration** (`cli.py`)
   - Load registry early: `registry = HandlerRegistry(Path("tools/config/handler_registry.yaml"))`
   - Validate doc_type is supported: `if not registry.supports_doc_type(doc_type): error`
   - Pass registry to WorkflowRunner: `runner = WorkflowRunner(... , handler_registry=registry)`

7. **Validation & Error Handling**
   - Missing `handler_registry.yaml` → error with setup instructions
   - Invalid YAML syntax → error with line number
   - Unknown handler mode → error listing valid modes
   - Missing required keys in config → error listing required keys
   - Unknown doc_type in registry → use `_default` if defined, else error

8. **Backward Compatibility Strategy**
   - Create default `handler_registry.yaml` matching current phase1/phase2 behavior
   - All existing section IDs mapped with current settings
   - Temporary adapter in Issue 3 gradually replaced by registry-driven dispatch

**Acceptance Criteria:**

* ✅ `tools/config/handler_registry.yaml` exists with entries for all current requirements sections
* ✅ `HandlerRegistry` class loads and parses YAML correctly
* ✅ `HandlerConfig` dataclass defined with all configuration fields
* ✅ Registry successfully maps `(doc_type="requirements", section_id="assumptions")` → handler config with `dedupe=true`
* ✅ Registry successfully maps `(doc_type="requirements", section_id="review_gate:coherence_check")` → review gate config
* ✅ Default handler exists for unknown sections (`_default` key)
* ✅ Unknown doc_type falls back to `_default` or produces clear error
* ✅ Invalid YAML produces clear error with file/line info
* ✅ WorkflowRunner uses registry to get handler configs (replaces hardcoded dispatch)
* ✅ All handler modes documented: integrate_then_questions, questions_then_integrate, review_gate
* ✅ Handler config includes LLM profile reference (used in Issue 6)

**Dependencies:**
- Issue 3 (WorkflowRunner) - required for integration point
- Issue 1 (doc_type metadata) - required for doc_type routing

**Breaking Changes:**
- None if default `handler_registry.yaml` matches existing behavior
- New dependency: YAML config file must exist at startup

**Testing:**
- Unit test: load valid handler_registry.yaml → parses correctly
- Unit test: malformed YAML → clear error
- Unit test: lookup known section → returns correct config
- Unit test: lookup unknown section → returns default config
- Unit test: lookup review gate → returns review_gate mode config
- Integration test: WorkflowRunner dispatches to correct handler based on registry
- Integration test: existing requirements.md processes identically to before (via registry)

**Config File Location:**
- Default: `tools/config/handler_registry.yaml` (relative to repo root)
- Allow override via `--handler-config <path>` CLI flag (future enhancement)

**Schema Validation:**
- Add `config/handler_registry_schema.yaml` (JSON Schema format) for validation
- Validate config at load time, fail fast with clear errors
- Consider using `jsonschema` library for validation

**Documentation:**
- Add `docs/handler-registry-guide.md` explaining:
  - Handler modes and when to use each
  - How to add new section types
  - How to define review gates
  - Output format options
  - Sanitization rules

**Future Enhancements (out of scope):**
- Conditional handlers (if section X complete, use handler Y)
- Handler inheritance (section A inherits from default + overrides)
- External handler plugins (Python modules loaded dynamically)

**Notes:**
- YAML chosen over JSON for human-readability and comments
- Registry is immutable after load (no runtime modification)
- LLM profile integration deferred to Issue 6
- Review gate auto-apply logic deferred to Issue 7

---

## Issue 5: Refactor LLM Integration into a Single Reusable Loop

**Type:** Refactor  
**Priority:** Critical (Eliminates Duplication)  
**Estimated Effort:** 12-16 hours  

**Description:**
Unify all LLM interactions (question generation, answer integration) behind a single execution loop driven by handler config. This eliminates duplicate logic in `phase1.py` and `phase2.py`, creates a single code path for all section processing, and ensures consistent LLM behavior. The unified loop is the engine that powers all section handlers (except review gates, which are handled separately in Issue 7).

**Current State:**
- `phases/phase1.py` and `phases/phase2.py` have ~80% duplicate code
- Both phases follow same pattern: check section state → generate questions OR integrate answers
- Differences are minor: section IDs, subsection support, sanitization rules
- `llm.py` has two functions: `generate_questions()` and `integrate_answers()`
- Sanitization logic in `sanitize.py` has section-specific rules hardcoded
- No unified abstraction for "section processing workflow"

**Implementation Plan:**

1. **Create Unified Section Processor** (new file: `section_processor.py`)
   ```python
   class SectionProcessor:
       def __init__(self, llm: LLMClient, lines: List[str], doc_type: str):
           self.llm = llm
           self.lines = lines
           self.doc_type = doc_type
       
       def process_section(self, section_id: str, config: HandlerConfig, dry_run: bool) -> ProcessResult:
           """
           Unified processing loop for a single section based on handler config.
           Handles both integrate_then_questions and questions_then_integrate modes.
           """
           # 1. Extract section state
           # 2. Determine action based on state + config.mode
           # 3. Execute action (generate questions OR integrate answers)
           # 4. Sanitize LLM output based on config
           # 5. Update document lines
           # 6. Return result
   ```

2. **Define ProcessResult Model** (`models.py`)
   ```python
   @dataclass(frozen=True)
   class ProcessResult:
       section_id: str
       action: str  # "generated_questions", "integrated_answers", "skip_locked", "skip_complete", "blocked"
       lines: List[str]  # updated document lines
       changed: bool
       blocked: bool
       blocked_reasons: List[str]
       questions_generated: int
       questions_resolved: int
       summaries: List[str]  # human-readable action descriptions
   ```

3. **Unified Processing Algorithm** (in `process_section()`)
   ```python
   # Step 1: Extract section state
   section_span = find_section_span(section_id, lines)
   is_locked = check_section_lock(section_id, section_span, lines)
   has_placeholder = check_placeholder(section_span, lines)
   open_questions = get_open_questions_for_section(section_id, lines, status=["Open", "Deferred"])
   answered_questions = get_answered_questions_for_section(section_id, lines)
   
   # Step 2: Determine action based on handler mode
   if is_locked:
       return ProcessResult(action="skip_locked", changed=False, blocked=False, ...)
   
   if config.mode == "integrate_then_questions":
       # Current phase1/phase2 behavior
       if answered_questions:
           # Action: Integrate answers into section
           result = self._integrate_answers(section_id, answered_questions, config)
           # After integration, check if still blank
           if still_has_placeholder and not has_open_questions:
               # Generate follow-up questions
               result2 = self._generate_questions(section_id, config)
               # Merge results
           return result
       elif has_placeholder and not open_questions:
           # Action: Generate questions
           return self._generate_questions(section_id, config)
       elif open_questions:
           # Action: Blocked (waiting for answers)
           return ProcessResult(action="blocked", blocked=True, blocked_reasons=["unanswered questions"], ...)
       else:
           # Section complete
           return ProcessResult(action="skip_complete", changed=False, blocked=False, ...)
   
   elif config.mode == "questions_then_integrate":
       # Alternative mode: generate questions first, then integrate (no follow-ups)
       if has_placeholder and not open_questions:
           return self._generate_questions(section_id, config)
       elif answered_questions:
           return self._integrate_answers(section_id, answered_questions, config)
       elif open_questions:
           return ProcessResult(action="blocked", blocked=True, ...)
       else:
           return ProcessResult(action="skip_complete", changed=False, ...)
   ```

4. **Refactor Question Generation** (in `section_processor.py`)
   ```python
   def _generate_questions(self, section_id: str, config: HandlerConfig) -> ProcessResult:
       # Extract section context (current body text)
       section_body = get_section_body(section_id, self.lines)
       
       # Get LLM profile (Issue 6 integration point)
       profile = load_llm_profile(config.llm_profile)  # stub for now
       
       # Call LLM to generate questions
       questions = self.llm.generate_questions(
           section_id=section_id,
           doc_type=self.doc_type,
           section_context=section_body,
           llm_profile=profile,  # added in Issue 6
           allow_subsections=config.subsections
       )
       
       # Deduplicate against existing questions
       new_questions = deduplicate_questions(questions, self.lines)
       
       # Insert into Open Questions table
       updated_lines = insert_questions(new_questions, self.lines)
       
       return ProcessResult(
           action="generated_questions",
           lines=updated_lines,
           changed=True,
           questions_generated=len(new_questions),
           summaries=[f"Generated {len(new_questions)} questions for {section_id}"]
       )
   ```

5. **Refactor Answer Integration** (in `section_processor.py`)
   ```python
   def _integrate_answers(self, section_id: str, questions: List[OpenQuestion], config: HandlerConfig) -> ProcessResult:
       # Extract section context
       section_body = get_section_body(section_id, self.lines)
       
       # Get LLM profile (Issue 6 integration point)
       profile = load_llm_profile(config.llm_profile)  # stub for now
       
       # Call LLM to integrate answers
       new_body = self.llm.integrate_answers(
           section_id=section_id,
           doc_type=self.doc_type,
           current_body=section_body,
           questions=questions,
           llm_profile=profile,  # added in Issue 6
           output_format=config.output_format
       )
       
       # Sanitize LLM output based on config
       sanitized_body = self._sanitize_output(new_body, section_id, config)
       
       # Replace section body (preserving markers, headers, locks)
       updated_lines = replace_section_body(section_id, sanitized_body, self.lines)
       
       # Mark questions as resolved
       updated_lines = resolve_questions([q.id for q in questions], updated_lines)
       
       return ProcessResult(
           action="integrated_answers",
           lines=updated_lines,
           changed=True,
           questions_resolved=len(questions),
           summaries=[f"Integrated {len(questions)} answers into {section_id}"]
       )
   ```

6. **Refactor Sanitization** (update `sanitize.py`)
   ```python
   def sanitize_section_output(body: str, section_id: str, config: HandlerConfig) -> str:
       """
       Sanitize LLM output based on handler config (not hardcoded section rules).
       """
       # Base sanitization (always applied)
       body = remove_markers(body)  # strip <!-- section:... -->, <!-- PLACEHOLDER -->, etc.
       body = collapse_empty_lines(body)
       
       # Config-driven sanitization
       if config.dedupe:
           body = deduplicate_similar_lines(body)
       
       for pattern in config.sanitize_remove:
           if pattern == "constraint classification headers":
               body = remove_constraint_classification_headers(body)
           # Add other patterns as needed
       
       if config.preserve_headers:
           body = ensure_headers_present(body, config.preserve_headers)
       
       return body
   ```

7. **Update WorkflowRunner Integration** (modify `runner_v2.py`)
   - Replace temporary adapter with SectionProcessor:
     ```python
     def _execute_section(self, target_id: str, config: HandlerConfig) -> WorkflowResult:
         if config.mode == "review_gate":
             return self._execute_review_gate(target_id, config)  # Issue 7
         else:
             processor = SectionProcessor(self.llm, self.lines, self.doc_type)
             result = processor.process_section(target_id, config, self.dry_run)
             self.lines = result.lines  # update runner's document state
             return self._convert_to_workflow_result(result)  # adapt ProcessResult → WorkflowResult
     ```

8. **Deprecate Old Phase Files**
   - Mark `phases/phase1.py` and `phases/phase2.py` as deprecated
   - Add deprecation warnings if directly imported
   - Keep files temporarily for reference, remove after testing confirms equivalence
   - Update imports throughout codebase to use SectionProcessor

9. **LLM Client Updates** (`llm.py`)
   - Update `generate_questions()` signature to accept `llm_profile` (stub for Issue 6)
   - Update `integrate_answers()` signature to accept `llm_profile` and `output_format`
   - Add `output_format` handling: "prose" vs "bullets" vs "subsections" influences prompt
   - No major logic changes; primarily signature updates for config integration

**Acceptance Criteria:**

* ✅ `SectionProcessor` class exists in `section_processor.py` with `process_section()` method
* ✅ `ProcessResult` dataclass defined with all result fields
* ✅ Unified loop handles both `integrate_then_questions` and `questions_then_integrate` modes
* ✅ Question generation logic consolidated (no duplication across phases)
* ✅ Answer integration logic consolidated (no duplication across phases)
* ✅ Sanitization driven by `HandlerConfig` (not hardcoded section IDs)
* ✅ LLM never edits document structure directly (all outputs sanitized)
* ✅ All LLM outputs are JSON (questions) or sanitized markdown (integration)
* ✅ Same loop used for all sections across all doc types
* ✅ WorkflowRunner uses SectionProcessor instead of phase-specific functions
* ✅ Old `phase1.py` and `phase2.py` marked deprecated, no longer called
* ✅ Existing requirements.md processes identically to before (verified via tests)

**Dependencies:**
- Issue 4 (handler registry) - required for HandlerConfig input
- Issue 3 (WorkflowRunner) - integration point for section processing

**Breaking Changes:**
- ⚠️ **BREAKING**: `phases/phase1.py` and `phases/phase2.py` deprecated (kept for reference)
- Internal API: `process_phase_1()` and `process_phase_2()` no longer called
- External behavior unchanged (SectionProcessor replicates phase logic exactly)

**Testing:**
- Unit test: integrate_then_questions mode with answered questions → integrates correctly
- Unit test: integrate_then_questions mode with blank section, no questions → generates questions
- Unit test: questions_then_integrate mode → different execution order
- Unit test: locked section → skip without processing
- Unit test: sanitization with dedupe=true → removes duplicates
- Unit test: sanitization with preserve_headers → keeps specified headers
- Integration test: process full requirements.md via SectionProcessor → identical to old phases
- Regression test: run old phase logic vs new SectionProcessor on same doc → bit-identical results

**Performance Considerations:**
- Section state extraction repeated for each section (not cached)
- For docs with >50 sections, consider caching document parsing results
- Current design optimizes for correctness; performance optimizations deferred

**Error Handling:**
- LLM API failure → return ProcessResult with blocked=True, clear error message
- Malformed LLM JSON output → retry once, then fail with diagnostic
- Section not found → error (should be caught earlier by workflow validation)
- Invalid handler mode → error (should be caught at registry load time)

**Logging & Observability:**
- Log each action taken: "Generated 3 questions for section X"
- Log LLM calls: token counts, latency, model used
- Log sanitization applied: "Deduplicated 2 similar lines in section Y"
- Enable debug logging with `--log-level DEBUG`

**Future Enhancements (out of scope):**
- Parallel section processing (multiple sections per run)
- LLM output caching (avoid redundant calls for unchanged context)
- Streaming LLM responses (for better UX in interactive mode)
- Custom handlers via Python plugins (not just config-driven)

**Notes:**
- This issue eliminates the most significant code duplication in the codebase
- Creates foundation for unlimited section types without code changes
- LLM profile integration (Issue 6) slots into the profile parameter
- Review gate handler (Issue 7) follows similar pattern but separate implementation

---

## Issue 6: Introduce Minimal LLM Policy + Style Profiles

**Type:** Enhancement  
**Priority:** Medium (Quality & Consistency)  
**Estimated Effort:** 8-10 hours  

**Description:**
Add lightweight, non-persona profiles injected into every LLM call. Profiles define rules-based guidance for LLM reasoning style, output constraints, and content quality standards. This replaces ad-hoc prompt engineering scattered across phase files with centralized, reusable profile documents. Profiles are markdown files (not YAML) for human readability and easy editing.

**Current State:**
- LLM prompts are hardcoded strings in `llm.py` functions: `generate_questions()` and `integrate_answers()`
- Prompt content is specific to requirements documents (assumes requirements context)
- No abstraction for "how should the LLM reason about this doc type"
- Different doc types (research, planning, test specs) would require duplicating/modifying prompts
- No centralized policy for LLM behavior (tone, constraints, forbidden actions)

**Implementation Plan:**

1. **Profile Directory Structure**
   ```
   profiles/
     base_policy.md         # Always injected into every LLM call
     requirements.md         # Task style for requirements documents
     requirements_review.md  # Task style for requirements review gates
     research.md            # Task style for research documents (future)
     planning.md            # Task style for planning documents (future)
     README.md              # Documentation for profile usage
   ```

2. **Base Policy Content** (`profiles/base_policy.md`)
   ```md
   # Base LLM Policy
   
   ## Core Rules
   1. Never invent facts, data, or technical details not provided in context
   2. Never output document structure markers (<!-- section:... -->, <!-- PLACEHOLDER -->, etc.)
   3. Always output valid JSON when JSON is requested
   4. Flag conflicts or ambiguities; do not resolve them silently
   5. Use crisp, technical language (no marketing speak or filler)
   
   ## Forbidden Actions
   - Do not create or modify section markers
   - Do not create or modify table schemas
   - Do not assume capabilities not explicitly stated
   - Do not combine conflicting requirements without flagging
   
   ## Output Format Rules
   - JSON outputs: strictly valid JSON, no markdown wrappers
   - Prose outputs: markdown-formatted text, no HTML
   - Bullet outputs: dash-prefixed lists, one item per line
   
   ## Reasoning Constraints
   - Prioritize clarity over cleverness
   - Prefer explicit over implicit
   - Avoid redundancy within a single section
   - Preserve user's original phrasing when incorporating answers
   ```

3. **Requirements Task Style** (`profiles/requirements.md`)
   ```md
   # Requirements Document Style
   
   ## Document Purpose
   This is a technical requirements document defining system/project specifications.
   
   ## Language Guidelines
   - Use present tense declarative statements ("The system SHALL...")
   - Avoid conditionals ("might", "could", "possibly")
   - Be specific and measurable where possible
   - Use RFC 2119 keywords appropriately: SHALL, MUST, SHOULD, MAY
   
   ## Question Generation Guidelines
   - Ask about missing critical requirements (security, performance, data)
   - Ask about ambiguous scope boundaries
   - Ask about stakeholder priorities or constraints
   - Do NOT ask questions answerable from existing context
   - Target questions to specific sections (use section_target field)
   
   ## Integration Guidelines
   - Convert answers into requirement-style statements
   - Organize content logically (general → specific)
   - Remove placeholder wording ("TBD", "to be determined")
   - Preserve traceability to original questions where reasonable
   - For assumptions: use bullet format, one assumption per line
   - For constraints: organize under Technical/Operational/Resource subsections
   ```

4. **Requirements Review Style** (`profiles/requirements_review.md`)
   ```md
   # Requirements Review Style
   
   ## Review Objective
   Validate completeness, consistency, and quality of requirements sections.
   
   ## Review Criteria
   - Completeness: Are critical requirements areas covered?
   - Consistency: Do sections contradict each other?
   - Clarity: Are requirements unambiguous and testable?
   - Feasibility: Are there obvious impossibilities or conflicts?
   
   ## Output Format
   Return JSON with:
   - `pass`: boolean (true if no blocking issues)
   - `issues`: array of {"severity": "blocker|warning", "section": "...", "description": "..."}
   - `patches`: array of {"section": "...", "suggestion": "...", "rationale": "..."} (optional)
   
   ## Issue Severity Guidelines
   - **Blocker**: Missing critical sections, contradictory requirements, impossible constraints
   - **Warning**: Ambiguous wording, missing details, inconsistent formatting
   
   ## Patching Guidelines
   - Only suggest patches for objective errors (typos, formatting, obvious omissions)
   - Do not suggest patches for subjective improvements
   - Patches must be unambiguous and mechanically applicable
   ```

5. **Profile Loader** (new file: `profile_loader.py`)
   ```python
   class ProfileLoader:
       def __init__(self, profiles_dir: Path = Path("profiles")):
           self.profiles_dir = profiles_dir
           self._cache = {}  # Cache loaded profiles in memory
       
       def load_profile(self, profile_name: str) -> str:
           """Load and cache a profile markdown file as a string."""
           if profile_name in self._cache:
               return self._cache[profile_name]
           
           profile_path = self.profiles_dir / f"{profile_name}.md"
           if not profile_path.exists():
               raise FileNotFoundError(f"Profile not found: {profile_path}")
           
           content = profile_path.read_text(encoding="utf-8")
           self._cache[profile_name] = content
           return content
       
       def get_base_policy(self) -> str:
           """Always load base policy (injected into every call)."""
           return self.load_profile("base_policy")
       
       def build_full_profile(self, task_style: str) -> str:
           """Combine base policy + task style into full profile."""
           base = self.get_base_policy()
           task = self.load_profile(task_style)
           return f"{base}\n\n---\n\n{task}"
   ```

6. **LLM Client Integration** (update `llm.py`)
   - Add ProfileLoader instance to LLMClient:
     ```python
     class LLMClient:
         def __init__(self):
             self.client = anthropic.Client(api_key=os.environ["ANTHROPIC_API_KEY"])
             self.profile_loader = ProfileLoader()
     ```
   
   - Update `generate_questions()` signature and implementation:
     ```python
     def generate_questions(self, section_id: str, doc_type: str, section_context: str, 
                           llm_profile: str, allow_subsections: bool) -> List[Dict]:
         # Load profile
         full_profile = self.profile_loader.build_full_profile(llm_profile)
         
         # Build prompt with profile injection
         prompt = f"""
         {full_profile}
         
         ---
         
         ## Task: Generate Clarifying Questions
         
         Section ID: {section_id}
         Document Type: {doc_type}
         Allow Subsections: {allow_subsections}
         
         Current Section Content:
         {section_context}
         
         Generate 2-5 clarifying questions to help complete this section.
         Output JSON array with format: [{{"question": "...", "section_target": "...", "rationale": "..."}}]
         """
         
         # Call LLM with profile-enhanced prompt
         response = self.client.messages.create(...)
         return parse_json_response(response)
     ```
   
   - Update `integrate_answers()` similarly:
     ```python
     def integrate_answers(self, section_id: str, doc_type: str, current_body: str,
                          questions: List[OpenQuestion], llm_profile: str, output_format: str) -> str:
         # Load profile
         full_profile = self.profile_loader.build_full_profile(llm_profile)
         
         # Build prompt with profile injection + output format guidance
         format_guidance = {
             "prose": "Write integrated content as flowing prose paragraphs.",
             "bullets": "Write integrated content as a bullet list (dash-prefixed, one item per line).",
             "subsections": "Organize content under appropriate subsection headers (###)."
         }[output_format]
         
         prompt = f"""
         {full_profile}
         
         ---
         
         ## Task: Integrate Answers into Section
         
         Section ID: {section_id}
         Document Type: {doc_type}
         Output Format: {format_guidance}
         
         Current Section Content:
         {current_body}
         
         Answered Questions:
         {format_questions(questions)}
         
         Rewrite the section incorporating answers. Remove placeholder wording.
         Output only the rewritten section body (no markers, no headers).
         """
         
         response = self.client.messages.create(...)
         return extract_text_response(response)
     ```

7. **SectionProcessor Integration** (update `section_processor.py`)
   - Pass `llm_profile` from HandlerConfig to LLM calls:
     ```python
     def _generate_questions(self, section_id: str, config: HandlerConfig) -> ProcessResult:
         questions = self.llm.generate_questions(
             section_id=section_id,
             doc_type=self.doc_type,
             section_context=section_body,
             llm_profile=config.llm_profile,  # ← now fully implemented
             allow_subsections=config.subsections
         )
     ```

8. **Profile Validation**
   - On startup, validate all referenced profiles exist
   - Fail fast if base_policy.md missing (critical dependency)
   - Warn if task style profile missing (use base_policy only as fallback)

**Acceptance Criteria:**

* ✅ `profiles/` directory exists with base_policy.md, requirements.md, requirements_review.md
* ✅ Base policy always injected into every LLM call (verifiable via debug logging)
* ✅ Task style selected via `llm_profile` field in HandlerConfig (from handler registry)
* ✅ ProfileLoader caches profiles in memory (no repeated disk reads)
* ✅ LLM prompts include full profile (base + task style) before task-specific instructions
* ✅ Profiles contain rules and constraints, not personas or narrative prose
* ✅ Missing profile file produces clear error at startup (not during processing)
* ✅ Profile injection does not break existing LLM calls (backward compatible prompts)
* ✅ Review gate profile (requirements_review.md) structured for review tasks
* ✅ Profiles are markdown files (human-readable, easy to edit, support comments)

**Dependencies:**
- Issue 5 (unified LLM loop) - integration point for profile injection
- Issue 4 (handler registry) - `llm_profile` field in HandlerConfig

**Breaking Changes:**
- None (profiles enhance existing prompts without changing signatures)
- LLM outputs may differ slightly due to enhanced guidance (expected improvement)

**Testing:**
- Unit test: ProfileLoader loads base_policy.md correctly
- Unit test: ProfileLoader builds full profile (base + task style)
- Unit test: Missing profile file → clear error
- Unit test: Profile injection → verify full_profile appears in LLM prompt
- Integration test: generate questions with requirements profile → questions follow guidelines
- Integration test: integrate answers with requirements profile → output follows style
- Manual test: compare LLM outputs before/after profiles → improved quality and consistency

**Profile Maintenance:**
- Profiles are living documents; update as LLM behavior is refined
- Version control profiles alongside code (track changes to reasoning rules)
- Document profile updates in changelog (impacts LLM output)
- Consider adding profile versioning (future enhancement)

**Future Enhancements (out of scope):**
- Conditional profile injection (different rules based on section state)
- User-customizable profiles (override default profiles)
- Profile inheritance/composition (mix multiple profiles)
- Profile A/B testing (compare outputs with different profiles)

**Notes:**
- Profiles are **rules**, not personas (avoid "You are an expert..." phrasing)
- Markdown chosen for readability; profiles are documentation as much as config
- Base policy prevents common LLM failure modes (structure injection, hallucination)
- Task styles adapt LLM reasoning to doc type without changing core engine
- This is the **MVP milestone** per your feedback (Issues 1-6 = new system provides value)

---

## Issue 7: Implement Review Gate Handler

**Type:** Feature  
**Priority:** Medium (Quality Assurance)  
**Estimated Effort:** 10-12 hours  

**Description:**
Support special workflow targets prefixed with `review_gate:` that trigger LLM-powered review of prior sections. Review gates validate completeness, consistency, and quality without mutating documents directly. They return JSON results (pass/fail, issues, optional patches) that humans can review and optionally apply. Auto-apply behavior is configurable per gate via handler registry.

**Current State:**
- No review capability exists
- Document quality depends entirely on human review of each section
- No automated consistency checking across sections
- No way to validate document before downstream automation (e.g., code generation)
- Workflow order supports only regular sections (no special targets)

**Implementation Plan:**

1. **Review Gate Target Format**
   - Workflow order includes targets like: `review_gate:coherence_check`, `review_gate:pre_approval`
   - Naming convention: `review_gate:` prefix required for recognition
   - Gate ID after prefix is arbitrary (human-readable name)
   - Gates are workflow targets just like sections (processed in sequence)

2. **Handler Registry Configuration** (extends Issue 4 config)
   ```yaml
   requirements:
     review_gate:coherence_check:
       mode: review_gate
       scope: all_prior_sections  # review all sections before this gate in workflow order
       auto_apply_patches: configurable  # "never", "always", "if_validation_passes"
       llm_profile: requirements_review
       validation_rules:
         - no_contradictions
         - no_missing_critical_sections
         - consistent_terminology
     
     review_gate:pre_approval:
       mode: review_gate
       scope: entire_document  # review everything regardless of position
       auto_apply_patches: never  # require human approval
       llm_profile: requirements_review
       validation_rules:
         - final_completeness
         - approval_section_ready
   ```

3. **Define ReviewResult Model** (`models.py`)
   ```python
   @dataclass(frozen=True)
   class ReviewIssue:
       severity: str  # "blocker", "warning"
       section: str   # section ID where issue found
       description: str
       suggestion: str | None  # optional fix suggestion
   
   @dataclass(frozen=True)
   class ReviewPatch:
       section: str       # section ID to patch
       suggestion: str    # proposed replacement content
       rationale: str     # why this patch is needed
       validated: bool    # passed structural validation?
   
   @dataclass(frozen=True)
   class ReviewResult:
       gate_id: str
       passed: bool       # true if no blocking issues
       issues: List[ReviewIssue]
       patches: List[ReviewPatch]
       scope_sections: List[str]  # sections actually reviewed
       summary: str       # human-readable summary
   ```

4. **Create ReviewGateHandler** (new file: `review_gate_handler.py`)
   ```python
   class ReviewGateHandler:
       def __init__(self, llm: LLMClient, lines: List[str], doc_type: str):
           self.llm = llm
           self.lines = lines
           self.doc_type = doc_type
       
       def execute_review(self, gate_id: str, config: HandlerConfig) -> ReviewResult:
           """
           Execute a review gate: analyze sections, return issues and patches.
           """
           # 1. Determine scope (which sections to review)
           scope_sections = self._determine_scope(gate_id, config.scope)
           
           # 2. Extract content for all scope sections
           section_contents = self._extract_sections(scope_sections)
           
           # 3. Call LLM to perform review
           review_data = self._call_review_llm(gate_id, section_contents, config)
           
           # 4. Parse LLM response into structured ReviewResult
           result = self._parse_review_response(gate_id, review_data, scope_sections)
           
           # 5. Validate patches (structural validation, not semantic)
           result = self._validate_patches(result)
           
           return result
   ```

5. **Scope Determination Logic**
   ```python
   def _determine_scope(self, gate_id: str, scope_config: str) -> List[str]:
       """
       Determine which sections to include in review based on scope config.
       """
       if scope_config == "all_prior_sections":
           # Get workflow order up to this gate
           workflow_order = extract_workflow_order(self.lines)
           gate_index = workflow_order.index(gate_id)
           return [s for s in workflow_order[:gate_index] if not s.startswith("review_gate:")]
       
       elif scope_config == "entire_document":
           # Get all section IDs in document
           return extract_all_section_ids(self.lines)
       
       elif scope_config.startswith("sections:"):
           # Explicit list: "sections:assumptions,constraints,requirements"
           return scope_config.replace("sections:", "").split(",")
       
       else:
           raise ValueError(f"Unknown scope config: {scope_config}")
   ```

6. **LLM Review Call** (update `llm.py`)
   ```python
   def perform_review(self, gate_id: str, doc_type: str, section_contents: Dict[str, str],
                      llm_profile: str, validation_rules: List[str]) -> Dict:
       """
       Call LLM to review multiple sections and return structured feedback.
       """
       # Load review profile
       full_profile = self.profile_loader.build_full_profile(llm_profile)
       
       # Build review prompt
       sections_text = "\n\n".join([
           f"## Section: {sid}\n{content}"
           for sid, content in section_contents.items()
       ])
       
       prompt = f"""
       {full_profile}
       
       ---
       
       ## Task: Review Document Sections
       
       Gate ID: {gate_id}
       Document Type: {doc_type}
       Validation Rules: {', '.join(validation_rules)}
       
       Sections to Review:
       {sections_text}
       
       Analyze the sections for:
       - Completeness (missing critical content?)
       - Consistency (contradictions between sections?)
       - Clarity (ambiguous or untestable requirements?)
       - Feasibility (impossible constraints?)
       
       Output JSON with format:
       {{
         "pass": boolean,
         "issues": [
           {{"severity": "blocker|warning", "section": "section_id", "description": "...", "suggestion": "..."}}
         ],
         "patches": [
           {{"section": "section_id", "suggestion": "...", "rationale": "..."}}
         ],
         "summary": "Brief overall assessment"
       }}
       """
       
       response = self.client.messages.create(
           model=MODEL,
           max_tokens=MAX_TOKENS,
           messages=[{"role": "user", "content": prompt}]
       )
       
       return parse_json_response(response)
   ```

7. **Patch Validation**
   ```python
   def _validate_patches(self, result: ReviewResult) -> ReviewResult:
       """
       Validate patches structurally (not semantically).
       Check: target section exists, suggestion is non-empty, no structure markers.
       """
       validated_patches = []
       for patch in result.patches:
           # Check section exists
           if not section_exists(patch.section, self.lines):
               logging.warning(f"Patch targets unknown section: {patch.section}")
               validated_patches.append(patch._replace(validated=False))
               continue
           
           # Check suggestion doesn't contain structure markers
           if contains_markers(patch.suggestion):
               logging.warning(f"Patch contains structure markers: {patch.section}")
               validated_patches.append(patch._replace(validated=False))
               continue
           
           # Passed validation
           validated_patches.append(patch._replace(validated=True))
       
       return result._replace(patches=validated_patches)
   ```

8. **Auto-Apply Logic** (in WorkflowRunner or ReviewGateHandler)
   ```python
   def _apply_patches_if_configured(self, result: ReviewResult, config: HandlerConfig) -> Tuple[List[str], bool]:
       """
       Optionally apply patches based on auto_apply_patches config.
       Returns (updated_lines, patches_applied).
       """
       auto_apply = config.auto_apply_patches  # "never", "always", "if_validation_passes"
       
       if auto_apply == "never":
           return self.lines, False
       
       if auto_apply == "if_validation_passes" and not all(p.validated for p in result.patches):
           logging.info("Patches not auto-applied: validation failed")
           return self.lines, False
       
       if auto_apply in ("always", "if_validation_passes"):
           updated_lines = self.lines
           for patch in result.patches:
               if patch.validated:
                   updated_lines = apply_patch(patch.section, patch.suggestion, updated_lines)
                   logging.info(f"Auto-applied patch to {patch.section}")
           return updated_lines, True
       
       raise ValueError(f"Unknown auto_apply_patches config: {auto_apply}")
   ```

9. **WorkflowRunner Integration** (update `runner_v2.py`)
   ```python
   def _execute_section(self, target_id: str, config: HandlerConfig) -> WorkflowResult:
       if config.mode == "review_gate":
           # Execute review gate
           handler = ReviewGateHandler(self.llm, self.lines, self.doc_type)
           review_result = handler.execute_review(target_id, config)
           
           # Optionally apply patches
           self.lines, patches_applied = handler._apply_patches_if_configured(review_result, config)
           
           # Convert to WorkflowResult
           return WorkflowResult(
               target_id=target_id,
               action_taken="review_gate",
               changed=patches_applied,
               blocked=not review_result.passed,
               blocked_reasons=[f"{i.severity}: {i.description}" for i in review_result.issues if i.severity == "blocker"],
               summaries=[review_result.summary] + [f"{i.severity}: {i.description}" for i in review_result.issues],
               questions_generated=0,
               questions_resolved=0
           )
       else:
           # Regular section processing (Issue 5)
           ...
   ```

10. **CLI Output for Review Gates**
    - Print review results in human-readable format:
      ```
      Review Gate: coherence_check
      Status: FAILED (2 blocker issues, 3 warnings)
      
      Blockers:
      - [assumptions] Contradicts constraint C-003 about data retention
      - [requirements] Missing critical security requirements
      
      Warnings:
      - [goals_objectives] Ambiguous success metric "good performance"
      - [constraints] Inconsistent terminology: "user" vs "customer"
      - [stakeholders_users] Missing key stakeholder group: operations team
      
      Patches Available: 2 (validation passed)
      - [assumptions] Remove contradictory assumption about data deletion
      - [goals_objectives] Clarify success metric with measurable threshold
      
      Auto-apply: Disabled (manual review required)
      ```

**Acceptance Criteria:**

* ✅ Review gates recognized as special workflow targets (prefix `review_gate:`)
* ✅ ReviewGateHandler executes LLM-powered review of specified scope
* ✅ Review gates cannot mutate doc directly (patches are suggestions only)
* ✅ LLM returns JSON with: pass/fail, issues (severity + description), patches (optional)
* ✅ Patch validation checks: section exists, no structure markers, non-empty
* ✅ Review status is machine-verifiable (pass boolean + structured issues)
* ✅ Auto-apply configurable per gate: "never", "always", "if_validation_passes"
* ✅ Scope configurable: "all_prior_sections", "entire_document", "sections:X,Y,Z"
* ✅ Blocker issues mark workflow as blocked (requires human intervention)
* ✅ Warnings logged but don't block workflow progression
* ✅ Review results printed in human-readable format
* ✅ Manual patch application supported (human reviews and applies via editing)

**Dependencies:**
- Issue 6 (LLM profiles) - requires requirements_review.md profile
- Issue 5 (unified LLM loop) - integration pattern similar
- Issue 4 (handler registry) - review gate config in registry
- Issue 3 (WorkflowRunner) - review gates as workflow targets

**Breaking Changes:**
- None (new feature, no existing review gates to break)

**Testing:**
- Unit test: determine_scope with "all_prior_sections" → correct section list
- Unit test: determine_scope with "entire_document" → all sections
- Unit test: validate_patches with valid patch → validated=True
- Unit test: validate_patches with markers in suggestion → validated=False
- Unit test: auto_apply="never" → patches not applied
- Unit test: auto_apply="if_validation_passes" + all valid → patches applied
- Integration test: review gate finds contradiction between sections → blocker issue
- Integration test: review gate passes → workflow continues
- Integration test: review gate fails → workflow blocked

**Security Considerations:**
- Patches are untrusted LLM output → always validate before applying
- Auto-apply should be used cautiously (risk of LLM hallucination)
- Recommendation: default to auto_apply="never" for production

**Future Enhancements (out of scope):**
- Interactive patch review (approve/reject each patch individually)
- Patch preview mode (show diff before applying)
- Custom validation rules (user-defined checks beyond LLM review)
- Multi-LLM review (consensus from multiple models)
- Review history tracking (log all review results over time)

**Notes:**
- Review gates are first-class workflow targets (same status as sections)
- Auto-apply="if_validation_passes" is recommended middle ground (safety + convenience)
- Review gates enable quality assurance without breaking determinism
- Future: cross-document review gates (validate consistency across multiple docs)

---

## Issue 8: Define Document Completion Criteria

**Type:** Enhancement  
**Priority:** Medium (Downstream Integration)  
**Estimated Effort:** 6-8 hours  

**Description:**
Formalize what "document complete" means with deterministic, machine-verifiable criteria. This enables downstream automation (code generation, artifact pipelines) to know when a document is ready for processing. Completion check blocks progression to automated workflows that depend on complete, validated requirements.

**Current State:**
- No explicit completion criteria beyond "all sections processed"
- `choose_phase()` returns "all complete" when last phase validates successfully
- Implicit assumptions: no PLACEHOLDER tokens, no open questions
- No formalized check for review gate passage
- No distinction between "section complete" vs "document complete"
- Downstream tools don't know if document is ready (risk of processing incomplete docs)

**Implementation Plan:**

1. **Define Completion Criteria** (in `config.py`)
   ```python
   # Document completion requirements
   COMPLETION_CRITERIA = {
       "no_placeholders_in_required_sections": True,    # Required sections must not have PLACEHOLDER token
       "no_open_questions": True,                       # No questions with status "Open"
       "all_review_gates_pass": True,                   # All review gates in workflow must pass
       "structure_valid": True,                         # All structural validators pass (markers, table schema)
       "all_workflow_targets_complete": True,           # All targets in workflow order marked complete
   }
   
   # Optional criteria (can be disabled via flags)
   OPTIONAL_CRITERIA = {
       "no_deferred_questions": False,  # Strict mode: even "Deferred" questions must be resolved
       "no_warnings_from_review": False, # Strict mode: review gates must have zero warnings
   }
   ```

2. **Define CompletionStatus Model** (`models.py`)
   ```python
   @dataclass(frozen=True)
   class CompletionCheck:
       criterion: str          # Which completion criterion
       passed: bool           # Did this criterion pass?
       details: str           # Human-readable explanation
       blocking: bool         # Is this a blocking failure?
   
   @dataclass(frozen=True)
   class CompletionStatus:
       complete: bool                    # Overall: document meets all criteria?
       checks: List[CompletionCheck]     # Individual criterion results
       blocking_failures: List[str]      # List of blocking criterion names that failed
       warnings: List[str]               # Non-blocking issues
       summary: str                      # Human-readable overall status
   ```

3. **Create DocumentValidator** (new file: `document_validator.py`)
   ```python
   class DocumentValidator:
       def __init__(self, lines: List[str], workflow_order: List[str], 
                    handler_registry: HandlerRegistry, doc_type: str):
           self.lines = lines
           self.workflow_order = workflow_order
           self.registry = handler_registry
           self.doc_type = doc_type
       
       def validate_completion(self, strict: bool = False) -> CompletionStatus:
           """
           Check all completion criteria and return structured status.
           """
           checks = []
           
           # Criterion 1: No placeholders in required sections
           checks.append(self._check_no_placeholders())
           
           # Criterion 2: No open questions
           checks.append(self._check_no_open_questions(strict))
           
           # Criterion 3: All review gates pass
           checks.append(self._check_review_gates_pass(strict))
           
           # Criterion 4: Structure valid
           checks.append(self._check_structure_valid())
           
           # Criterion 5: All workflow targets complete
           checks.append(self._check_workflow_complete())
           
           # Aggregate results
           blocking_failures = [c.criterion for c in checks if not c.passed and c.blocking]
           warnings = [c.details for c in checks if not c.passed and not c.blocking]
           complete = len(blocking_failures) == 0
           
           summary = self._build_summary(complete, blocking_failures, warnings)
           
           return CompletionStatus(
               complete=complete,
               checks=checks,
               blocking_failures=blocking_failures,
               warnings=warnings,
               summary=summary
           )
   ```

4. **Individual Completion Checks**
   ```python
   def _check_no_placeholders(self) -> CompletionCheck:
       """Check that no required sections contain PLACEHOLDER token."""
       required_sections = self._get_required_sections()
       sections_with_placeholders = []
       
       for section_id in required_sections:
           span = find_section_span(section_id, self.lines)
           if span and has_placeholder(span, self.lines):
               sections_with_placeholders.append(section_id)
       
       passed = len(sections_with_placeholders) == 0
       details = (
           "All required sections have content"
           if passed
           else f"Sections with PLACEHOLDER: {', '.join(sections_with_placeholders)}"
       )
       
       return CompletionCheck(
           criterion="no_placeholders_in_required_sections",
           passed=passed,
           details=details,
           blocking=True
       )
   
   def _check_no_open_questions(self, strict: bool) -> CompletionCheck:
       """Check that no questions remain unanswered."""
       open_questions = parse_open_questions_table(self.lines)
       
       if strict:
           # Strict mode: even Deferred questions count as incomplete
           incomplete = [q for q in open_questions if q.status in ("Open", "Deferred")]
       else:
           # Normal mode: only Open questions count
           incomplete = [q for q in open_questions if q.status == "Open"]
       
       passed = len(incomplete) == 0
       details = (
           "All questions resolved"
           if passed
           else f"{len(incomplete)} questions remain: {[q.id for q in incomplete[:5]]}"
       )
       
       return CompletionCheck(
           criterion="no_open_questions",
           passed=passed,
           details=details,
           blocking=True
       )
   
   def _check_review_gates_pass(self, strict: bool) -> CompletionCheck:
       """Check that all review gates in workflow have passed."""
       review_gates = [t for t in self.workflow_order if t.startswith("review_gate:")]
       
       if not review_gates:
           return CompletionCheck(
               criterion="all_review_gates_pass",
               passed=True,
               details="No review gates in workflow",
               blocking=False
           )
       
       # Retrieve review gate results (must be stored somewhere - see note below)
       failed_gates = self._get_failed_review_gates(review_gates, strict)
       
       passed = len(failed_gates) == 0
       details = (
           f"All {len(review_gates)} review gates passed"
           if passed
           else f"Failed gates: {', '.join(failed_gates)}"
       )
       
       return CompletionCheck(
           criterion="all_review_gates_pass",
           passed=passed,
           details=details,
           blocking=True
       )
   
   def _check_structure_valid(self) -> CompletionCheck:
       """Check that document structure is valid (markers, table schema, etc.)."""
       errors = []
       
       # Check: workflow order matches actual sections
       missing_sections = self._find_missing_workflow_sections()
       if missing_sections:
           errors.append(f"Missing sections: {', '.join(missing_sections)}")
       
       # Check: Open Questions table has correct schema
       if not validate_open_questions_table_schema(self.lines):
           errors.append("Open Questions table schema invalid")
       
       # Check: No duplicate section markers
       duplicate_sections = find_duplicate_section_markers(self.lines)
       if duplicate_sections:
           errors.append(f"Duplicate section markers: {', '.join(duplicate_sections)}")
       
       passed = len(errors) == 0
       details = "Document structure valid" if passed else "; ".join(errors)
       
       return CompletionCheck(
           criterion="structure_valid",
           passed=passed,
           details=details,
           blocking=True
       )
   
   def _check_workflow_complete(self) -> CompletionCheck:
       """Check that all workflow targets have been processed."""
       incomplete_targets = []
       
       for target in self.workflow_order:
           if target.startswith("review_gate:"):
               # Check review gate result (must pass)
               if not self._review_gate_passed(target):
                   incomplete_targets.append(target)
           else:
               # Check section complete (no placeholder, no open questions)
               config = self.registry.get_handler_config(self.doc_type, target)
               if not self._section_complete(target, config):
                   incomplete_targets.append(target)
       
       passed = len(incomplete_targets) == 0
       details = (
           "All workflow targets complete"
           if passed
           else f"Incomplete: {', '.join(incomplete_targets)}"
       )
       
       return CompletionCheck(
           criterion="all_workflow_targets_complete",
           passed=passed,
           details=details,
           blocking=True
       )
   ```

5. **Review Gate Result Storage**
   - Issue: Review gate results are ephemeral (only in WorkflowResult, not persisted)
   - Solution: Add review gate result marker to document:
     ```md
     <!-- review_gate_result:coherence_check status="passed" timestamp="2026-02-10T15:30:00Z" -->
     ```
   - Parser function: `extract_review_gate_results(lines)` → Dict[gate_id, status]
   - Update ReviewGateHandler to write result marker after execution
   - Completion validator reads these markers to check gate passage

6. **CLI Integration** (`cli.py`)
   - Add `--validate` flag to check completion without processing:
     ```python
     if args.validate:
         validator = DocumentValidator(lines, workflow_order, registry, doc_type)
         status = validator.validate_completion(strict=args.strict)
         print(json.dumps(asdict(status), indent=2))
         return 0 if status.complete else 1
     ```
   
   - Add `--strict` flag for strict completion checking (includes optional criteria)
   
   - Check completion before downstream pipelines:
     ```python
     if args.generate_artifacts:  # hypothetical future flag for code gen
         validator = DocumentValidator(lines, workflow_order, registry, doc_type)
         status = validator.validate_completion()
         if not status.complete:
             print(f"ERROR: Cannot generate artifacts - document incomplete:\n{status.summary}")
             return 2
         # Proceed with artifact generation...
     ```

7. **Human-Readable Output**
   ```
   Document Completion Status: INCOMPLETE
   
   ✅ No placeholders in required sections
   ❌ Open questions remain: Q-003, Q-007, Q-012 (3 total)
   ✅ All review gates passed (2/2)
   ✅ Document structure valid
   ❌ Workflow incomplete: requirements, interfaces_integrations (2 sections)
   
   Blocking Issues:
   - 3 questions remain unanswered
   - 2 workflow sections not yet complete
   
   Document cannot proceed to downstream automation until all criteria met.
   ```

8. **Required Sections Definition**
   ```python
   def _get_required_sections(self) -> List[str]:
       """
       Determine which sections are required based on doc_type and workflow.
       For now: all non-review-gate targets in workflow are required.
       Future: support optional sections via metadata.
       """
       return [
           t for t in self.workflow_order
           if not t.startswith("review_gate:")
       ]
   ```

**Acceptance Criteria:**

* ✅ Completion check is deterministic (same document state → same result)
* ✅ All five core criteria implemented: no_placeholders, no_open_questions, review_gates_pass, structure_valid, workflow_complete
* ✅ `CompletionStatus` model defined with structured results
* ✅ `DocumentValidator` class checks all criteria and returns status
* ✅ Review gate results persisted as document markers for validation
* ✅ CLI `--validate` flag performs standalone completion check
* ✅ CLI `--strict` flag enables optional criteria (deferred questions, warnings)
* ✅ Completion check used to block progression to downstream automation
* ✅ Human-readable output clearly explains blocking issues
* ✅ Machine-readable JSON output available for tooling integration

**Dependencies:**
- Issue 7 (review gates) - review gate passage is a completion criterion
- Issue 3 (WorkflowRunner) - workflow completion is a criterion
- Issue 2 (workflow order) - workflow order defines required targets

**Breaking Changes:**
- None (new validation feature, doesn't affect existing workflows)

**Testing:**
- Unit test: document with PLACEHOLDER → completion fails (no_placeholders criterion)
- Unit test: document with Open questions → completion fails (no_open_questions criterion)
- Unit test: document with failed review gate → completion fails (review_gates_pass criterion)
- Unit test: document with invalid table schema → completion fails (structure_valid criterion)
- Unit test: document with incomplete workflow → completion fails (workflow_complete criterion)
- Unit test: fully complete document → all criteria pass
- Unit test: strict mode with Deferred questions → completion fails
- Integration test: `--validate` flag returns exit code 1 for incomplete doc
- Integration test: `--validate` flag returns exit code 0 for complete doc

**Future Enhancements (out of scope):**
- Custom completion criteria per doc_type
- Weightings (some criteria more important than others)
- Partial completion scoring (80% complete based on criteria weights)
- Time-based criteria (document older than X days must be re-reviewed)
- Change-based triggers (if section X changes, re-validate criteria)

**Notes:**
- Completion criteria enable safe downstream automation (artifact generation, code generation, etc.)
- Review gate result markers make gate passage visible and auditable
- Strict mode useful for high-stakes docs requiring perfect completion
- Normal mode allows pragmatic "good enough" completion (Deferred questions OK)

---

## Issue 9: Harden Structural and Span Validation

**Type:** Hardening  
**Priority:** High (Data Integrity)  
**Estimated Effort:** 8-10 hours  

**Description:**
Strengthen guardrails around section spans, patch application, and document structure integrity. Current parsing and editing logic has implicit trust in document structure; this issue makes validation explicit, fail-fast, and comprehensive. Prevents silent corruption and catches structural errors early.

**Current State:**
- `parsing.py` has span extraction but minimal validation (trusts markers exist and are well-formed)
- `editing.py` replaces section bodies but doesn't validate spans before/after
- No validation for: duplicate markers, overlapping spans, malformed markers, orphaned locks
- `sanitize.py` removes markers from LLM output but doesn't validate surrounding structure
- Patch application (Issue 7) trusts section exists but doesn't validate span consistency
- Silent corruption possible: mismatched markers, duplicate sections, broken table schema

**Implementation Plan:**

1. **Define StructuralError Types** (new file: `validation_errors.py`)
   ```python
   class StructuralError(Exception):
       """Base class for document structure validation errors."""
       pass
   
   class DuplicateSectionError(StructuralError):
       """Multiple sections with same ID found."""
       def __init__(self, section_id: str, line_numbers: List[int]):
           self.section_id = section_id
           self.line_numbers = line_numbers
           super().__init__(f"Duplicate section '{section_id}' at lines: {line_numbers}")
   
   class MalformedMarkerError(StructuralError):
       """Marker has invalid syntax."""
       def __init__(self, line_num: int, line_content: str, reason: str):
           super().__init__(f"Malformed marker at line {line_num}: {reason}\n  {line_content}")
   
   class InvalidSpanError(StructuralError):
       """Section span is invalid or ambiguous."""
       def __init__(self, section_id: str, reason: str):
           super().__init__(f"Invalid span for section '{section_id}': {reason}")
   
   class TableSchemaError(StructuralError):
       """Open Questions table schema is invalid."""
       def __init__(self, reason: str):
           super().__init__(f"Table schema error: {reason}")
   
   class OrphanedLockError(StructuralError):
       """Lock marker exists without corresponding section marker."""
       def __init__(self, lock_id: str, line_num: int):
           super().__init__(f"Lock marker for '{lock_id}' at line {line_num} has no corresponding section")
   ```

2. **Create StructuralValidator** (new file: `structural_validator.py`)
   ```python
   class StructuralValidator:
       def __init__(self, lines: List[str]):
           self.lines = lines
           self.errors: List[StructuralError] = []
       
       def validate_all(self) -> List[StructuralError]:
           """Run all structural validations and return errors."""
           self.errors = []
           
           self._validate_section_markers()
           self._validate_lock_markers()
           self._validate_table_markers()
           self._validate_subsection_markers()
           self._validate_open_questions_table()
           self._validate_metadata_markers()
           self._validate_workflow_order_marker()
           
           return self.errors
       
       def validate_or_raise(self):
           """Run validations and raise first error encountered."""
           errors = self.validate_all()
           if errors:
               raise errors[0]
   ```

3. **Section Marker Validation**
   ```python
   def _validate_section_markers(self):
       """Check: no duplicates, all well-formed, no orphaned spans."""
       section_ids = {}  # {section_id: [line_numbers]}
       
       for i, line in enumerate(self.lines):
           match = SECTION_MARKER_RE.search(line)
           if match:
               section_id = match.group("id")
               
               # Check well-formed
               if not re.fullmatch(r"[a-z0-9_]+", section_id):
                   self.errors.append(MalformedMarkerError(
                       i + 1, line, f"Invalid section ID format: {section_id}"
                   ))
               
               # Track for duplicate detection
               if section_id not in section_ids:
                   section_ids[section_id] = []
               section_ids[section_id].append(i + 1)
       
       # Check for duplicates
       for section_id, line_nums in section_ids.items():
           if len(line_nums) > 1:
               self.errors.append(DuplicateSectionError(section_id, line_nums))
   ```

4. **Lock Marker Validation**
   ```python
   def _validate_lock_markers(self):
       """Check: every lock has corresponding section, lock value is boolean."""
       section_ids = set()
       for line in self.lines:
           match = SECTION_MARKER_RE.search(line)
           if match:
               section_ids.add(match.group("id"))
       
       for i, line in enumerate(self.lines):
           match = SECTION_LOCK_RE.search(line)
           if match:
               lock_id = match.group("id")
               lock_value = match.group("lock")
               
               # Check section exists
               if lock_id not in section_ids:
                   self.errors.append(OrphanedLockError(lock_id, i + 1))
               
               # Check lock value
               if lock_value not in ("true", "false"):
                   self.errors.append(MalformedMarkerError(
                       i + 1, line, f"Lock value must be 'true' or 'false', got: {lock_value}"
                   ))
   ```

5. **Open Questions Table Validation**
   ```python
   def _validate_open_questions_table(self):
       """Check: table exists, schema matches expected, no malformed rows."""
       table_span = find_table_span("open_questions", self.lines)
       if not table_span:
           self.errors.append(TableSchemaError("Open Questions table not found"))
           return
       
       # Extract table rows
       table_lines = self.lines[table_span.start:table_span.end]
       
       # Find header row
       header_row = None
       for line in table_lines:
           if "|" in line and "Question ID" in line:
               header_row = line
               break
       
       if not header_row:
           self.errors.append(TableSchemaError("Table header row not found"))
           return
       
       # Parse header columns
       columns = [c.strip() for c in header_row.split("|") if c.strip()]
       
       # Validate schema
       if columns != OPEN_Q_COLUMNS:
           self.errors.append(TableSchemaError(
               f"Expected columns {OPEN_Q_COLUMNS}, got {columns}"
           ))
       
       # Validate row format (basic check: correct number of pipes)
       expected_pipes = len(OPEN_Q_COLUMNS) + 1  # 7 columns = 8 pipes (including start/end)
       for i, line in enumerate(table_lines):
           if "|" in line and "---" not in line and "Question ID" not in line:
               pipe_count = line.count("|")
               if pipe_count != expected_pipes:
                   self.errors.append(TableSchemaError(
                       f"Malformed table row at offset {i}: expected {expected_pipes} pipes, got {pipe_count}"
                   ))
   ```

6. **Span Validation Before Edit** (update `editing.py`)
   ```python
   def replace_section_body(section_id: str, new_body: str, lines: List[str]) -> List[str]:
       """
       Replace section body text, validating span before and after.
       """
       # Validate structure before edit
       validator = StructuralValidator(lines)
       validator.validate_or_raise()
       
       # Find section span
       span = find_section_span(section_id, lines)
       if not span:
           raise InvalidSpanError(section_id, "Section not found")
       
       # Validate span is sensible
       if span.start >= span.end:
           raise InvalidSpanError(section_id, f"Invalid span: start={span.start} >= end={span.end}")
       
       if span.body_start >= span.body_end:
           raise InvalidSpanError(section_id, f"Empty body span: {span.body_start} to {span.body_end}")
       
       # Perform replacement
       new_lines = lines[:span.body_start] + new_body.splitlines() + lines[span.body_end:]
       
       # Validate structure after edit
       validator_after = StructuralValidator(new_lines)
       errors_after = validator_after.validate_all()
       if errors_after:
           raise StructuralError(
               f"Edit to '{section_id}' would corrupt structure: {errors_after[0]}"
           )
       
       return new_lines
   ```

7. **Patch Application Validation** (update ReviewGateHandler in Issue 7)
   ```python
   def apply_patch(section_id: str, suggestion: str, lines: List[str]) -> List[str]:
       """
       Apply a review gate patch with comprehensive validation.
       """
       # Validate current structure
       validator_before = StructuralValidator(lines)
       validator_before.validate_or_raise()
       
       # Validate section exists and span is valid
       span = find_section_span(section_id, lines)
       if not span:
           raise InvalidSpanError(section_id, "Cannot apply patch - section not found")
       
       # Validate suggestion doesn't contain structure markers
       if contains_structure_markers(suggestion):
           raise ValidationError(f"Patch suggestion contains forbidden structure markers")
       
       # Apply via replace_section_body (which does its own validation)
       updated_lines = replace_section_body(section_id, suggestion, lines)
       
       return updated_lines
   ```

8. **Startup Validation** (update `cli.py`)
   ```python
   # After loading document, validate structure immediately
   lines = split_lines(read_text(doc_path))
   
   # Fail fast if structure is corrupted
   validator = StructuralValidator(lines)
   errors = validator.validate_all()
   if errors:
       print("ERROR: Document structure validation failed:")
       for error in errors:
           print(f"  - {error}")
       return 2
   ```

9. **Validation Reporting** (helper function)
   ```python
   def report_structural_errors(errors: List[StructuralError]) -> str:
       """Format structural errors for human-readable output."""
       report = ["Document Structure Validation Failed:", ""]
       
       for error in errors:
           if isinstance(error, DuplicateSectionError):
               report.append(f"❌ Duplicate section '{error.section_id}' at lines: {error.line_numbers}")
           elif isinstance(error, OrphanedLockError):
               report.append(f"❌ Orphaned lock marker: {error}")
           elif isinstance(error, TableSchemaError):
               report.append(f"❌ Table schema error: {error}")
           else:
               report.append(f"❌ {error}")
       
       report.append("")
       report.append("Fix structural errors before processing document.")
       return "\n".join(report)
   ```

10. **Add --validate-structure CLI Flag**
    ```python
    parser.add_argument("--validate-structure", action="store_true",
                       help="Check document structure without processing")
    
    if args.validate_structure:
        validator = StructuralValidator(lines)
        errors = validator.validate_all()
        if errors:
            print(report_structural_errors(errors))
            return 1
        else:
            print("✅ Document structure valid")
            return 0
    ```

**Acceptance Criteria:**

* ✅ `StructuralValidator` class validates all document structure elements
* ✅ Duplicate section markers detected and reported with line numbers
* ✅ Malformed markers (invalid syntax, bad IDs) detected and reported
* ✅ Orphaned lock markers (no corresponding section) detected
* ✅ Open Questions table schema validated (columns, row format)
* ✅ Patches rejected if they would corrupt structure (markers, invalid spans)
* ✅ Invalid or ambiguous spans detected before edit operations
* ✅ No silent corruption allowed (all structural changes validated)
* ✅ Startup validation fails fast if document corrupted
* ✅ `--validate-structure` CLI flag performs standalone validation
* ✅ Clear error messages with line numbers and actionable guidance

**Dependencies:**
- Issue 5 (unified LLM loop) - validation integrated into editing flow
- Issue 7 (review gates) - patch application validation

**Breaking Changes:**
- ⚠️ **BREAKING**: Documents with silent corruption will now fail validation (good thing!)
- Previously-tolerated malformed markers now cause errors
- Stricter validation may reject documents that previously "worked"

**Testing:**
- Unit test: duplicate section markers → DuplicateSectionError
- Unit test: malformed section ID (`section:foo-bar` with hyphen) → MalformedMarkerError
- Unit test: orphaned lock marker → OrphanedLockError
- Unit test: table with wrong columns → TableSchemaError
- Unit test: table with wrong pipe count → TableSchemaError
- Unit test: replace section body with invalid span → InvalidSpanError
- Unit test: apply patch with structure markers → raises error
- Integration test: corrupted document → validation fails at startup
- Integration test: valid document → validation passes silently
- Integration test: edit creates corruption → reverted/prevented

**Performance:**
- Validation adds overhead (~10-50ms for typical documents)
- Cache validation results within a single run (don't re-validate unchanged docs)
- Validation on startup + before critical edits (not after every operation)

**Future Enhancements (out of scope):**
- Auto-repair for common corruption patterns
- Validation warnings (non-blocking but flagged for review)
- Custom validation rules per doc_type
- Validation hooks for plugin extensibility

**Notes:**
- This issue prevents the most common source of automation failures: document corruption
- Fail-fast principle: catch errors early, don't propagate corruption
- Explicit validation replaces implicit trust in document structure
- Clear error messages enable fast debugging and manual fixes

---

## Issue 10: Update Developer Documentation

**Type:** Documentation  
**Priority:** High (Knowledge Transfer)  
**Estimated Effort:** 12-16 hours  

**Description:**
Document the new architecture comprehensively so Codex, contributors, and future maintainers operate from the same mental model. This is critical for long-term maintainability and enables others to extend the system without reverse-engineering code. Documentation should explain concepts, provide examples, and include decision rationale.

**Current State:**
- `README.md` describes old phase-based system
- No architectural diagrams or workflow visualizations
- No guide for adding new doc types or sections
- `contributing.md` exists but lacks technical detail
- No explanation of handler registry, LLM profiles, or review gates
- Implementation notes scattered across issue comments and code comments

**Implementation Plan:**

1. **Update README.md** (high-level overview)
   - Replace phase-based description with workflow-order model
   - Add "Quick Start" section with common use cases
   - Add "Architecture Overview" section with links to detailed docs
   - Update CLI examples to show new flags (--validate, --strict, --max-steps)
   - Add "Migration from Phase-Based System" section

2. **Create Architecture Guide** (`docs/architecture.md`)
   ```md
   # Architecture Guide
   
   ## Core Concepts
   ### Document-Driven Workflow
   - Workflow order defined in document template, not code
   - Sections processed in template-declared sequence
   - Review gates are first-class workflow targets
   
   ### Handler Registry
   - Maps (doc_type, section_id) → processing configuration
   - Enables new doc types without code changes
   - YAML-based configuration with clear schema
   
   ### Unified Processing Loop
   - Single code path for all section types
   - Configured via handler registry
   - Two modes: integrate_then_questions, questions_then_integrate
   
   ### LLM Profiles
   - Base policy + task style = full profile
   - Injected into every LLM call
   - Rules-based, not persona-based
   
   ### Review Gates
   - Quality assurance checkpoints in workflow
   - LLM-powered review with structured results
   - Patches suggested but not auto-applied (configurable)
   
   ## Component Interactions
   [Mermaid diagram showing: CLI → WorkflowRunner → SectionProcessor → LLM]
   [Mermaid diagram showing: Template → Parser → WorkflowOrder → Runner]
   
   ## Data Flow
   [Diagram: Document → Parser → Validator → Processor → Sanitizer → Document]
   
   ## Extension Points
   - Handler registry (add section behaviors)
   - LLM profiles (customize reasoning styles)
   - Validation rules (custom structural checks)
   ```

3. **Create Handler Registry Guide** (`docs/handler-registry-guide.md`)
   ```md
   # Handler Registry Guide
   
   ## Overview
   The handler registry maps (doc_type, section_id) → configuration.
   
   ## Configuration Schema
   [Documented YAML structure with all fields explained]
   
   ## Handler Modes
   ### integrate_then_questions
   - Use when: section needs iterative refinement
   - Behavior: integrate answers, then generate follow-up questions if still blank
   
   ### questions_then_integrate
   - Use when: single-pass workflow desired
   - Behavior: generate questions once, integrate answers, done
   
   ### review_gate
   - Use when: quality assurance checkpoint needed
   - Behavior: review prior sections, return issues and patches
   
   ## Output Formats
   - prose: flowing paragraphs
   - bullets: dash-prefixed lists
   - subsections: organized under ### headers
   
   ## Adding a New Section Type
   [Step-by-step guide with example]
   
   ## Adding a New Doc Type
   [Step-by-step guide with example]
   ```

4. **Create LLM Profiles Guide** (`docs/llm-profiles-guide.md`)
   ```md
   # LLM Profiles Guide
   
   ## Purpose
   Profiles define LLM reasoning rules and constraints.
   
   ## Profile Structure
   - profiles/base_policy.md: Always injected (forbidden actions, output rules)
   - profiles/<task_style>.md: Doc-type-specific guidance
   
   ## Writing Effective Profiles
   - Use rules, not personas ("Never X" not "You are an expert")
   - Be explicit about constraints and forbidden actions
   - Provide examples of good vs. bad outputs
   - Keep concise (profiles are injected into every call)
   
   ## Profile Development Workflow
   [How to test and iterate on profiles]
   
   ## Common Pitfalls
   - Overly verbose profiles (token waste)
   - Persona-based phrasing (inconsistent behavior)
   - Contradictory rules (confuses LLM)
   ```

5. **Create Review Gates Guide** (`docs/review-gates-guide.md`)
   ```md
   # Review Gates Guide
   
   ## What Are Review Gates?
   Quality assurance checkpoints in the workflow.
   
   ## When to Use Review Gates
   - Before critical transitions (requirements → design)
   - Before expensive downstream automation (code generation)
   - Periodic consistency checks (every 5 sections)
   
   ## Configuring Review Gates
   [Example configurations with explanations]
   
   ## Auto-Apply Policies
   - never: Always require human review (safest)
   - if_validation_passes: Auto-apply validated patches (recommended)
   - always: Auto-apply all patches (risky, use with caution)
   
   ## Interpreting Review Results
   [Example output with annotations]
   
   ## Handling Failed Review Gates
   [Troubleshooting guide]
   ```

6. **Create Workflow Order Guide** (`docs/workflow-order-guide.md`)
   ```md
   # Workflow Order Guide
   
   ## Defining Workflow Order
   Template header declares section processing sequence.
   
   ## Syntax
   [Explained with examples]
   
   ## Special Targets
   - review_gate:<name>: Quality assurance checkpoints
   - Future: conditional targets, parallel groups
   
   ## Best Practices
   - Order sections logically (general → specific)
   - Place review gates at natural checkpoints
   - Keep workflow order flat (no deep nesting)
   
   ## Validation Rules
   [What makes a valid workflow order]
   ```

7. **Create Template Guide** (`docs/template-guide.md`)
   ```md
   # Template Guide
   
   ## Template Anatomy
   - Metadata block (doc_type, version)
   - Workflow order declaration
   - Section definitions with markers
   - Open Questions table
   
   ## Creating a New Template
   [Step-by-step with full example]
   
   ## Template Best Practices
   - Use semantic section IDs (snake_case)
   - Lock sections that shouldn't change (approval_record)
   - Provide helpful section descriptions
   
   ## Template Versioning
   [Future: versioning strategy]
   ```

8. **Create Migration Guide** (`docs/migration-guide.md`)
   ```md
   # Migration Guide: Phase-Based → Workflow-Based
   
   ## Why Migrate?
   - More flexible (define workflow in template)
   - Extensible (new doc types without code changes)
   - Maintainable (less duplicate logic)
   
   ## Migration Steps
   1. Add metadata block to existing documents
   2. Add workflow order declaration
   3. Update CLI invocations (remove phase assumptions)
   4. Test with --dry-run
   5. Commit updated documents
   
   ## Breaking Changes
   [Documented list from all issues]
   
   ## Rollback Plan
   [If migration fails]
   
   ## Migration Script
   [Reference to tools/migrate_workflow_order.py]
   ```

9. **Create Troubleshooting Guide** (`docs/troubleshooting.md`)
   ```md
   # Troubleshooting Guide
   
   ## Common Errors
   ### "Document structure validation failed"
   - Cause: Duplicate markers, malformed syntax
   - Solution: Run --validate-structure, fix reported issues
   
   ### "Review gate failed: contradictions detected"
   - Cause: Inconsistent requirements across sections
   - Solution: Review issues, resolve contradictions, re-run
   
   ### "Section incomplete: unanswered questions"
   - Cause: Open questions still exist
   - Solution: Answer questions in table, re-run
   
   [More scenarios with solutions]
   
   ## Debug Techniques
   - Use --log-level DEBUG for detailed logging
   - Use --dry-run to preview changes
   - Check backup files in /tmp/requirements_automation_backups/
   
   ## Getting Help
   [Where to file issues, ask questions]
   ```

10. **Update CONTRIBUTING.md** (detailed for contributors)
    - Add "Architecture Overview" section linking to docs/architecture.md
    - Document code structure (which modules do what)
    - Explain testing strategy and how to run tests
    - Add "Adding a Feature" section with checklist
    - Document PR review criteria

11. **Create API Reference** (`docs/api-reference.md`)
    ```md
    # API Reference
    
    ## Core Classes
    ### WorkflowRunner
    [Documented methods, parameters, return types]
    
    ### SectionProcessor
    [Documented methods and usage]
    
    ### HandlerRegistry
    [Documented configuration and lookup]
    
    ## Utility Functions
    ### parsing.py
    [Documented functions with examples]
    
    ### editing.py
    [Documented functions with examples]
    
    ## Data Models
    ### models.py
    [All dataclasses documented with field descriptions]
    ```

12. **Create Examples Directory** (`docs/examples/`)
    - `requirements-template-annotated.md`: Fully annotated example template
    - `research-template.md`: Example of alternative doc type
    - `handler-registry-examples.yaml`: Commented example configurations
    - `profile-example.md`: Annotated LLM profile with explanations

13. **Add Mermaid Diagrams**
    - Architecture overview diagram
    - Workflow execution flow diagram
    - Section processing state machine diagram
    - Handler dispatch decision tree

**Acceptance Criteria:**

* ✅ README.md updated with workflow-based system description
* ✅ Architecture guide (`docs/architecture.md`) covers all core concepts
* ✅ Handler registry guide explains configuration and extension
* ✅ LLM profiles guide explains writing and using profiles
* ✅ Review gates guide covers configuration and usage
* ✅ Workflow order guide explains syntax and best practices
* ✅ Template guide covers creating new templates from scratch
* ✅ Migration guide enables smooth transition from phase-based system
* ✅ Troubleshooting guide addresses common errors and solutions
* ✅ CONTRIBUTING.md updated with architecture and development workflow
* ✅ API reference documents all public classes and functions
* ✅ Examples directory provides annotated real-world examples
* ✅ Mermaid diagrams visualize architecture and workflows
* ✅ All documentation cross-linked (easy navigation between guides)
* ✅ Documentation reviewed for clarity by someone unfamiliar with codebase

**Dependencies:**
- Issues 1-9 (all features to document)

**Breaking Changes:**
- None (documentation only)

**Testing:**
- Manual review: can a new contributor understand architecture from docs alone?
- Validation: do all code examples in docs actually work?
- Completeness check: are all CLI flags documented?
- Accuracy check: do diagrams match actual code flow?

**Documentation Standards:**
- Use Markdown with GitHub-flavored syntax
- Include code examples for all major concepts
- Use Mermaid for diagrams (renders in GitHub)
- Keep individual docs focused (<3000 words each)
- Cross-link related documents extensively
- Provide "Next Steps" or "See Also" sections

**Maintenance Plan:**
- Update docs in same PR as code changes (keep in sync)
- Add "Last Updated" date to each doc
- Review docs quarterly for accuracy
- Track documentation debt in issues

**Success Metrics:**
- New contributors can add a section handler without asking questions
- Contributors can create a new doc type template without code inspection
- 80% of support questions answerable from docs
- Zero critical features undocumented

**Notes:**
- Documentation is a first-class deliverable (not an afterthought)
- Good docs enable future you and future contributors
- Diagrams and examples provide clarity faster than prose
- This issue completes the refactor epic (Issues 1-10)

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

---

## Epic Summary & Milestones

### MVP Milestone (Issues 1-6)
After completing Issues 1-6, the system provides core value:
- New doc types can be added without code changes (metadata + handler registry)
- Workflow order is template-driven (flexible section sequencing)
- Unified processing loop eliminates duplication (single code path)
- LLM profiles enable consistent reasoning across doc types

**What Works:** Basic requirements automation with new architecture  
**What's Missing:** Review gates, completion validation, comprehensive docs/tests

### Production-Ready Milestone (Issues 1-11)
After completing all 11 issues, the system is production-ready:
- Review gates provide quality assurance checkpoints
- Completion criteria enable downstream automation integration
- Structural validation prevents document corruption
- Comprehensive documentation enables contributor onboarding
- Test suite ensures reliability and catches regressions

**What Works:** Full-featured, tested, documented automation system  
**What's Next:** Advanced features (artifact pipelines, multi-doc workflows, cross-doc review gates)

---

## Implementation Notes

### Issue Execution Order
Issues **must** be completed in strict sequential order (1-11) due to dependencies:
- Issues 1-2: Foundation (metadata, workflow order)
- Issue 3: Core orchestration (WorkflowRunner)
- Issues 4-6: Extensibility (registry, unified loop, profiles) - **MVP HERE**
- Issues 7-9: Quality & safety (review gates, completion, validation)
- Issue 10: Documentation (knowledge transfer)
- Issue 11: Testing (production readiness)

### Breaking Changes Summary
All breaking changes occur in template/document format, not external API:
- **Issue 1:** No breaking changes (fallback to default doc_type)
- **Issue 2:** ⚠️ Templates must include `<!-- workflow:order -->` block
- **Issue 3:** Internal API change (WorkflowRunner replaces phase functions)
- **Issue 4-8:** No breaking changes (new features, backward compatible)
- **Issue 9:** ⚠️ Documents with silent corruption now fail validation (improvement!)
- **Issue 10-11:** No breaking changes (docs and tests)

### Migration Path
1. Complete Issues 1-11 on feature branch
2. Update `docs/requirements.md` template with metadata + workflow order
3. Run migration script: `python tools/migrate_workflow_order.py`
4. Test migrated document: `python -m requirements_automation ... --dry-run`
5. Verify regression tests pass (phase equivalence maintained)
6. Merge to main, deprecate old phase files

### Deprecated Code Cleanup
After Issue 5 is complete and tested:
- Mark `phases/phase1.py` as deprecated (add warning)
- Mark `phases/phase2.py` as deprecated (add warning)
- Mark `validators.py` phase validation functions as deprecated
- Remove deprecated code after Issue 11 regression tests pass

### Future Work (Out of Scope for This Epic)
This refactor intentionally defers:
- **Artifact Pipelines:** JSON-first requirements, code generation from requirements
- **Multi-Document Workflows:** Cross-doc dependencies, multi-doc orchestration
- **Cross-Doc Review Gates:** Consistency checks spanning multiple documents
- **Conditional Workflows:** If/else logic in workflow order declarations
- **Parallel Processing:** Multiple sections processed per single run
- **Interactive Mode:** User prompts/confirmations during workflow execution
- **Custom Validators:** User-defined validation rules beyond structural checks
- **Workflow Visualization:** Graphical representation of workflow progress

---

*This plan favors mechanical determinism over cleverness. That's a feature, not a limitation.*
