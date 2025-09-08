from typing import Dict, Optional, List, Any
from .base import BaseProvider, AIResult
from .gpt5 import Gpt5Provider
from .gemini import GeminiProvider


class CompositeProvider(BaseProvider):
    """Route capabilities: GPT-5 for plan/write; Gemini for revise/formatting."""

    def __init__(self, gpt: BaseProvider | None = None, gemini: BaseProvider | None = None):
        self.gpt = gpt or Gpt5Provider()
        self.gemini = gemini or GeminiProvider()

    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        return self.gpt.plan(grant_url=grant_url, text_spec=text_spec)

    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        return self.gpt.write(section_id=section_id, answers=answers, file_refs=file_refs, deterministic=deterministic)

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        return self.gemini.revise(
            base_text=base_text,
            change_request=change_request,
            file_refs=file_refs,
            deterministic=deterministic,
        )

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        return self.gemini.format_final(
            full_text=full_text,
            template_hint=template_hint,
            file_refs=file_refs,
            deterministic=deterministic,
        )
