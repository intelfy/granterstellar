from typing import Dict, Optional, List, Any
from .base import BaseProvider, AIResult
from .util import summarize_file_refs


class GeminiProvider(BaseProvider):
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        return {"schema_version": "v1", "source": grant_url or "text", "sections": [], "model": "gemini"}

    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        content = "\n".join(f"- {k}: {v}" for k, v in answers.items())
        det = " deterministic=1" if deterministic else ""
        return AIResult(text=f"[gemini:formatted{det}] {section_id}\n{content}", usage_tokens=0, model_id="gemini")

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        formatted = base_text.strip() + "\n\n[gemini:polish] " + change_request.strip()
        det = " deterministic=1" if deterministic else ""
        ctx = summarize_file_refs(file_refs)
        return AIResult(text=formatted + det + ctx, usage_tokens=0, model_id="gemini")

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        hint = f" template={template_hint}" if template_hint else ""
        det = " deterministic=1" if deterministic else ""
        return AIResult(text=f"[gemini:final_format{hint}{det}]\n\n{full_text}", usage_tokens=0, model_id="gemini")
