from dataclasses import dataclass
from typing import Dict, Optional, List, Any

@dataclass
class AIResult:
    text: str
    usage_tokens: int = 0
    model_id: str = "local.stub"

class BaseProvider:
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:  # pragma: no cover - interface
        raise NotImplementedError
    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ):
        raise NotImplementedError
    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ):
        raise NotImplementedError
    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
        deterministic: bool = False,
    ):
        raise NotImplementedError
