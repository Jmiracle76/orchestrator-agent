"""Prompt building and formatting utilities for LLM interactions."""

from __future__ import annotations

from typing import List, Optional

from .models import OpenQuestion


def format_prior_sections(prior_sections: dict) -> str:
    """Format prior_sections dict into a Document Context block.

    Args:
        prior_sections: Dict mapping section IDs to their content

    Returns:
        Formatted markdown string with document context
    """
    if not prior_sections:
        return ""

    lines = ["## Document Context (completed sections)"]
    for section_id, content in prior_sections.items():
        lines.append(f"### {section_id}")
        lines.append(content.strip())
    return "\n".join(lines)


def build_open_questions_prompt(
    section_id: str, section_context: str, full_profile: str, prior_sections: Optional[dict[str, str]] = None
) -> str:
    """Build prompt for generating open questions.

    Args:
        section_id: Section identifier
        section_context: Current section content
        full_profile: LLM profile text
        prior_sections: Optional dict of completed section IDs to their content

    Returns:
        Formatted prompt string
    """
    # Build document context if prior sections provided
    doc_context = ""
    if prior_sections:
        doc_context = f"\n\n{format_prior_sections(prior_sections)}\n"

    # Update task instruction based on whether context is present
    task_instruction = (
        "Given the document context above, generate 2-5 clarifying questions to help complete this section."
        if prior_sections
        else "Generate 2-5 clarifying questions to help complete this section."
    )

    return f'''
{full_profile}
{doc_context}
---

## Task: Generate Clarifying Questions

Section ID: {section_id}

Current Section Content:
"""{section_context}"""

{task_instruction}
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


def build_integrate_answers_prompt(
    section_id: str,
    section_context: str,
    answered_questions: List[OpenQuestion],
    full_profile: str,
    output_format: str = "prose",
    prior_sections: Optional[dict[str, str]] = None,
) -> str:
    """Build prompt for integrating answered questions into section.

    Args:
        section_id: Section identifier
        section_context: Current section content
        answered_questions: List of OpenQuestion objects with answers
        full_profile: LLM profile text
        output_format: Output format hint ("prose", "bullets", "subsections")
        prior_sections: Optional dict of completed section IDs to their content

    Returns:
        Formatted prompt string
    """
    # Build format guidance
    format_guidance = {
        "prose": "Write integrated content as flowing prose paragraphs.",
        "bullets": "Write integrated content as a bullet list (dash-prefixed, one item per line).",
        "subsections": "Organize content under appropriate subsection headers (###).",
    }.get(output_format, "Write integrated content as prose.")

    # Build document context if prior sections provided
    doc_context = ""
    if prior_sections:
        doc_context = f"\n\n{format_prior_sections(prior_sections)}\n"

    # Update task instruction based on whether context is present
    task_instruction = (
        "Using the document context and answered questions, rewrite the section incorporating answers."
        if prior_sections
        else "Rewrite the section incorporating answers."
    )

    qa = "\n".join(
        f"- {q.question_id}: {q.question}\n  Answer: {q.answer}" for q in answered_questions
    )

    return f'''
{full_profile}
{doc_context}
---

## Task: Integrate Answers into Section

Section ID: {section_id}
Output Format: {format_guidance}

Current Section Content:
"""{section_context}"""

Answered Questions:
{qa}

{task_instruction} Remove placeholder wording.
Output only the rewritten section body (no markers, no headers, no lock tags).
'''


def build_draft_section_prompt(
    section_id: str,
    section_context: str,
    prior_sections: dict[str, str],
    full_profile: str,
    output_format: str = "prose",
) -> str:
    """Build prompt for drafting initial section content from prior context.

    Args:
        section_id: Section identifier
        section_context: Current section content (typically contains placeholder)
        prior_sections: Dict of completed section IDs to their content
        full_profile: LLM profile text
        output_format: Output format hint ("prose", "bullets", "subsections")

    Returns:
        Formatted prompt string
    """
    # Build format guidance
    format_guidance = {
        "prose": "Write content as flowing prose paragraphs.",
        "bullets": "Write content as a bullet list (dash-prefixed, one item per line).",
        "subsections": "Organize content under appropriate subsection headers (###).",
    }.get(output_format, "Write content as prose.")

    # Build document context - this is required for drafting
    doc_context = ""
    if prior_sections:
        doc_context = f"\n\n{format_prior_sections(prior_sections)}\n"

    return f'''
{full_profile}
{doc_context}
---

## Task: Draft Section Content from Prior Context

Section ID: {section_id}
Output Format: {format_guidance}

Current Section Content (for structural reference):
"""{section_context}"""

Based on the document context above, draft initial content for the {section_id} section.
Synthesize the content from what is already known in the completed sections.
Be thorough but stay within what can be reasonably inferred from the prior context.
If something truly cannot be determined from the context, note it but still draft what you can.
Remove any placeholder wording.
Output only the section body (no markers, no headers, no lock tags).
'''


def build_review_prompt(
    gate_id: str,
    doc_type: str,
    section_contents: dict,
    full_profile: str,
    validation_rules: List[str],
) -> str:
    """Build prompt for reviewing multiple sections.

    Args:
        gate_id: Review gate identifier
        doc_type: Document type (e.g., "requirements")
        section_contents: Dict mapping section IDs to their content
        full_profile: LLM profile text
        validation_rules: List of validation rules to apply

    Returns:
        Formatted prompt string
    """
    # Build sections text
    sections_text = "\n\n".join(
        [f"## Section: {sid}\n{content}" for sid, content in section_contents.items()]
    )

    return f"""
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
"""
