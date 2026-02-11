"""Review Gate Handler for Document Quality Assurance.

This module provides the ReviewGateHandler class that executes LLM-powered
review of document sections. Review gates validate completeness, consistency,
and quality without mutating documents directly. They return structured results
(pass/fail, issues, optional patches) that can be reviewed and optionally applied.
"""
from __future__ import annotations
import logging
from typing import List, Dict, Tuple
from dataclasses import replace
from .models import HandlerConfig, ReviewIssue, ReviewPatch, ReviewResult
from .parsing import (
    find_sections, 
    get_section_span, 
    section_body, 
    extract_all_section_ids,
    extract_workflow_order,
    section_exists,
    contains_markers,
    apply_patch,
)
from .llm import LLMClient


class ReviewGateHandler:
    """Handler for executing review gate workflow targets."""
    
    def __init__(self, llm: LLMClient, lines: List[str], doc_type: str):
        """
        Initialize the review gate handler.
        
        Args:
            llm: LLMClient instance for AI operations
            lines: Document content as list of strings
            doc_type: Document type (requirements, research, planning)
        """
        self.llm = llm
        self.lines = lines
        self.doc_type = doc_type
    
    def execute_review(self, gate_id: str, config: HandlerConfig) -> ReviewResult:
        """
        Execute a review gate: analyze sections, return issues and patches.
        
        Args:
            gate_id: Review gate identifier
            config: Handler configuration for the review gate
            
        Returns:
            ReviewResult with pass/fail status, issues, and patches
        """
        # 1. Determine scope (which sections to review)
        scope_sections = self._determine_scope(gate_id, config.scope)
        
        # 2. Extract content for all scope sections
        section_contents = self._extract_sections(scope_sections)
        
        # 3. Call LLM to perform review
        review_data = self.llm.perform_review(
            gate_id=gate_id,
            doc_type=self.doc_type,
            section_contents=section_contents,
            llm_profile=config.llm_profile,
            validation_rules=config.validation_rules,
        )
        
        # 4. Parse LLM response into structured ReviewResult
        result = self._parse_review_response(gate_id, review_data, scope_sections)
        
        # 5. Validate patches (structural validation, not semantic)
        result = self._validate_patches(result)
        
        return result
    
    def _determine_scope(self, gate_id: str, scope_config: str) -> List[str]:
        """
        Determine which sections to include in review based on scope config.
        
        Args:
            gate_id: Review gate identifier
            scope_config: Scope configuration string
            
        Returns:
            List of section IDs to review
            
        Raises:
            ValueError: If scope_config is unknown or invalid
        """
        if scope_config == "all_prior_sections":
            # Get workflow order up to this gate
            workflow_order = extract_workflow_order(self.lines)
            if gate_id not in workflow_order:
                logging.warning(
                    f"Review gate '{gate_id}' not in workflow order, "
                    f"reviewing all sections"
                )
                return [s for s in extract_all_section_ids(self.lines) 
                       if not s.startswith("review_gate:")]
            
            gate_index = workflow_order.index(gate_id)
            return [s for s in workflow_order[:gate_index] 
                   if not s.startswith("review_gate:")]
        
        elif scope_config == "entire_document":
            # Get all section IDs in document
            return extract_all_section_ids(self.lines)
        
        elif scope_config.startswith("sections:"):
            # Explicit list: "sections:assumptions,constraints,requirements"
            section_list = scope_config.replace("sections:", "").split(",")
            return [s.strip() for s in section_list if s.strip()]
        
        else:
            raise ValueError(f"Unknown scope config: {scope_config}")
    
    def _extract_sections(self, section_ids: List[str]) -> Dict[str, str]:
        """
        Extract content for specified sections.
        
        Args:
            section_ids: List of section IDs to extract
            
        Returns:
            Dict mapping section IDs to their body content
        """
        spans = find_sections(self.lines)
        section_contents = {}
        
        for section_id in section_ids:
            span = get_section_span(spans, section_id)
            if span:
                body = section_body(self.lines, span)
                section_contents[section_id] = body
            else:
                logging.warning(f"Section '{section_id}' not found in document")
        
        return section_contents
    
    def _parse_review_response(
        self, gate_id: str, review_data: dict, scope_sections: List[str]
    ) -> ReviewResult:
        """
        Parse LLM review response into structured ReviewResult.
        
        Args:
            gate_id: Review gate identifier
            review_data: Raw review data from LLM
            scope_sections: Sections that were reviewed
            
        Returns:
            ReviewResult with parsed issues and patches
        """
        # Parse issues
        issues = []
        for issue_data in review_data.get("issues", []):
            if not isinstance(issue_data, dict):
                logging.warning(f"Invalid issue data: {issue_data}")
                continue
            
            issues.append(ReviewIssue(
                severity=issue_data.get("severity", "warning"),
                section=issue_data.get("section", "unknown"),
                description=issue_data.get("description", ""),
                suggestion=issue_data.get("suggestion"),
            ))
        
        # Parse patches
        patches = []
        for patch_data in review_data.get("patches", []):
            if not isinstance(patch_data, dict):
                logging.warning(f"Invalid patch data: {patch_data}")
                continue
            
            patches.append(ReviewPatch(
                section=patch_data.get("section", "unknown"),
                suggestion=patch_data.get("suggestion", ""),
                rationale=patch_data.get("rationale", ""),
                validated=False,  # Will be validated in next step
            ))
        
        # Determine if review passed (no blocker issues)
        passed = not any(issue.severity == "blocker" for issue in issues)
        
        return ReviewResult(
            gate_id=gate_id,
            passed=passed,
            issues=issues,
            patches=patches,
            scope_sections=scope_sections,
            summary=review_data.get("summary", "Review completed"),
        )
    
    def _validate_patches(self, result: ReviewResult) -> ReviewResult:
        """
        Validate patches structurally (not semantically).
        Check: target section exists, suggestion is non-empty, no structure markers.
        
        Args:
            result: ReviewResult with unvalidated patches
            
        Returns:
            ReviewResult with validated patches
        """
        validated_patches = []
        for patch in result.patches:
            # Check section exists
            if not section_exists(patch.section, self.lines):
                logging.warning(f"Patch targets unknown section: {patch.section}")
                validated_patches.append(replace(patch, validated=False))
                continue
            
            # Check suggestion is non-empty
            if not patch.suggestion.strip():
                logging.warning(f"Patch has empty suggestion: {patch.section}")
                validated_patches.append(replace(patch, validated=False))
                continue
            
            # Check suggestion doesn't contain structure markers
            if contains_markers(patch.suggestion):
                logging.warning(f"Patch contains structure markers: {patch.section}")
                validated_patches.append(replace(patch, validated=False))
                continue
            
            # Passed validation
            validated_patches.append(replace(patch, validated=True))
        
        return replace(result, patches=validated_patches)
    
    def apply_patches_if_configured(
        self, result: ReviewResult, config: HandlerConfig
    ) -> Tuple[List[str], bool]:
        """
        Optionally apply patches based on auto_apply_patches config.
        
        Args:
            result: ReviewResult with validated patches
            config: Handler configuration
            
        Returns:
            Tuple of (updated_lines, patches_applied)
            
        Raises:
            ValueError: If auto_apply_patches config is unknown
        """
        auto_apply = config.auto_apply_patches
        
        if auto_apply == "never":
            return self.lines, False
        
        if auto_apply == "if_validation_passes":
            if not all(p.validated for p in result.patches):
                logging.info("Patches not auto-applied: validation failed")
                return self.lines, False
        
        if auto_apply in ("always", "if_validation_passes"):
            updated_lines = self.lines
            patches_applied = 0
            
            for patch in result.patches:
                if patch.validated:
                    try:
                        updated_lines = apply_patch(
                            patch.section, patch.suggestion, updated_lines
                        )
                        logging.info(f"Auto-applied patch to {patch.section}")
                        patches_applied += 1
                    except Exception as e:
                        logging.error(f"Failed to apply patch to {patch.section}: {e}")
            
            return updated_lines, patches_applied > 0
        
        raise ValueError(f"Unknown auto_apply_patches config: {auto_apply}")
    
    def write_review_gate_result(
        self, result: ReviewResult, lines: List[str]
    ) -> Tuple[List[str], bool]:
        """
        Write review gate result marker to document.
        
        Args:
            result: ReviewResult to persist
            lines: Document lines to update
            
        Returns:
            Tuple of (updated_lines, changed) where changed indicates if marker was added/updated
        """
        # Count blocker issues and warnings
        blocker_count = sum(1 for issue in result.issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in result.issues if issue.severity == "warning")
        
        # Determine status
        status = "passed" if result.passed else "failed"
        
        # Create result marker
        marker = (
            f"<!-- review_gate_result:{result.gate_id} "
            f"status={status} "
            f"issues={blocker_count} "
            f"warnings={warning_count} -->"
        )
        
        # Find where to insert the marker - at the beginning of the document
        # (after metadata but before first section)
        insert_index = 0
        
        # Skip past metadata and workflow order blocks
        in_comment = False
        for i, line in enumerate(lines):
            # Check if we're entering or exiting a comment block
            if "<!--" in line:
                if "-->" not in line:
                    in_comment = True
                # else: single-line comment, don't change in_comment state
            # Check if we're exiting a comment block
            if in_comment and "-->" in line:
                in_comment = False
                insert_index = i + 1
                continue
            # If we hit a section marker or non-comment content, stop
            if not in_comment and line.strip() and not line.strip().startswith("<!--"):
                break
            if not in_comment:
                insert_index = i + 1
        
        # Check if result marker already exists for this gate
        from .config import REVIEW_GATE_RESULT_RE
        new_lines = []
        marker_replaced = False
        marker_changed = False
        
        for line in lines:
            m = REVIEW_GATE_RESULT_RE.search(line)
            if m and m.group("gate_id") == result.gate_id:
                # Replace existing marker only if it's different
                if line.strip() != marker.strip():
                    new_lines.append(marker)
                    marker_changed = True
                else:
                    new_lines.append(line)
                marker_replaced = True
            else:
                new_lines.append(line)
        
        if not marker_replaced:
            # Insert new marker
            new_lines = lines[:insert_index] + [marker] + lines[insert_index:]
            return new_lines, True
        
        return new_lines, marker_changed
