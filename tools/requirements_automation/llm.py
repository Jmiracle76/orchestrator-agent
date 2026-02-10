from __future__ import annotations
import json, os, re
from typing import List
from .config import MODEL, MAX_TOKENS
from .models import OpenQuestion

def extract_json_object(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    first, last = t.find("{"), t.rfind("}")
    if first != -1 and last != -1 and last > first:
        return t[first:last+1].strip()
    raise ValueError("No JSON object found in LLM output")

class LLMClient:
    def __init__(self, model: str = MODEL, max_tokens: int = MAX_TOKENS) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = self._make_client()

    @staticmethod
    def _make_client():
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("anthropic package not installed (pip install anthropic)") from e
        return Anthropic()

    def _call(self, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    def generate_open_questions(self, section_id: str, section_context: str) -> List[dict]:
        prompt = f'''
You are a requirements assistant. Produce ONLY valid JSON.

TASK:
Generate clarifying questions needed to fill the section "{section_id}".

RULES:
- Do NOT edit the document.
- Do NOT include markdown tables.
- Output JSON with this exact shape:

{{
  "questions": [
    {{
      "question": "string",
      "section_target": "string (must be a valid section id, default to {section_id})",
      "rationale": "string (short)"
    }}
  ]
}}

CONTEXT (current section text):
\"\"\"{section_context}\"\"\"

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
            qt = (q.get("question") or "").strip()
            st = (q.get("section_target") or section_id).strip()
            rat = (q.get("rationale") or "").strip()
            if qt:
                cleaned.append({"question": qt, "section_target": st, "rationale": rat})
        return cleaned

    def integrate_answers(self, section_id: str, section_context: str, answered_questions: List[OpenQuestion]) -> str:
        qa = "\n".join(f"- {q.question_id}: {q.question}\n  Answer: {q.answer}" for q in answered_questions)
        prompt = f'''
You are a requirements assistant.

TASK:
Integrate the provided Q&A into section "{section_id}".
Return ONLY the updated section body text (data-plane). No markers, no section headers, no lock tags.

RULES:
- Keep it crisp and requirements-style.
- Remove placeholder wording.
- If answers conflict, do NOT guess: add a short "Open issues" note at end describing the conflict (do not create table rows).

CURRENT SECTION TEXT:
\"\"\"{section_context}\"\"\"

ANSWERED QUESTIONS:
{qa}

Return updated body text only.
'''
        return self._call(prompt).strip()
