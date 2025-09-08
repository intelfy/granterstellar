"""Simple diff engine utility (Phase 3 scaffold).

Produces a line-oriented unified diff summary and a compact change ratio.
Later phases may swap this with a semantic diff (e.g., sentence alignment).
"""
from __future__ import annotations
import difflib
from dataclasses import dataclass


@dataclass
class DiffResult:
    summary: str
    change_ratio: float


def diff_texts(old: str, new: str) -> DiffResult:
    old_lines = (old or "").splitlines(keepends=True)
    new_lines = (new or "").splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new", n=3)
    summary = "".join(diff)
    sm = difflib.SequenceMatcher(a=old, b=new)
    ratio = 1.0 - sm.ratio()  # change proportion
    return DiffResult(summary=summary, change_ratio=ratio)
