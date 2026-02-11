"""Document Validator for Completion Criteria.

This module provides the DocumentValidator class that checks whether a document
meets all completion criteria required for downstream automation processing.
"""
from __future__ import annotations
import logging
from typing import List, Set
from .models import CompletionCheck, CompletionStatus, HandlerConfig
from .config import (
    COMPLETION_CRITERIA,
    OPTIONAL_CRITERIA,
    PLACEHOLDER_TOKEN,
    is_special_workflow_target,
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    QUESTION_STATUS_DEFERRED,
)
from .parsing import (
    find_sections,
    get_section_span,
    has_placeholder,
    extract_review_gate_results,
    find_duplicate_section_markers,
    validate_open_questions_table_schema,
)
from .open_questions import open_questions_parse
from .handler_registry import HandlerRegistry


class DocumentValidator:
    """Validates document completion criteria."""
    
    def __init__(
        self,
        lines: List[str],
        workflow_order: List[str],
        handler_registry: HandlerRegistry,
        doc_type: str,
    ):
        """
        Initialize the document validator.
        
        Args:
            lines: Document content as list of strings
            workflow_order: List of workflow targets in order
            handler_registry: Handler registry for section configs
            doc_type: Document type (requirements, research, planning)
        """
        self.lines = lines
        self.workflow_order = workflow_order
        self.registry = handler_registry
        self.doc_type = doc_type
    
    def validate_completion(self, strict: bool = False) -> CompletionStatus:
        """
        Check all completion criteria and return structured status.
        
        Args:
            strict: If True, apply optional strict criteria
            
        Returns:
            CompletionStatus with overall status and individual checks
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
        
        summary = self._build_summary(complete, checks, blocking_failures, warnings)
        
        return CompletionStatus(
            complete=complete,
            checks=checks,
            blocking_failures=blocking_failures,
            warnings=warnings,
            summary=summary,
        )
    
    def _check_no_placeholders(self) -> CompletionCheck:
        """Check that no required sections contain PLACEHOLDER token."""
        required_sections = self._get_required_sections()
        sections_with_placeholders = []
        
        spans = find_sections(self.lines)
        for section_id in required_sections:
            span = get_section_span(spans, section_id)
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
            blocking=True,
        )
    
    def _check_no_open_questions(self, strict: bool) -> CompletionCheck:
        """Check that no questions remain unanswered."""
        try:
            open_questions, _, _ = open_questions_parse(self.lines)
        except Exception as e:
            logging.warning("Failed to parse open questions: %s", e)
            return CompletionCheck(
                criterion="no_open_questions",
                passed=False,
                details=f"Failed to parse Open Questions table: {e}",
                blocking=True,
            )
        
        if strict:
            # Strict mode: even Deferred questions count as incomplete
            incomplete = [
                q for q in open_questions 
                if q.status in (QUESTION_STATUS_OPEN, QUESTION_STATUS_DEFERRED)
            ]
        else:
            # Normal mode: only Open questions count
            incomplete = [q for q in open_questions if q.status == QUESTION_STATUS_OPEN]
        
        passed = len(incomplete) == 0
        if passed:
            details = "All questions resolved"
        else:
            question_ids = [q.question_id for q in incomplete[:5]]
            suffix = f" (showing first 5 of {len(incomplete)})" if len(incomplete) > 5 else ""
            details = f"{len(incomplete)} questions remain: {', '.join(question_ids)}{suffix}"
        
        return CompletionCheck(
            criterion="no_open_questions",
            passed=passed,
            details=details,
            blocking=True,
        )
    
    def _check_review_gates_pass(self, strict: bool) -> CompletionCheck:
        """Check that all review gates in workflow have passed."""
        review_gates = [
            t for t in self.workflow_order if t.startswith("review_gate:")
        ]
        
        if not review_gates:
            return CompletionCheck(
                criterion="all_review_gates_pass",
                passed=True,
                details="No review gates in workflow",
                blocking=False,
            )
        
        # Retrieve review gate results from document markers
        gate_results = extract_review_gate_results(self.lines)
        
        failed_gates = []
        for gate_id in review_gates:
            if gate_id not in gate_results:
                # Gate not yet executed
                failed_gates.append(f"{gate_id} (not executed)")
            else:
                status, issues, warnings = gate_results[gate_id]
                if status == "failed":
                    failed_gates.append(f"{gate_id} (failed)")
                elif strict and warnings > 0:
                    failed_gates.append(f"{gate_id} ({warnings} warnings)")
        
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
            blocking=True,
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
            blocking=True,
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
                if not self._section_complete(target):
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
            blocking=True,
        )
    
    def _get_required_sections(self) -> List[str]:
        """
        Determine which sections are required based on doc_type and workflow.
        For now: all non-review-gate targets in workflow are required.
        Future: support optional sections via metadata.
        """
        return [
            t for t in self.workflow_order
            if not is_special_workflow_target(t)
        ]
    
    def _find_missing_workflow_sections(self) -> List[str]:
        """Find workflow targets that don't exist in the document."""
        spans = find_sections(self.lines)
        existing_sections = {sp.section_id for sp in spans}
        
        missing = []
        for target in self.workflow_order:
            if is_special_workflow_target(target):
                # Skip review gates - they don't need section markers
                continue
            if target not in existing_sections:
                missing.append(target)
        
        return missing
    
    def _review_gate_passed(self, gate_id: str) -> bool:
        """Check if a review gate has passed."""
        gate_results = extract_review_gate_results(self.lines)
        
        if gate_id not in gate_results:
            # Gate not executed yet
            return False
        
        status, issues, warnings = gate_results[gate_id]
        return status == "passed"
    
    def _section_complete(self, section_id: str) -> bool:
        """Check if a section is complete (no placeholder, no open questions)."""
        spans = find_sections(self.lines)
        span = get_section_span(spans, section_id)
        
        if not span:
            return False
        
        # Check for placeholder
        if has_placeholder(span, self.lines):
            return False
        
        # Check for open questions targeting this section
        try:
            open_qs, _, _ = open_questions_parse(self.lines)
        except Exception:
            # If we can't parse questions, consider incomplete
            return False
        
        # Import here to avoid circular dependency
        from .config import TARGET_CANONICAL_MAP
        from .parsing import find_subsections_within
        
        def _canon_target(t: str) -> str:
            t0 = (t or "").strip()
            return TARGET_CANONICAL_MAP.get(t0, t0)
        
        # Include subsections when checking questions
        subs = find_subsections_within(self.lines, span)
        target_ids = {section_id} | {s.subsection_id for s in subs}
        
        for q in open_qs:
            if q.status.strip() == QUESTION_STATUS_OPEN and _canon_target(q.section_target) in target_ids:
                return False
        
        return True
    
    def _build_summary(
        self,
        complete: bool,
        checks: List[CompletionCheck],
        blocking_failures: List[str],
        warnings: List[str],
    ) -> str:
        """Build human-readable summary of completion status."""
        lines = []
        
        # Header
        status_text = "COMPLETE" if complete else "INCOMPLETE"
        lines.append(f"Document Completion Status: {status_text}")
        lines.append("")
        
        # Individual checks
        for check in checks:
            icon = "✅" if check.passed else "❌"
            lines.append(f"{icon} {check.details}")
        
        # Blocking issues summary
        if blocking_failures:
            lines.append("")
            lines.append("Blocking Issues:")
            for criterion in blocking_failures:
                # Find the check for this criterion to get details
                check = next((c for c in checks if c.criterion == criterion), None)
                if check:
                    lines.append(f"- {check.details}")
        
        # Warnings
        if warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in warnings:
                lines.append(f"- {warning}")
        
        # Footer message
        if not complete:
            lines.append("")
            lines.append(
                "Document cannot proceed to downstream automation until all criteria met."
            )
        
        return "\n".join(lines)
