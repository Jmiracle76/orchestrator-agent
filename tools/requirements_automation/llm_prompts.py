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

    lines = ["## Previously Completed Sections"]
    lines.append("")
    lines.append("Use the following completed sections as context when formulating new questions.")
    lines.append("Avoid asking questions that have already been answered in these sections.")
    lines.append("")

    for section_id, content in prior_sections.items():
        # Format section ID as readable title
        title = section_id.replace("_", " ").title()
        lines.append(f"### {title}")
        lines.append(content.strip())
        lines.append("")

    return "\n".join(lines)


def _build_base_format_guidance(output_format: str) -> str:
    """Build base format guidance string from output_format.
    
    Args:
        output_format: Output format hint ("prose", "bullets", "subsections")
        
    Returns:
        Base format guidance string
    """
    format_guidance_map = {
        "prose": "Write content as flowing prose paragraphs.",
        "bullets": "Write content as a bullet list (dash-prefixed, one item per line).",
        "subsections": "Organize content under appropriate subsection headers (###).",
    }
    return format_guidance_map.get(output_format, "Write content as prose.")


def _build_subsection_guidance_for_questions(subsection_structure: Optional[List[dict]]) -> str:
    """Build simpler subsection guidance for question generation prompts.
    
    Args:
        subsection_structure: Optional list of subsection dicts with 'id' and 'type' keys
        
    Returns:
        Subsection guidance string for questions, or empty string if no subsections
    """
    if not subsection_structure:
        return ""
    
    guidance = "\n\n**Subsection Structure:**\nThis section has the following subsections:\n"
    for sub in subsection_structure:
        sub_id = sub.get("id", "")
        sub_type = sub.get("type", "prose")
        guidance += f"- `{sub_id}`: {sub_type}\n"
    guidance += "\nWhen generating questions, target them to the appropriate subsection using section_target.\n"
    
    return guidance


def _build_subsection_guidance(subsection_structure: Optional[List[dict]]) -> str:
    """Build subsection structure guidance for LLM prompts.
    
    Args:
        subsection_structure: Optional list of subsection dicts with 'id' and 'type' keys
        
    Returns:
        Subsection guidance string, or empty string if no subsections
    """
    if not subsection_structure:
        return ""
    
    guidance = "\n\n**Subsection Structure:**\n"
    guidance += "This section has the following subsections. Output content using subsection delimiters:\n"
    for sub in subsection_structure:
        sub_id = sub.get("id", "")
        sub_type = sub.get("type", "prose")
        # Convert subsection_id to readable header
        readable_header = sub_id.replace("_", " ").title()
        guidance += f"\n### {readable_header}\n"
        if sub_type == "table":
            guidance += "Output: Markdown table rows only (no header, just data rows with pipe delimiters).\n"
        elif sub_type == "bullets":
            guidance += "Output: Bullet list items (dash-prefixed).\n"
        else:
            guidance += "Output: Prose or list as appropriate.\n"
    
    return guidance


def build_open_questions_prompt(
    section_id: str,
    section_context: str,
    full_profile: str,
    prior_sections: Optional[dict[str, str]] = None,
    subsection_structure: Optional[List[dict]] = None,
) -> str:
    """Build prompt for generating open questions.

    Args:
        section_id: Section identifier
        section_context: Current section content
        full_profile: LLM profile text
        prior_sections: Optional dict of completed section IDs to their content
        subsection_structure: Optional list of subsection dicts with 'id' and 'type' keys

    Returns:
        Formatted prompt string
    """
    # Build document context if prior sections provided
    doc_context = ""
    if prior_sections:
        doc_context = f"\n\n{format_prior_sections(prior_sections)}\n"

    # Build subsection structure guidance if provided
    subsection_guidance = _build_subsection_guidance_for_questions(subsection_structure)

    # Update task instruction based on whether context is present
    task_instruction = (
        """Generate 2-5 clarifying questions that:
- Fill gaps in the current section
- Build on information from prior sections
- Do NOT repeat questions already answered in prior sections
- Help establish clear, testable requirements"""
        if prior_sections
        else "Generate 2-5 clarifying questions to help complete this section."
    )

    return f'''
{full_profile}
{doc_context}
---

## Task: Generate Clarifying Questions

Section ID: {section_id}
{subsection_guidance}

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
    subsection_structure: Optional[List[dict]] = None,
) -> str:
    """Build prompt for integrating answered questions into section.

    Args:
        section_id: Section identifier
        section_context: Current section content
        answered_questions: List of OpenQuestion objects with answers
        full_profile: LLM profile text
        output_format: Output format hint ("prose", "bullets", "subsections")
        prior_sections: Optional dict of completed section IDs to their content
        subsection_structure: Optional list of subsection dicts with 'id' and 'type' keys

    Returns:
        Formatted prompt string
    """
    # Build format guidance - combine base format with subsection-specific guidance
    format_guidance = _build_base_format_guidance(output_format) + _build_subsection_guidance(subsection_structure)

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
    subsection_structure: Optional[List[dict]] = None,
) -> str:
    """Build prompt for drafting initial section content from prior context.

    Args:
        section_id: Section identifier
        section_context: Current section content (typically contains placeholder)
        prior_sections: Dict of completed section IDs to their content
        full_profile: LLM profile text
        output_format: Output format hint ("prose", "bullets", "subsections")
        subsection_structure: Optional list of subsection dicts with 'id' and 'type' keys

    Returns:
        Formatted prompt string
    """
    # Build format guidance - combine base format with subsection-specific guidance
    format_guidance = _build_base_format_guidance(output_format) + _build_subsection_guidance(subsection_structure)

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
