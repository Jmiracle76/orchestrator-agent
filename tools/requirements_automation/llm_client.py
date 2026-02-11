"""LLM client for API interactions."""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional

from .config import MAX_TOKENS, MODEL
from .llm_parsing import extract_json_object
from .llm_prompts import (
    build_draft_section_prompt,
    build_integrate_answers_prompt,
    build_open_questions_prompt,
    build_review_prompt,
)
from .models import OpenQuestion
from .profile_loader import ProfileLoader


class LLMClient:
    """Thin wrapper around the Anthropic client with prompt helpers."""

    def __init__(self, model: str = MODEL, max_tokens: int = MAX_TOKENS) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = self._make_client()
        self.profile_loader = ProfileLoader()

    @staticmethod
    def _make_client() -> Any:
        """Create and return Anthropic API client."""
        # Require credentials and SDK before attempting to call the API.
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("anthropic package not installed (pip install anthropic)") from e
        return Anthropic()

    def _call(self, prompt: str) -> str:
        """Execute a single prompt and return the assistant's raw text.

        Args:
            prompt: Text prompt to send to the LLM

        Returns:
            LLM response text
        """
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return str(resp.content[0].text)

    def generate_open_questions(
        self,
        section_id: str,
        section_context: str,
        llm_profile: str = "requirements",
        prior_sections: Optional[dict[str, str]] = None,
    ) -> List[dict]:
        """Ask the LLM to propose clarifying questions for a blank section.

        Args:
            section_id: Section identifier
            section_context: Current section content
            llm_profile: Profile name to use (default: "requirements")
            prior_sections: Optional dict of completed section IDs to their content

        Returns:
            List of question dictionaries with fields: question, section_target, rationale
        """
        # Load profile
        full_profile = self.profile_loader.build_full_profile(llm_profile)

        # Build prompt
        prompt = build_open_questions_prompt(
            section_id, section_context, full_profile, prior_sections
        )

        # Call LLM
        raw = self._call(prompt).strip()
        payload = extract_json_object(raw)
        data = json.loads(payload)
        qs = data.get("questions", [])
        if not isinstance(qs, list):
            return []

        # Clean and normalize questions
        cleaned = []
        for q in qs:
            if not isinstance(q, dict):
                continue
            # Normalize fields and drop empty/invalid entries.
            qt = (q.get("question") or "").strip()
            st = (q.get("section_target") or section_id).strip()
            rat = (q.get("rationale") or "").strip()
            if qt:
                cleaned.append({"question": qt, "section_target": st, "rationale": rat})
        return cleaned

    def integrate_answers(
        self,
        section_id: str,
        section_context: str,
        answered_questions: List[OpenQuestion],
        llm_profile: str = "requirements",
        output_format: str = "prose",
        prior_sections: Optional[dict[str, str]] = None,
    ) -> str:
        """Ask the LLM to rewrite a section using the provided Q&A context.

        Args:
            section_id: Section identifier
            section_context: Current section content
            answered_questions: List of OpenQuestion objects with answers
            llm_profile: Profile name to use (default: "requirements")
            output_format: Output format hint ("prose", "bullets", "subsections")
            prior_sections: Optional dict of completed section IDs to their content

        Returns:
            Rewritten section body text
        """
        # Load profile
        full_profile = self.profile_loader.build_full_profile(llm_profile)

        # Build prompt
        prompt = build_integrate_answers_prompt(
            section_id,
            section_context,
            answered_questions,
            full_profile,
            output_format,
            prior_sections,
        )

        return self._call(prompt).strip()

    def draft_section(
        self,
        section_id: str,
        section_context: str,
        prior_sections: dict[str, str],
        llm_profile: str = "requirements",
        output_format: str = "prose",
    ) -> str:
        """Draft initial section content from prior section context.

        This is distinct from integrate_answers() because it has no Q&A pairs to integrate.
        Instead, it synthesizes content directly from what is known in prior sections.

        Args:
            section_id: Section identifier
            section_context: Current section content (typically contains placeholder)
            prior_sections: Dict of completed section IDs to their content
            llm_profile: Profile name to use (default: "requirements")
            output_format: Output format hint ("prose", "bullets", "subsections")

        Returns:
            Drafted section body text
        """
        # Load profile
        full_profile = self.profile_loader.build_full_profile(llm_profile)

        # Build prompt
        prompt = build_draft_section_prompt(
            section_id, section_context, prior_sections, full_profile, output_format
        )

        return self._call(prompt).strip()

    def perform_review(
        self,
        gate_id: str,
        doc_type: str,
        section_contents: dict,
        llm_profile: str,
        validation_rules: List[str],
    ) -> dict:
        """Ask the LLM to review multiple sections and return structured feedback.

        Args:
            gate_id: Review gate identifier
            doc_type: Document type (e.g., "requirements")
            section_contents: Dict mapping section IDs to their content
            llm_profile: Profile name to use for review
            validation_rules: List of validation rules to apply

        Returns:
            Dict with review results including pass/fail, issues, patches, and summary
        """
        # Load review profile
        full_profile = self.profile_loader.build_full_profile(llm_profile)

        # Build prompt
        prompt = build_review_prompt(
            gate_id, doc_type, section_contents, full_profile, validation_rules
        )

        raw = self._call(prompt).strip()
        payload = extract_json_object(raw)
        result: dict[Any, Any] = json.loads(payload)
        return result
