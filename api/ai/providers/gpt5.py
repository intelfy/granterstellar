from typing import Dict, Optional, List, Any
from .base import BaseProvider, AIResult
from .util import summarize_file_refs


class Gpt5Provider(BaseProvider):
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        sections = [
            {"id": "summary", "title": "Executive Summary", "inputs": ["objective", "impact", "outcomes"]},
            {"id": "narrative", "title": "Project Narrative", "inputs": ["background", "approach", "risks"]},
            {"id": "budget", "title": "Budget", "inputs": ["items", "totals", "justification"]},
        ]
        return {"schema_version": "v1", "source": grant_url or "text", "sections": sections, "model": "gpt-5"}

    def write(self, *, section_id: str, answers: Dict[str, str], file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        draft = (
            f"[gpt-5] Draft for {section_id}:\n" + "\n".join(f"- {k}: {v}" for k, v in answers.items())
        )
        ctx = summarize_file_refs(file_refs)
        return AIResult(text=draft + ctx, usage_tokens=0, model_id="gpt-5")

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        text = base_text + "\n\n[gpt-5] Changes: " + change_request
        ctx = summarize_file_refs(file_refs)
        return AIResult(text=text + ctx, usage_tokens=0, model_id="gpt-5")

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        return AIResult(text=full_text, usage_tokens=0, model_id="gpt-5")
