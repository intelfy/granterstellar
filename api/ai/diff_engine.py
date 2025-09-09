"""Paragraph-oriented diff engine.

Phase 1 semantic-ish implementation without external deps (rapidfuzz optional later).
Provides structured change blocks suitable for UI highlighting:

Output schema (dictionary):
{
  "change_ratio": float,  # proportion changed (0-1)
  "blocks": [
     {"type": "equal"|"add"|"remove"|"change", "before": str, "after": str,
      "similarity": float}
  ]
}

Change detection algorithm:
1. Split texts into paragraphs (double newline or newline boundaries).
2. Use SequenceMatcher on paragraph lists.
3. For replace op, compute simple char similarity; if high (>=0.6) treat as 'change'; else emit separate remove/add.

Determinism: stable ordering by original sequence indices; no randomness.
"""
from __future__ import annotations
import difflib
from typing import Any


def _split_paragraphs(text: str) -> list[str]:
    if not text:
        return []
    # Normalize Windows newlines and split on blank lines preserving core paragraphs.
    norm = text.replace("\r\n", "\n")
    # Simple heuristic: split on double newlines; fallback to lines if no doubles.
    if "\n\n" in norm:
        parts = [p.strip("\n") for p in norm.split("\n\n")]
    else:
        parts = [p for p in norm.split("\n")]
    return [p for p in parts if p is not None]


def _similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(a=a, b=b).ratio()


def diff_texts(old: str, new: str) -> dict[str, Any]:
    old_paras = _split_paragraphs(old or "")
    new_paras = _split_paragraphs(new or "")
    sm = difflib.SequenceMatcher(a=old_paras, b=new_paras)
    blocks: list[dict[str, Any]] = []
    changed_chars = 0
    total_chars = max(len(old or "") + len(new or ""), 1)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                blocks.append({
                    "type": "equal",
                    "before": old_paras[k],
                    "after": new_paras[j1 + (k - i1)],
                    "similarity": 1.0,
                })
            continue
        if tag == "delete":
            for k in range(i1, i2):
                seg = old_paras[k]
                changed_chars += len(seg)
                blocks.append({
                    "type": "remove",
                    "before": seg,
                    "after": "",
                    "similarity": 0.0,
                })
            continue
        if tag == "insert":
            for k in range(j1, j2):
                seg = new_paras[k]
                changed_chars += len(seg)
                blocks.append({
                    "type": "add",
                    "before": "",
                    "after": seg,
                    "similarity": 0.0,
                })
            continue
        if tag == "replace":
            old_segment = "\n".join(old_paras[i1:i2])
            new_segment = "\n".join(new_paras[j1:j2])
            sim = _similarity(old_segment, new_segment)
            if sim >= 0.6:
                changed_chars += max(len(old_segment), len(new_segment))
                blocks.append({
                    "type": "change",
                    "before": old_segment,
                    "after": new_segment,
                    "similarity": sim,
                })
            else:
                # Low similarity -> treat as removal + addition for clearer UI.
                changed_chars += len(old_segment) + len(new_segment)
                if old_segment:
                    blocks.append({
                        "type": "remove",
                        "before": old_segment,
                        "after": "",
                        "similarity": 0.0,
                    })
                if new_segment:
                    blocks.append({
                        "type": "add",
                        "before": "",
                        "after": new_segment,
                        "similarity": 0.0,
                    })
            continue
    change_ratio = min(changed_chars / total_chars, 1.0)
    return {"change_ratio": change_ratio, "blocks": blocks}
