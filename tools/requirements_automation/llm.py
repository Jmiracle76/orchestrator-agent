from __future__ import annotations
import json
import logging
import os
import re
from typing import List
from .config import MODEL, MAX_TOKENS
from .models import OpenQuestion
from .profile_loader import ProfileLoader

def extract_json_object(text: str) -> str:
    """Extract a JSON object from LLM output that may include extra prose."""
    t = (text or "").strip()
    # Prefer JSON embedded in a markdown code fence, if present.
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fall back to raw braces if the entire response is JSON.
    if t.startswith("{") and t.endswith("}"):
        return t
    # Final attempt: slice the first to last braces in the response.
    first, last = t.find("{"), t.rfind("}")
    if first != -1 and last != -1 and last > first:
        return t[first:last+1].strip()
    raise ValueError("No JSON object found in LLM output")

class LLMClient:
    """Thin wrapper around the Anthropic client with prompt helpers."""
    def __init__(self, model: str = MODEL, max_tokens: int = MAX_TOKENS) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = self._make_client()
        self.profile_loader = ProfileLoader()

    @staticmethod
    def _make_client():
        # Require credentials and SDK before attempting to call the API.
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("anthropic package not installed (pip install anthropic)") from e
        return Anthropic()

    def _call(self, prompt: str) -> str:
        # Execute a single prompt and return the assistant's raw text.
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    def generate_open_questions(self, section_id: str, section_context: str, llm_profile: str = "requirements") -> List[dict]:
        """Ask the LLM to propose clarifying questions for a blank section.
        
        Args:
            section_id: Section identifier
            section_context: Current section content
            llm_profile: Profile name to use (default: "requirements")
            
        Returns:
            List of question dictionaries with fields: question, section_target, rationale
        """
        # Load profile
        full_profile = self.profile_loader.build_full_profile(llm_profile)
        
        prompt = f'''
{full_profile}

---

## Task: Generate Clarifying Questions

Section ID: {section_id}

Current Section Content:
"""{section_context}"""

Generate 2-5 clarifying questions to help complete this section.
Output JSON with this exact shape:

{{
  "questions": [
    {{
      "question": "string",
      "section_target": "string (must be a valid section id, default to {section_id})",
      "rationale": "string (short)"
    }}
  ]
}}

Return JSON only. No prose.
'''
        raw = self._call(prompt).strip()
        payload = extract_json_object(raw)
        data = json.loads(payload)
        qs = data.get("questions", [])
        if not isinstance(qs, list):
            return []
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

    def integrate_answers(self, section_id: str, section_context: str, answered_questions: List[OpenQuestion], llm_profile: str = "requirements", output_format: str = "prose") -> str:
        """Ask the LLM to rewrite a section using the provided Q&A context.
        
        Args:
            section_id: Section identifier
            section_context: Current section content
            answered_questions: List of OpenQuestion objects with answers
            llm_profile: Profile name to use (default: "requirements")
            output_format: Output format hint ("prose", "bullets", "subsections")
            
        Returns:
            Rewritten section body text
        """
        # Load profile
        full_profile = self.profile_loader.build_full_profile(llm_profile)
        
        # Build format guidance
        format_guidance = {
            "prose": "Write integrated content as flowing prose paragraphs.",
            "bullets": "Write integrated content as a bullet list (dash-prefixed, one item per line).",
            "subsections": "Organize content under appropriate subsection headers (###)."
        }.get(output_format, "Write integrated content as prose.")
        
        qa = "\n".join(f"- {q.question_id}: {q.question}\n  Answer: {q.answer}" for q in answered_questions)
        prompt = f'''
{full_profile}

---

## Task: Integrate Answers into Section

Section ID: {section_id}
Output Format: {format_guidance}

Current Section Content:
"""{section_context}"""

Answered Questions:
{qa}

Rewrite the section incorporating answers. Remove placeholder wording.
Output only the rewritten section body (no markers, no headers, no lock tags).
'''
        return self._call(prompt).strip()

    def perform_review(self, gate_id: str, doc_type: str, section_contents: dict, 
                      llm_profile: str, validation_rules: List[str]) -> dict:
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
        
        # Build sections text
        sections_text = "\n\n".join([
            f"## Section: {sid}\n{content}"
            for sid, content in section_contents.items()
        ])
        
        prompt = f'''
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

Return JSON only. No prose.
'''
        
        raw = self._call(prompt).strip()
        payload = extract_json_object(raw)
        return json.loads(payload)
