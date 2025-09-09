from typing import Dict, Optional, List, Any

from .base import BaseProvider, AIResult
from ai.validators import (
    validate_planner_output,
    validate_writer_output,
    validate_reviser_output,
    validate_formatter_output,
)
from .util import summarize_file_refs
from ai.context_budget import apply_context_budget


class GeminiProvider(BaseProvider):
    """Gemini stub provider with role output validation wrappers."""

    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        payload: Dict[str, Any] = {
            "schema_version": "v1",
            "source": grant_url or "text",
            "sections": [],  # Gemini stub returns no sections here (alternate planner)
            "model": "gemini",
        }
        validate_planner_output(payload)
        return payload

    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        budget = apply_context_budget(
            retrieval=[],
            memory=[],
            file_refs=file_refs or [],
            model_max_tokens=None,
        )
        content = "\n".join(f"- {k}: {v}" for k, v in answers.items())
        det = " deterministic=1" if deterministic else ""
        ctx = summarize_file_refs(budget.file_refs)
        payload = {"draft": f"[gemini:formatted{det}] {section_id}\n{content}" + ctx}
        validate_writer_output(payload)
        return AIResult(text=payload["draft"], usage_tokens=0, model_id="gemini")

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        budget = apply_context_budget(
            retrieval=[],
            memory=[],
            file_refs=file_refs or [],
            model_max_tokens=None,
        )
        formatted = base_text.strip() + "\n\n[gemini:polish] " + change_request.strip()
        det = " deterministic=1" if deterministic else ""
        ctx = summarize_file_refs(budget.file_refs)
        payload = {"revised": formatted + det + ctx, "diff": {"added": [], "removed": []}}
        validate_reviser_output(payload)
        return AIResult(text=payload["revised"], usage_tokens=0, model_id="gemini")

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        budget = apply_context_budget(
            retrieval=[],
            memory=[],
            file_refs=file_refs or [],
            model_max_tokens=None,
        )
        hint = f" template={template_hint}" if template_hint else ""
        det = " deterministic=1" if deterministic else ""
        ctx = summarize_file_refs(budget.file_refs)
        payload = {"formatted_markdown": f"[gemini:final_format{hint}{det}]\n\n{full_text}" + ctx}
        validate_formatter_output(payload)
        return AIResult(text=payload["formatted_markdown"], usage_tokens=0, model_id="gemini")
