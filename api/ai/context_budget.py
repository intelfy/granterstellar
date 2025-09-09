"""Context budget management (Phase 2 completion).

Deterministic trimming for retrieval snippets, memory items, and file refs.

Policy (initial):
1. Inputs provided already ordered by priority (retrieval: score desc, memory: caller order, files: caller order).
2. Reserve fixed output token allowance (caller supplies `reserved_output_tokens`).
3. Hard model max tokens optionally provided; if omitted only per-section caps enforced.
4. Approx token estimation: whitespace word count (same heuristic used elsewhere).
5. Deterministic: no randomness; stable slicing given identical inputs.

Future extensions: dynamic reservation percentages, semantic tag buckets, refined token estimator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


def _approx_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))


@dataclass
class BudgetResult:
    retrieval: list[dict[str, Any]]
    memory: list[dict[str, Any]]
    file_refs: list[dict[str, Any]]
    used_retrieval_tokens: int
    used_memory_tokens: int
    used_file_ref_tokens: int
    total_used: int
    model_max_tokens: int | None
    reserved_output_tokens: int


def apply_context_budget(
    *,
    retrieval: Sequence[dict[str, Any]] | None,
    memory: Sequence[dict[str, Any]] | None,
    file_refs: Sequence[dict[str, Any]] | None,
    model_max_tokens: int | None,
    reserved_output_tokens: int = 512,
    max_retrieval_tokens: int = 1200,
    max_memory_tokens: int = 300,
    max_file_ref_tokens: int = 300,
) -> BudgetResult:
    retrieval = list(retrieval or [])
    memory = list(memory or [])
    file_refs = list(file_refs or [])

    # Cap budgets by model allowance if provided
    if model_max_tokens is not None:
        ctx_cap = max(0, model_max_tokens - reserved_output_tokens)
    else:
        ctx_cap = None

    def trim(items: list[dict[str, Any]], token_cap: int) -> tuple[list[dict[str, Any]], int]:
        out: list[dict[str, Any]] = []
        used = 0
        for it in items:
            t = it.get("token_len") or _approx_tokens(it.get("text"))
            if used + t > token_cap:
                break
            used += t
            out.append(it)
        return out, used

    r_cap = min(max_retrieval_tokens, ctx_cap) if ctx_cap is not None else max_retrieval_tokens
    trimmed_retrieval, used_r = trim(retrieval, r_cap)

    remaining = None if ctx_cap is None else max(0, ctx_cap - used_r)
    m_cap_base = max_memory_tokens
    if remaining is not None:
        m_cap = min(m_cap_base, remaining)
    else:
        m_cap = m_cap_base
    trimmed_memory, used_m = trim(memory, m_cap)

    remaining2 = None if ctx_cap is None else max(0, ctx_cap - used_r - used_m)
    f_cap_base = max_file_ref_tokens
    if remaining2 is not None:
        f_cap = min(f_cap_base, remaining2)
    else:
        f_cap = f_cap_base
    trimmed_files, used_f = trim(file_refs, f_cap)

    total_used = used_r + used_m + used_f
    return BudgetResult(
        retrieval=trimmed_retrieval,
        memory=trimmed_memory,
        file_refs=trimmed_files,
        used_retrieval_tokens=used_r,
        used_memory_tokens=used_m,
        used_file_ref_tokens=used_f,
        total_used=total_used,
        model_max_tokens=model_max_tokens,
        reserved_output_tokens=reserved_output_tokens,
    )


__all__ = ["apply_context_budget", "BudgetResult"]
