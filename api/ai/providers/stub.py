from typing import Dict, Optional, List, Any
from .base import BaseProvider, AIResult


class LocalStubProvider(BaseProvider):
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        sections = [
            {'id': 'summary', 'title': 'Executive Summary', 'inputs': ['objective', 'impact']},
            {'id': 'narrative', 'title': 'Project Narrative', 'inputs': ['background', 'approach']},
            {'id': 'budget', 'title': 'Budget', 'inputs': ['items', 'total']},
        ]
        return {'schema_version': 'v1', 'source': grant_url or 'text', 'sections': sections}

    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        draft = f'Draft for {section_id}:\n' + '\n'.join(f'- {k}: {v}' for k, v in answers.items())
        if deterministic:
            draft = '[deterministic]\n' + draft
        return AIResult(text=draft, usage_tokens=0)

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        new_text = base_text + '\n\nRevisions applied: ' + change_request
        if deterministic:
            new_text = '[deterministic]\n' + new_text
        return AIResult(text=new_text, usage_tokens=0)

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ) -> AIResult:
        header = '[stub:formatted]' + (f' template={template_hint}' if template_hint else '')
        if deterministic:
            header += ' deterministic=1'
        return AIResult(text=f'{header}\n\n{full_text}')
