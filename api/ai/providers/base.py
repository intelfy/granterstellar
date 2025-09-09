from dataclasses import dataclass
from typing import Any


@dataclass
class AIResult:
    text: str
    usage_tokens: int = 0
    model_id: str = 'local.stub'


class BaseProvider:
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> dict:  # pragma: no cover - interface
        raise NotImplementedError

    def write(
        self,
        *,
        section_id: str,
        answers: dict[str, str],
        file_refs: list[dict[str, Any]] | None = None,
        deterministic: bool = False,
    ):
        raise NotImplementedError

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: list[dict[str, Any]] | None = None,
        deterministic: bool = False,
    ):
        raise NotImplementedError

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: list[dict[str, Any]] | None = None,
        deterministic: bool = False,
    ):
        raise NotImplementedError
