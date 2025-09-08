"""Prompt template rendering utility.

Responsibilities:
- Fetch active template for a role (highest version, active=True)
- Validate required variables are supplied and no undeclared extras (strict mode)
- Perform safe "{{var}}" substitution (no logic, no attribute access)
- Return both raw rendered and redacted snapshot (using AIJobContext.redact)
- Fallback: minimal hardcoded template if DB has none (keeps system functioning)

Security / Safety:
- Hard caps on final length
- Variable values coerced to str and truncated
- Escapes braces in values to avoid accidental double expansion

Design Notes:
We deliberately avoid Jinja to reduce attack surface and remove need for a template sandbox.
The formatting agent and other roles receive deterministic, backend-owned prompt text.
"""
from __future__ import annotations
from dataclasses import dataclass
from .models import AIPromptTemplate, AIJobContext
import hashlib

MAX_PROMPT_LEN = 30000
MAX_VALUE_LEN = 4000

class PromptTemplateError(ValueError):
    pass

@dataclass(frozen=True)
class RenderedPrompt:
    template: AIPromptTemplate | None
    rendered: str
    redacted: str
    variables_used: dict[str, str]


def _get_active_template(role: str) -> AIPromptTemplate | None:
    qs = (
        AIPromptTemplate.objects.filter(role=role, active=True)
        .order_by('-version')
    )
    return qs.first()


def _fallback_template(role: str) -> tuple[str, list[str]]:
    # Minimal safe fallback; kept intentionally simple.
    base = (
        f"ROLE: {role}\n"
        "Instructions: Follow role guidelines.\n"
        "Input JSON: {{input_json}}\n"
    )
    return base, ["input_json"]


def render_role_prompt(*, role: str, variables: dict[str, object]) -> RenderedPrompt:
    tpl = _get_active_template(role)
    if tpl is None:
        raw_tpl, declared = _fallback_template(role)
        declared_set = set(declared)
    else:
        raw_tpl = tpl.template
        declared_set = set(tpl.variables or [])

    # If template has blueprint metadata and role is formatter, append structured blueprint guidance
    if tpl and role == 'formatter' and (tpl.blueprint_schema or tpl.blueprint_instructions):
        blueprint_block = "\n---\nSTRUCTURE BLUEPRINT INSTRUCTIONS:\n"
        if tpl.blueprint_instructions:
            blueprint_block += tpl.blueprint_instructions.strip() + "\n"
        if tpl.blueprint_schema:
            import json
            try:
                blueprint_block += "SCHEMA JSON:\n" + json.dumps(tpl.blueprint_schema, sort_keys=True) + "\n"
            except Exception:  # pragma: no cover - defensive
                pass
        raw_tpl = raw_tpl.rstrip() + blueprint_block

    # Normalize and coerce variable values
    norm_vars: dict[str, str] = {}
    for k, v in variables.items():
        if v is None:
            continue
        s = str(v)
        if len(s) > MAX_VALUE_LEN:
            s = s[:MAX_VALUE_LEN] + "…"
        # Escape any '{{' or '}}' to prevent confusion
        s = s.replace('{{', '{ {').replace('}}', '} }')
        norm_vars[k] = s

    # Strict variable enforcement
    provided = set(norm_vars.keys())
    missing = declared_set - provided
    extras = provided - declared_set
    if tpl is not None:  # Only enforce strictness when template exists in DB
        if missing:
            raise PromptTemplateError(f"missing variables: {', '.join(sorted(missing))}")
        if extras:
            raise PromptTemplateError(f"unexpected variables: {', '.join(sorted(extras))}")

    # Render (one-pass replace of {{var}} tokens)
    def replace_token(token: str) -> str:
        name = token[2:-2].strip()
        return norm_vars.get(name, '')

    out_parts: list[str] = []
    i = 0
    while i < len(raw_tpl):
        if raw_tpl.startswith('{{', i):
            j = raw_tpl.find('}}', i + 2)
            if j == -1:
                # no closing, treat as literal
                out_parts.append(raw_tpl[i:])
                break
            token = raw_tpl[i:j+2]
            out_parts.append(replace_token(token))
            i = j + 2
        else:
            out_parts.append(raw_tpl[i])
            i += 1
    rendered = ''.join(out_parts)
    if len(rendered) > MAX_PROMPT_LEN:
        rendered = rendered[:MAX_PROMPT_LEN] + "…"

    # Use extended redaction to capture mapping
    redacted, _map = AIJobContext.redact_with_mapping(rendered)

    # Attach template checksum for drift detection (checksum already stored, but recompute on combined template)
    if tpl is not None:
        # Compute for callers that may extend RenderedPrompt later (side-effect only)
        _ = hashlib.sha256(tpl.template.encode('utf-8')).hexdigest()

    return RenderedPrompt(
        template=tpl,
        rendered=rendered,
        redacted=redacted,
        variables_used=norm_vars,
    )

__all__ = [
    'RenderedPrompt',
    'render_role_prompt',
    'PromptTemplateError',
]

def detect_template_drift(ctx: AIJobContext) -> bool:
    """Return True if stored template checksum differs from current template text.

    If context has no linked template or no stored checksum, returns False (no drift detectable).
    """
    tpl = ctx.prompt_template
    if not tpl or not ctx.template_sha256:
        return False
    # IMPORTANT: ctx.prompt_template may be a stale in-memory instance (tests mutate a different
    # Python object referencing the same DB row). Always refetch current template text from DB.
    try:
        current_text = (
            AIPromptTemplate.objects.filter(id=getattr(tpl, 'id', None))
            .values_list('template', flat=True)
            .first()
        )
    except Exception:  # pragma: no cover - defensive DB error handling
        return False
    if current_text is None:
        return False
    current = AIPromptTemplate.compute_checksum(current_text)
    return current != ctx.template_sha256

__all__.append('detect_template_drift')
