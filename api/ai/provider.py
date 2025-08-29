from dataclasses import dataclass
from typing import Dict, Optional, List, Any


@dataclass
class AIResult:
    text: str
    usage_tokens: int = 0
    model_id: str = "local.stub"


class BaseProvider:
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        raise NotImplementedError

    def write(self, *, section_id: str, answers: Dict[str, str], file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        raise NotImplementedError

    def revise(self, *, base_text: str, change_request: str, file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        raise NotImplementedError

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        """Final formatting pass across the complete proposal text.
        Implementations should prioritize structure suitable for PDF export.
        """
        raise NotImplementedError


class LocalStubProvider(BaseProvider):
    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        sections = [
            {"id": "summary", "title": "Executive Summary", "inputs": ["objective", "impact"]},
            {"id": "narrative", "title": "Project Narrative", "inputs": ["background", "approach"]},
            {"id": "budget", "title": "Budget", "inputs": ["items", "total"]},
        ]
        return {"schema_version": "v1", "source": grant_url or "text", "sections": sections}

    def write(self, *, section_id: str, answers: Dict[str, str], file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        draft = f"Draft for {section_id}:\n" + "\n".join(f"- {k}: {v}" for k, v in answers.items())
        return AIResult(text=draft, usage_tokens=0)

    def revise(self, *, base_text: str, change_request: str, file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        new_text = base_text + "\n\nRevisions applied: " + change_request
        return AIResult(text=new_text, usage_tokens=0)

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        header = "[stub:formatted]" + (f" template={template_hint}" if template_hint else "")
        return AIResult(text=f"{header}\n\n{full_text}")


def _summarize_file_refs(file_refs: Optional[List[Dict[str, Any]]]) -> str:
    """Return a compact, deterministic summary block for provided file refs.

    Format:
    [context:sources]
    - <name-or-id>: <ocr-snippet>
    """
    if not file_refs:
        return ""
    lines: List[str] = []
    for ref in file_refs[:5]:
        try:
            label = (
                str(ref.get("name") or "").strip() or f"file#{ref.get('id', '?')}"
            )
            ocr = str(ref.get("ocr_text") or "").strip().replace("\n", " ")
            if len(ocr) > 200:
                ocr = ocr[:200]
            if label or ocr:
                lines.append(f"- {label}: {ocr}".rstrip())
        except Exception:
            continue
    if not lines:
        return ""
    return "\n\n[context:sources]\n" + "\n".join(lines)


class Gpt5Provider(BaseProvider):
    """Stub for GPT-5-backed operations. In production, call the OpenAI API here."""

    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        # Slightly more structured plan stub
        sections = [
            {"id": "summary", "title": "Executive Summary", "inputs": ["objective", "impact", "outcomes"]},
            {"id": "narrative", "title": "Project Narrative", "inputs": ["background", "approach", "risks"]},
            {"id": "budget", "title": "Budget", "inputs": ["items", "totals", "justification"]},
        ]
        return {"schema_version": "v1", "source": grant_url or "text", "sections": sections, "model": "gpt-5"}

    def write(
        self,
        *,
        section_id: str,
        answers: Dict[str, str],
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        draft = (
            f"[gpt-5] Draft for {section_id}:\n"
            + "\n".join(f"- {k}: {v}" for k, v in answers.items())
        )
        ctx = _summarize_file_refs(file_refs)
        return AIResult(text=draft + ctx, usage_tokens=0, model_id="gpt-5")

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        # Not primary role in our setup; fall back to appending changes
        text = base_text + "\n\n[gpt-5] Changes: " + change_request
        ctx = _summarize_file_refs(file_refs)
        return AIResult(text=text + ctx, usage_tokens=0, model_id="gpt-5")

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        # Not the formatter in our flow; return identity
        return AIResult(text=full_text, usage_tokens=0, model_id="gpt-5")


class GeminiProvider(BaseProvider):
    """Stub for Gemini-backed operations. In production, call the Gemini API here."""

    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        # Not primary role in our setup; mirror input
        return {"schema_version": "v1", "source": grant_url or "text", "sections": [], "model": "gemini"}

    def write(self, *, section_id: str, answers: Dict[str, str], file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        # Not primary role; identity pass-through formatting
        content = "\n".join(f"- {k}: {v}" for k, v in answers.items())
        return AIResult(text=f"[gemini:formatted] {section_id}\n{content}", usage_tokens=0, model_id="gemini")

    def revise(
        self,
        *,
        base_text: str,
        change_request: str,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        # Treat revise as formatting/polish plus cite any context
        formatted = base_text.strip() + "\n\n[gemini:polish] " + change_request.strip()
        ctx = _summarize_file_refs(file_refs)
        return AIResult(text=formatted + ctx, usage_tokens=0, model_id="gemini")

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        # Final structuring for export; simulate by annotating
        hint = f" template={template_hint}" if template_hint else ""
        return AIResult(text=f"[gemini:final_format{hint}]\n\n{full_text}", usage_tokens=0, model_id="gemini")


class CompositeProvider(BaseProvider):
    """Route capabilities: GPT-5 for plan/write; Gemini for revise/formatting."""

    def __init__(self, gpt: BaseProvider | None = None, gemini: BaseProvider | None = None):
        self.gpt = gpt or Gpt5Provider()
        self.gemini = gemini or GeminiProvider()

    def plan(self, *, grant_url: str | None, text_spec: str | None) -> Dict:
        return self.gpt.plan(grant_url=grant_url, text_spec=text_spec)

    def write(self, *, section_id: str, answers: Dict[str, str], file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        # GPT-5 produces the draft; no formatting until all sections are complete
        return self.gpt.write(section_id=section_id, answers=answers, file_refs=file_refs)

    def revise(self, *, base_text: str, change_request: str, file_refs: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        return self.gemini.revise(base_text=base_text, change_request=change_request, file_refs=file_refs)

    def format_final(
        self,
        *,
        full_text: str,
        template_hint: str | None = None,
        file_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResult:
        return self.gemini.format_final(
            full_text=full_text,
            template_hint=template_hint,
            file_refs=file_refs,
        )


def get_provider(name: Optional[str] = None) -> BaseProvider:
    """Select provider.

    Defaults to CompositeProvider (GPT-5 plan/write, Gemini revise). Supported names:
    - 'composite': CompositeProvider
    - 'stub': LocalStubProvider
    - 'gpt5': Gpt5Provider
    - 'gemini': GeminiProvider
    """
    key = (name or "composite").lower()
    if key == "stub":
        return LocalStubProvider()
    if key == "gpt5":
        return Gpt5Provider()
    if key == "gemini":
        return GeminiProvider()
    # default
    return CompositeProvider()
