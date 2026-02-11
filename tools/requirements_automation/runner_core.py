"""Core workflow runner implementation."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from .config import REVIEW_GATE_RESULT_RE, is_special_workflow_target
from .handler_registry import HandlerRegistry
from .models import WorkflowResult
from .runner_handlers import (
    execute_phase_based_handler,
    execute_review_gate,
    execute_unified_handler,
)
from .runner_state import gather_prior_sections, get_section_state
from .versioning import (
    get_current_version,
    get_version_for_section,
    should_increment_version,
    update_document_version,
)


class WorkflowRunner:
    """
    Single, reusable workflow runner that replaces phase-specific branching logic.
    Iterates workflow targets in template-declared order, executes only the first
    incomplete target per run, and stops deterministically.
    """

    def __init__(
        self,
        lines: List[str],
        llm: Any,
        doc_type: str,
        workflow_order: List[str],
        handler_registry: Optional[HandlerRegistry] = None,
    ) -> None:
        """
        Initialize the workflow runner.

        Args:
            lines: Document content as list of strings
            llm: LLMClient instance for AI operations
            doc_type: Document type (requirements, research, planning)
            workflow_order: List of target IDs to process in order
            handler_registry: Handler registry instance
        """
        self.lines = lines
        self.llm = llm
        self.doc_type = doc_type
        self.workflow_order = workflow_order
        self.handler_registry = handler_registry

    def _check_and_update_version(self, target_id: str, result: WorkflowResult) -> None:
        """Check if version should be updated after processing a target.

        Args:
            target_id: Target ID that was just processed
            result: WorkflowResult from processing the target
        """
        # Only update version if something changed and action was successful
        if not result.changed:
            return

        # Skip version update for certain actions that don't complete sections
        if result.action_taken in ("skip_locked", "no_action", "skip_special"):
            return

        # Get current version
        current_version = get_current_version(self.lines)

        # Check if version should increment
        if should_increment_version(target_id, current_version):
            new_version = get_version_for_section(target_id)

            # Create change description based on target type
            if target_id.startswith("review_gate:"):
                changes = (
                    f"{target_id.replace('review_gate:', '').replace('_', ' ').title()} completed"
                )
            else:
                changes = f"{target_id.replace('_', ' ').title()} completed"

            # Update document version
            self.lines = update_document_version(self.lines, new_version, changes)
            logging.info("Document version updated: %s -> %s", current_version, new_version)

    def _execute_section(self, target_id: str, state: Any, dry_run: bool) -> WorkflowResult:
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
                handler_config = self.handler_registry.get_handler_config(self.doc_type, target_id)
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
            self.lines, result = execute_review_gate(
                self.lines, target_id, self.llm, self.doc_type, handler_config, dry_run
            )
            return result

        # Check if this uses integrate_then_questions or questions_then_integrate mode
        # If so, use unified handler logic driven by handler config
        if handler_config and handler_config.mode in (
            "integrate_then_questions",
            "questions_then_integrate",
        ):
            # Gather prior completed sections for context based on scope config
            if handler_config.scope == "all_prior_sections":
                prior_sections = gather_prior_sections(self.lines, self.workflow_order, target_id)
            else:
                # For current_section scope or any other scope, don't pass prior context
                prior_sections = {}

            self.lines, result = execute_unified_handler(
                self.lines, target_id, state, self.llm, handler_config, prior_sections, dry_run
            )
            return result

        # For sections without handler config, fall back to phase-based logic
        self.lines, result = execute_phase_based_handler(self.lines, target_id, self.llm, dry_run)
        return result

    def run_once(self, dry_run: bool = False) -> WorkflowResult:
        """
        Execute the first incomplete workflow target.

        Algorithm:
        1. Iterate workflow_order from start
        2. For each target_id:
           - Get section state (locked, placeholder, has_questions, has_answers)
           - If locked → skip, continue to next
           - If review_gate → call review handler, return result
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
                            # Check if review gate already passed
                            gate_already_passed = False
                            for line in self.lines:
                                m = REVIEW_GATE_RESULT_RE.search(line)
                                if (
                                    m
                                    and m.group("gate_id") == target_id
                                    and m.group("status") == "passed"
                                ):
                                    gate_already_passed = True
                                    logging.info(
                                        "Review gate '%s' already passed, skipping", target_id
                                    )
                                    break

                            if gate_already_passed:
                                # Skip this gate and continue to next workflow target
                                continue

                            # Execute review gate
                            self.lines, result = execute_review_gate(
                                self.lines,
                                target_id,
                                self.llm,
                                self.doc_type,
                                handler_config,
                                dry_run,
                            )

                            # Check and update version if review gate passed
                            self._check_and_update_version(target_id, result)

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
            state = get_section_state(self.lines, target_id)

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

            # Check and update version if section completed successfully
            self._check_and_update_version(target_id, result)

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

    def run_until_blocked(self, dry_run: bool = False, max_steps: int = 10) -> List[WorkflowResult]:
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
                logging.info("Stopping after %d steps: %s", step + 1, result.action_taken)
                break

            if not result.changed:
                logging.info("No changes in step %d, stopping", step + 1)
                break

        return results
