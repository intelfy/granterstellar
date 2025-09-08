"""Context budget manager (Phase 2 scaffolding)."""
from __future__ import annotations

def allocate(*, max_prompt_tokens: int, snippet_texts: list[str], memory_items: list[dict], file_refs: list[dict] | None) -> dict:
    # Very rough token estimator: words
    def estimate(s: str) -> int:
        return max(1, len(s.split()))

    budget = max_prompt_tokens
    out_snips: list[str] = []
    for s in snippet_texts:
        cost = estimate(s)
        if cost + 50 > budget:  # reserve some margin
            break
        out_snips.append(s)
        budget -= cost
    # memory simplistic inclusion (no trimming yet)
    return {
        "snippets": out_snips,
        "memory": memory_items,
        "file_refs": file_refs or [],
        "remaining_budget": budget,
    }
