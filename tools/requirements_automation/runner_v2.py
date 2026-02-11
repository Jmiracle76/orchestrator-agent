from __future__ import annotations
import logging
import re
from typing import List, Optional
from .models import WorkflowResult, SectionState
from .config import PHASES, is_special_workflow_target, PLACEHOLDER_TOKEN
from .parsing import find_sections, get_section_span, section_is_locked, section_is_blank, find_subsections_within
from .open_questions import open_questions_parse
from .config import TARGET_CANONICAL_MAP
from .phases import process_phase_1, process_phase_2, process_placeholder_phase


def _canon_target(t: str) -> str:
    """Normalize alias section IDs to canonical targets."""
    t0 = (t or "").strip()
    return TARGET_CANONICAL_MAP.get(t0, t0)


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
        
        # If we have a handler config, use it to dispatch
        if handler_config:
            # For now, we still use the old phase processors but log the handler config
            # Future Issue 5 will implement unified handlers that use the full config
            if handler_config.mode == "review_gate":
                # Review gates not yet implemented (Issue 7)
                logging.info("Review gate '%s' not yet implemented", target_id)
                return WorkflowResult(
                    target_id=target_id,
                    action_taken="skip_special",
                    changed=False,
                    blocked=True,
                    blocked_reasons=[f"Review gate '{target_id}' not implemented"],
                    summaries=[f"Skipped review gate: {target_id}"],
                    questions_generated=0,
                    questions_resolved=0,
                )
        
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
                            # Review gates not yet implemented (Issue 7)
                            logging.info("Review gate '%s' configured but not yet implemented", target_id)
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
