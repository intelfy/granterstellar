from typing import Dict, Optional, List, Any
from .base import BaseProvider, AIResult
from ai.validators import (
    validate_planner_output,
    validate_writer_output,
    validate_reviser_output,
    validate_formatter_output,
    SchemaError,
)
from .util import summarize_file_refs
from ai.context_budget import apply_context_budget


class Gpt5Provider(BaseProvider):
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        sections = [
            {"id": "summary", "title": "Executive Summary", "questions": ["objective", "impact", "outcomes"]},
            {"id": "narrative", "title": "Project Narrative", "questions": ["background", "approach", "risks"]},
            {"id": "budget", "title": "Budget", "questions": ["items", "totals", "justification"]},
        ]
        payload = {"schema_version": "v1", "source": grant_url or "text", "sections": sections, "model": "gpt-5"}
        try:
            validate_planner_output(payload)
        except SchemaError:
            # In stub context just raise; real provider would attempt repair
            raise
        return payload

    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        # Placeholder: retrieval & memory not yet passed into provider; budget manager still invoked for future parity.
        budget = apply_context_budget(
            retrieval=[],
            memory=[],
            file_refs=file_refs or [],
            model_max_tokens=None,
        )
        draft = f"[gpt-5] Draft for {section_id}:\n" + "\n".join(f"- {k}: {v}" for k, v in answers.items())
        ctx = summarize_file_refs(budget.file_refs)
        payload = {"draft": draft + ctx}
        validate_writer_output(payload)
        return AIResult(text=payload["draft"], usage_tokens=0, model_id="gpt-5")

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
        text = base_text + "\n\n[gpt-5] Changes: " + change_request
        ctx = summarize_file_refs(budget.file_refs)
        payload = {"revised": text + ctx, "diff": {"added": [], "removed": []}}
        validate_reviser_output(payload)
        return AIResult(text=payload["revised"], usage_tokens=0, model_id="gpt-5")

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
        ctx = summarize_file_refs(budget.file_refs)
        payload = {"formatted_markdown": full_text + ctx}
        validate_formatter_output(payload)
        return AIResult(text=payload["formatted_markdown"], usage_tokens=0, model_id="gpt-5")
