from __future__ import annotations
import logging
import re
from typing import List, Optional, Dict
from .models import WorkflowResult, SectionState, SectionSpan, SubsectionSpan
from .config import PHASES, is_special_workflow_target, PLACEHOLDER_TOKEN, REVIEW_GATE_RESULT_RE
from .parsing import find_sections, get_section_span, section_is_locked, section_is_blank, find_subsections_within, section_body, section_text
from .open_questions import open_questions_parse, open_questions_resolve, open_questions_insert
from .config import TARGET_CANONICAL_MAP
from .phases import process_phase_1, process_phase_2, process_placeholder_phase
from .review_gate_handler import ReviewGateHandler
from .formatting import format_review_gate_output
from .editing import replace_block_body_preserving_markers
from .utils_io import iso_today


def _canon_target(t: str) -> str:
    """Normalize alias section IDs to canonical targets."""
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)


def _get_replacement_end_boundary(lines: List[str], section_span: SectionSpan, subsections: List[SubsectionSpan]) -> int:
    """
    Calculate the effective end boundary for section body replacement.
    
    If the section contains an 'open_questions' subsection, returns the line
    where that subsection starts to prevent overwriting it. Otherwise, returns
    the original section end boundary.
    
    Args:
        lines: Document content as list of strings
        section_span: SectionSpan object for the section
        subsections: List of SubsectionSpan objects within the section
        
    Returns:
        Line number to use as end boundary for replacement
    """
    # Check if there's an open_questions subsection
    for sub in subsections:
        if sub.subsection_id == "open_questions":
            # Return the start line of the open_questions subsection as the boundary
            return sub.start_line
    
    # No open_questions subsection found, use the full section span
    return section_span.end_line


class WorkflowRunner:
    """
    Single, reusable workflow runner that replaces phase-specific branching logic.
    Iterates workflow targets in template-declared order, executes only the first
    incomplete target per run, and stops deterministically.
    """

    def __init__(
        self,
        lines: List[str],
        llm,
        doc_type: str,
        workflow_order: List[str],
        handler_registry=None,  # Placeholder for Issue 4
    ):
        """
        Initialize the workflow runner.

        Args:
            lines: Document content as list of strings
            llm: LLMClient instance for AI operations
            doc_type: Document type (requirements, research, planning)
            workflow_order: List of target IDs to process in order
            handler_registry: Handler registry (stub for now, will be used in Issue 4)
        """
        self.lines = lines
        self.llm = llm
        self.doc_type = doc_type
        self.workflow_order = workflow_order
        self.handler_registry = handler_registry

    def _get_section_state(self, target_id: str) -> SectionState:
        """
        Extract section state for decision-making.

        Args:
            target_id: Section ID to analyze

        Returns:
            SectionState object with section information
        """
        spans = find_sections(self.lines)
        span = get_section_span(spans, target_id)

        if not span:
            return SectionState(
                section_id=target_id,
                exists=False,
                locked=False,
                is_blank=False,
                has_placeholder=False,
                has_open_questions=False,
                has_answered_questions=False,
            )

        locked = section_is_locked(self.lines, span)
        is_blank = section_is_blank(self.lines, span)

        # Check for placeholder token
        has_placeholder = any(
            PLACEHOLDER_TOKEN in line
            for line in self.lines[span.start_line : span.end_line]
        )

        # Check for open questions targeting this section
        try:
            open_qs, _, _ = open_questions_parse(self.lines)
        except Exception as e:
            logging.warning("Failed to parse open questions: %s", e)
            open_qs = []

        # Include subsections when checking questions
        subs = find_subsections_within(self.lines, span)
        target_ids = {target_id} | {s.subsection_id for s in subs}

        targeted_questions = [
            q for q in open_qs if _canon_target(q.section_target) in target_ids
        ]

        has_open_questions = any(
            q.status.strip() in ("Open", "Deferred")
            and q.answer.strip() in ("", "-", "Pending")
            for q in targeted_questions
        )

        # Note: Questions with status "Open"/"Deferred" and non-empty answers
        # are considered "answered but not yet integrated". After integration,
        # they are marked as "Resolved" by the phase processors.
        has_answered_questions = any(
            q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
            for q in targeted_questions
        )

        return SectionState(
            section_id=target_id,
            exists=True,
            locked=locked,
            is_blank=is_blank,
            has_placeholder=has_placeholder,
            has_open_questions=has_open_questions,
            has_answered_questions=has_answered_questions,
        )

    def _execute_section(
        self, target_id: str, state: SectionState, dry_run: bool
    ) -> WorkflowResult:
        """
        Execute processing for a section target.

        Uses handler registry to determine section processing behavior.
        Falls back to phase-based logic if handler_registry is not provided.

        Args:
            target_id: Section ID to process
            state: Section state information
            dry_run: Whether to run in dry-run mode

        Returns:
            WorkflowResult with execution details
        """
        # Try to get handler config from registry
        handler_config = None
        if self.handler_registry:
            try:
                handler_config = self.handler_registry.get_handler_config(
                    self.doc_type, target_id
                )
                logging.debug(
                    "Using handler config for %s: mode=%s, output_format=%s",
                    target_id,
                    handler_config.mode,
                    handler_config.output_format,
                )
            except Exception as e:
                logging.warning(
                    "Failed to get handler config for %s: %s. Falling back to phase logic.",
                    target_id,
                    e,
                )
        
        # Check if this is a review gate (special handling)
        if handler_config and handler_config.mode == "review_gate":
            # Execute review gate
            handler = ReviewGateHandler(self.llm, self.lines, self.doc_type)
            review_result = handler.execute_review(target_id, handler_config)
            
            # Write review gate result marker to document
            self.lines, marker_changed = handler.write_review_gate_result(review_result, self.lines)
            
            # Sync handler state with updated document lines (now includes result marker)
            handler.lines = self.lines
            
            # Optionally apply patches
            self.lines, patches_applied = handler.apply_patches_if_configured(
                review_result, handler_config
            )
            
            # Convert to WorkflowResult
            result = WorkflowResult(
                target_id=target_id,
                action_taken="review_gate",
                changed=marker_changed or patches_applied,
                blocked=not review_result.passed,
                blocked_reasons=[
                    f"{i.severity}: {i.description}" 
                    for i in review_result.issues 
                    if i.severity == "blocker"
                ],
                summaries=[review_result.summary] + [
                    f"{i.severity}: {i.description}" 
                    for i in review_result.issues
                ],
                questions_generated=0,
                questions_resolved=0,
            )
            
            # Log formatted output for human readability
            formatted_output = format_review_gate_output(result)
            if formatted_output:
                print(formatted_output)
            
            return result
        
        # Check if this uses integrate_then_questions or questions_then_integrate mode
        # If so, use unified handler logic driven by handler config
        if handler_config and handler_config.mode in ("integrate_then_questions", "questions_then_integrate"):
            return self._execute_unified_handler(target_id, state, handler_config, dry_run)
        
        # For sections without handler config, fall back to phase-based logic
        
        # Map section to phase for backward compatibility
        phase_name = None
        for phase, sections in PHASES.items():
            if target_id in sections:
                phase_name = phase
                break

        if not phase_name:
            # Unknown section, use placeholder processor
            self.lines, changed, blocked, needs_human, summaries = (
                process_placeholder_phase(target_id, self.lines, self.llm, dry_run)
            )
            return WorkflowResult(
                target_id=target_id,
                action_taken="placeholder",
                changed=changed,
                blocked=len(blocked) > 0,
                blocked_reasons=blocked,
                summaries=summaries,
                questions_generated=0,
                questions_resolved=0,
            )

        # Count questions before processing
        try:
            open_qs_before, _, _ = open_questions_parse(self.lines)
            questions_before = len(
                [
                    q
                    for q in open_qs_before
                    if _canon_target(q.section_target) == target_id
                ]
            )
        except Exception:
            questions_before = 0

        # Call appropriate phase processor
        if phase_name == "phase_1_intent_scope":
            self.lines, changed, blocked, needs_human, summaries = process_phase_1(
                self.lines, self.llm, dry_run, target_section=target_id
            )
        elif phase_name == "phase_2_assumptions_constraints":
            self.lines, changed, blocked, needs_human, summaries = process_phase_2(
                self.lines, self.llm, dry_run, target_section=target_id
            )
        else:
            self.lines, changed, blocked, needs_human, summaries = (
                process_placeholder_phase(target_id, self.lines, self.llm, dry_run)
            )

        # Count questions after processing
        try:
            open_qs_after, _, _ = open_questions_parse(self.lines)
            questions_after = len(
                [
                    q
                    for q in open_qs_after
                    if _canon_target(q.section_target) == target_id
                ]
            )
            resolved_count = 0
            # Count resolved questions from summaries
            # TODO (Issue 5): This is fragile string parsing. Replace with
            # structured return data from unified handlers.
            for summary in summaries:
                if "resolved" in summary.lower():
                    # Try to extract count from summary
                    match = re.search(r"(\d+)\s+questions?\s+resolved", summary.lower())
                    if match:
                        resolved_count = int(match.group(1))
        except Exception:
            questions_after = 0
            resolved_count = 0

        questions_generated = max(0, questions_after - questions_before)

        # Determine action taken
        action = "no_action"
        if questions_generated > 0:
            action = "question_gen"
        elif resolved_count > 0 or changed:
            action = "integration"

        return WorkflowResult(
            target_id=target_id,
            action_taken=action,
            changed=changed,
            blocked=len(blocked) > 0,
            blocked_reasons=blocked,
            summaries=summaries,
            questions_generated=questions_generated,
            questions_resolved=resolved_count,
        )

    def _gather_prior_sections(self, target_id: str) -> dict[str, str]:
        """
        Gather completed prior section content before the target section.
        
        Iterates through workflow_order up to (but not including) target_id,
        skips review gates, checks if each section is complete (no placeholder,
        no open questions), and extracts the section body.
        
        Args:
            target_id: Section ID to gather prior sections for
            
        Returns:
            Dict mapping section_id → body content for all completed prior sections
        """
        prior_sections = {}
        
        # Find the index of target_id in workflow_order
        try:
            target_index = self.workflow_order.index(target_id)
        except ValueError:
            # Target not in workflow order, return empty dict
            return prior_sections
        
        # Parse sections once for efficiency
        spans = find_sections(self.lines)
        
        # Iterate through sections before target_id
        for section_id in self.workflow_order[:target_index]:
            # Skip review gates
            if is_special_workflow_target(section_id):
                continue
            
            # Check if section is complete
            state = self._get_section_state(section_id)
            
            # Section must exist, not be blank, have no placeholder, and no open questions
            if not state.exists:
                continue
            if state.has_placeholder or state.has_open_questions:
                continue
            
            # Extract section body
            span = get_section_span(spans, section_id)
            
            if span:
                body = section_body(self.lines, span)
                # Only include non-empty sections
                if body.strip():
                    prior_sections[section_id] = body
        
        return prior_sections

    def _execute_unified_handler(
        self, target_id: str, state: SectionState, handler_config, dry_run: bool
    ) -> WorkflowResult:
        """
        Execute unified handler using handler config parameters.
        
        This implements the integrate-then-questions pattern using configuration
        from the handler registry, replacing hardcoded phase-specific logic.
        
        Args:
            target_id: Section ID to process
            state: Section state information
            handler_config: Handler configuration from registry
            dry_run: Whether to run in dry-run mode
            
        Returns:
            WorkflowResult with execution details
        """
        changed = False
        blocked_reasons = []
        summaries = []
        questions_generated = 0
        questions_resolved = 0
        
        # Gather prior completed sections for context based on scope config
        # - scope: current_section → empty dict (no prior context)
        # - scope: all_prior_sections → gather all prior completed sections
        if handler_config.scope == "all_prior_sections":
            prior_sections = self._gather_prior_sections(target_id)
        else:
            # For current_section scope or any other scope, don't pass prior context
            prior_sections = {}
        
        # Get current section span
        spans = find_sections(self.lines)
        span = get_section_span(spans, target_id)
        
        if not span:
            return WorkflowResult(
                target_id=target_id,
                action_taken="error",
                changed=False,
                blocked=True,
                blocked_reasons=[f"Section span not found: {target_id}"],
                summaries=[],
                questions_generated=0,
                questions_resolved=0,
            )
        
        # Parse open questions
        try:
            open_qs, _, _ = open_questions_parse(self.lines)
        except Exception as e:
            logging.warning("Failed to parse open questions: %s", e)
            open_qs = []
        
        # Include subsections when checking questions
        subs = find_subsections_within(self.lines, span)
        target_ids = {target_id} | {s.subsection_id for s in subs}
        
        targeted_questions = [
            q for q in open_qs if _canon_target(q.section_target) in target_ids
        ]
        
        # Find questions with answers (status "Open"/"Deferred" with non-empty answers)
        answered_questions = [
            q for q in targeted_questions
            if q.answer.strip() not in ("", "-", "Pending")
            and q.status.strip() in ("Open", "Deferred")
        ]
        
        # Find questions without answers
        open_unanswered = [
            q for q in targeted_questions
            if q.status.strip() in ("Open", "Deferred")
            and q.answer.strip() in ("", "-", "Pending")
        ]
        
        # Step 1: If section has answered questions, integrate them
        if answered_questions:
            logging.info(
                "Integrating %d answered questions into section: %s",
                len(answered_questions),
                target_id,
            )
            
            # Group questions by target (section or subsection)
            by_target: Dict[str, List] = {}
            for q in answered_questions:
                tgt = _canon_target(q.section_target)
                by_target.setdefault(tgt, []).append(q)
            
            any_integrated = False
            for tgt, qs in by_target.items():
                # Get the span for this target (section or subsection)
                if tgt == target_id:
                    target_start = span.start_line
                    # Check if section contains open_questions subsection
                    # If it does, stop replacement before that subsection
                    target_end = _get_replacement_end_boundary(self.lines, span, subs)
                else:
                    # Find subsection span
                    subspan = None
                    for s in subs:
                        if s.subsection_id == tgt:
                            subspan = s
                            break
                    if not subspan:
                        logging.warning(
                            "Answered questions target '%s' but no matching subsection exists; skipping.",
                            tgt,
                        )
                        continue
                    target_start, target_end = subspan.start_line, subspan.end_line
                
                # Get current context for this target
                context = "\n".join(self.lines[target_start:target_end])
                
                # Call LLM to integrate answers using handler config parameters
                new_body = self.llm.integrate_answers(
                    tgt,
                    context,
                    qs,
                    llm_profile=handler_config.llm_profile,
                    output_format=handler_config.output_format,
                    prior_sections=prior_sections,
                )
                
                if new_body.strip() and new_body.strip() != context.strip():
                    if not dry_run:
                        self.lines = replace_block_body_preserving_markers(
                            self.lines,
                            target_start,
                            target_end,
                            section_id=tgt,
                            new_body=new_body,
                        )
                        # Update spans after modification
                        spans = find_sections(self.lines)
                    any_integrated = True
            
            if any_integrated:
                changed = True
                questions_resolved = len(answered_questions)
                
                # Mark questions as resolved
                qids = [q.question_id for q in answered_questions]
                if not dry_run:
                    try:
                        self.lines, resolved = open_questions_resolve(self.lines, qids)
                        if resolved:
                            summaries.append(
                                f"Integrated {len(answered_questions)} answers; resolved {resolved} questions"
                            )
                            # Re-parse questions after resolving
                            try:
                                open_qs, _, _ = open_questions_parse(self.lines)
                            except Exception:
                                open_qs = []
                    except Exception as e:
                        logging.warning("Failed to resolve questions: %s", e)
                        summaries.append(
                            f"Integrated {len(answered_questions)} answers (questions table not available)"
                        )
                
                # Update span after integration
                spans = find_sections(self.lines)
                span = get_section_span(spans, target_id)
        
        # Step 2: Check if section is still blank after integration
        # A section is blank if it contains the PLACEHOLDER token
        is_blank = section_is_blank(self.lines, span)
        
        # Step 2.5: If section is blank and prior context is available, try drafting first
        # Skip drafting if answered_questions exist because Step 1 just integrated them,
        # and we should give the integration a chance to complete the section before drafting.
        # Drafting is only appropriate when starting from a completely blank section.
        if is_blank and prior_sections and not answered_questions:
            logging.info(
                "Section '%s' is blank with prior context available; attempting to draft content",
                target_id,
            )
            
            try:
                ctx = section_body(self.lines, span)
                draft = self.llm.draft_section(
                    target_id,
                    ctx,
                    prior_sections,
                    llm_profile=handler_config.llm_profile,
                    output_format=handler_config.output_format,
                )
                
                if draft.strip() and draft.strip() != ctx.strip():
                    if not dry_run:
                        # Calculate effective end boundary to preserve open_questions subsection
                        # Using subs calculated earlier (integration step doesn't run when drafting)
                        draft_end = _get_replacement_end_boundary(self.lines, span, subs)
                        
                        # Write the draft to the section body
                        self.lines = replace_block_body_preserving_markers(
                            self.lines,
                            span.start_line,
                            draft_end,
                            section_id=target_id,
                            new_body=draft,
                        )
                        # Update spans after modification
                        spans = find_sections(self.lines)
                        span = get_section_span(spans, target_id)
                    
                    changed = True
                    summaries.append(f"Drafted initial content for {target_id} using prior section context")
                    
                    # Re-check if section is still blank after drafting
                    is_blank = section_is_blank(self.lines, span)
                    logging.info(
                        "Draft completed for '%s'; section is_blank=%s",
                        target_id,
                        is_blank,
                    )
                else:
                    logging.info(
                        "Draft for '%s' was empty or unchanged; will fall through to question generation",
                        target_id,
                    )
            except Exception as e:
                logging.warning("Failed to draft section '%s': %s; falling back to question generation", target_id, e)
        
        # Step 3: If section is blank and no open questions exist, generate new ones
        if is_blank:
            # Re-check for unanswered questions after integration
            try:
                open_qs, _, _ = open_questions_parse(self.lines)
                targeted_questions = [
                    q for q in open_qs if _canon_target(q.section_target) in target_ids
                ]
                open_unanswered = [
                    q for q in targeted_questions
                    if q.status.strip() in ("Open", "Deferred")
                    and q.answer.strip() in ("", "-", "Pending")
                ]
            except Exception as e:
                logging.warning("Failed to parse open questions: %s", e)
                open_qs = []
                open_unanswered = []
            
            if not open_unanswered:
                # Generate new questions
                logging.info(
                    "Section '%s' is blank and has no open questions; generating questions",
                    target_id,
                )
                
                ctx = section_body(self.lines, span)
                proposed = self.llm.generate_open_questions(
                    target_id,
                    ctx,
                    llm_profile=handler_config.llm_profile,
                    prior_sections=prior_sections,
                )
                
                new_qs = []
                for item in proposed:
                    q_text = (item.get("question") or "").strip()
                    q_target = _canon_target(
                        (item.get("section_target") or target_id).strip()
                    )
                    # Validate that target is this section or a subsection
                    if q_target not in target_ids:
                        q_target = target_id
                    if q_text:
                        new_qs.append((q_text, q_target, iso_today()))
                
                if new_qs and not dry_run:
                    try:
                        self.lines, inserted = open_questions_insert(self.lines, new_qs)
                        if inserted:
                            changed = True
                            questions_generated = inserted
                            summaries.append(
                                f"Generated {inserted} open questions for {target_id}"
                            )
                    except Exception as e:
                        logging.warning("Failed to insert open questions: %s", e)
                        summaries.append(
                            f"Generated {len(new_qs)} questions but could not insert (no questions table)"
                        )
            else:
                # Section is blank but has open questions - blocked waiting for answers
                logging.info(
                    "Section '%s' is blank but has %d open questions; waiting for answers",
                    target_id,
                    len(open_unanswered),
                )
                blocked_reasons.append(
                    f"Waiting for {len(open_unanswered)} questions to be answered"
                )
        
        # Determine action taken
        action = "no_action"
        if questions_generated > 0:
            action = "question_gen"
        elif questions_resolved > 0 or changed:
            action = "integration"
        
        return WorkflowResult(
            target_id=target_id,
            action_taken=action,
            changed=changed,
            blocked=len(blocked_reasons) > 0,
            blocked_reasons=blocked_reasons,
            summaries=summaries,
            questions_generated=questions_generated,
            questions_resolved=questions_resolved,
        )

    def run_once(self, dry_run: bool = False) -> WorkflowResult:
        """
        Execute the first incomplete workflow target.

        Algorithm:
        1. Iterate workflow_order from start
        2. For each target_id:
           - Get section state (locked, placeholder, has_questions, has_answers)
           - If locked → skip, continue to next
           - If review_gate → call review handler (placeholder for Issue 7), return result
           - If complete (no placeholder, no open questions) → skip, continue
           - If incomplete → call section handler, return result
        3. If all targets complete → return result with action="complete"

        Args:
            dry_run: If True, don't modify document or persist changes

        Returns:
            WorkflowResult with execution details
        """
        for target_id in self.workflow_order:
            # Handle special workflow targets (e.g., review gates)
            if is_special_workflow_target(target_id):
                # Check handler registry for review gate config
                if self.handler_registry:
                    try:
                        handler_config = self.handler_registry.get_handler_config(
                            self.doc_type, target_id
                        )
                        if handler_config.mode == "review_gate":
                            # Fix 2: Check if review gate already passed
                            # Note: For large documents with many review gates, consider caching
                            # gate results in a dictionary for better performance
                            gate_already_passed = False
                            for line in self.lines:
                                m = REVIEW_GATE_RESULT_RE.search(line)
                                if m and m.group("gate_id") == target_id and m.group("status") == "passed":
                                    gate_already_passed = True
                                    logging.info("Review gate '%s' already passed, skipping", target_id)
                                    break
                            
                            if gate_already_passed:
                                # Skip this gate and continue to next workflow target
                                continue
                            
                            # Execute review gate
                            handler = ReviewGateHandler(self.llm, self.lines, self.doc_type)
                            review_result = handler.execute_review(target_id, handler_config)
                            
                            # Fix 1: Write review gate result marker to document
                            self.lines, marker_changed = handler.write_review_gate_result(review_result, self.lines)
                            
                            # Sync handler state with updated document lines (now includes result marker)
                            handler.lines = self.lines
                            
                            # Optionally apply patches
                            self.lines, patches_applied = handler.apply_patches_if_configured(
                                review_result, handler_config
                            )
                            
                            # Convert to WorkflowResult
                            result = WorkflowResult(
                                target_id=target_id,
                                action_taken="review_gate",
                                changed=marker_changed or patches_applied,
                                blocked=not review_result.passed,
                                blocked_reasons=[
                                    f"{i.severity}: {i.description}" 
                                    for i in review_result.issues 
                                    if i.severity == "blocker"
                                ],
                                summaries=[review_result.summary] + [
                                    f"{i.severity}: {i.description}" 
                                    for i in review_result.issues
                                ],
                                questions_generated=0,
                                questions_resolved=0,
                            )
                            
                            # Log formatted output for human readability
                            formatted_output = format_review_gate_output(result)
                            if formatted_output:
                                print(formatted_output)
                            
                            return result
                        else:
                            logging.warning(
                                "Special target '%s' has non-review_gate mode: %s",
                                target_id,
                                handler_config.mode,
                            )
                    except Exception as e:
                        logging.warning(
                            "Failed to get handler config for special target '%s': %s",
                            target_id,
                            e,
                        )
                
                return WorkflowResult(
                    target_id=target_id,
                    action_taken="skip_special",
                    changed=False,
                    blocked=True,
                    blocked_reasons=[f"Special target '{target_id}' not implemented"],
                    summaries=[f"Skipped special target: {target_id}"],
                    questions_generated=0,
                    questions_resolved=0,
                )

            # Get section state
            state = self._get_section_state(target_id)

            # Skip if section doesn't exist (shouldn't happen after validation)
            if not state.exists:
                logging.warning("Section '%s' not found in document", target_id)
                continue

            # Skip locked sections
            if state.locked:
                logging.info("Section '%s' is locked, skipping", target_id)
                continue

            # Skip completed sections (no placeholder, no open questions)
            # A section is complete if it has content (not blank, no placeholder) and no open questions
            if not state.has_placeholder and not state.has_open_questions:
                logging.debug("Section '%s' is complete, skipping", target_id)
                continue

            # Section is incomplete, process it
            logging.info("Processing incomplete section: %s", target_id)
            result = self._execute_section(target_id, state, dry_run)
            return result

        # All targets complete
        last_target = self.workflow_order[-1] if self.workflow_order else "none"
        logging.info("All workflow targets complete")
        return WorkflowResult(
            target_id=last_target,
            action_taken="complete",
            changed=False,
            blocked=False,
            blocked_reasons=[],
            summaries=["All workflow targets complete"],
            questions_generated=0,
            questions_resolved=0,
        )

    def run_until_blocked(
        self, dry_run: bool = False, max_steps: int = 10
    ) -> List[WorkflowResult]:
        """
        Execute workflow targets until blocked or complete.

        Useful for automated CI pipelines processing multiple sections.

        Args:
            dry_run: If True, don't modify document or persist changes
            max_steps: Maximum number of iterations (default: 10)

        Returns:
            List of WorkflowResult objects, one per iteration
        """
        results = []

        for step in range(max_steps):
            logging.info("Run step %d/%d", step + 1, max_steps)
            result = self.run_once(dry_run)
            results.append(result)

            # Stop if blocked, complete, or no changes
            if result.blocked or result.action_taken == "complete":
                logging.info(
                    "Stopping after %d steps: %s", step + 1, result.action_taken
                )
                break

            if not result.changed:
                logging.info("No changes in step %d, stopping", step + 1)
                break

        return results
