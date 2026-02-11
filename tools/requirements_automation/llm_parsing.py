"""JSON parsing utilities for LLM responses."""

import re


def extract_json_object(text: str) -> str:
    """Extract a JSON object from LLM output that may include extra prose.

    Args:
        text: LLM response text that may contain JSON

    Returns:
        Extracted JSON string

    Raises:
        ValueError: If no JSON object found in the text
    """
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
        return t[first : last + 1].strip()
    raise ValueError("No JSON object found in LLM output")
