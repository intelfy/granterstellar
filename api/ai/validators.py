from __future__ import annotations
from typing import Any

"""Role contract validators for AI provider IO schemas.

Ensures provider outputs conform to strict backend-owned schemas.
"""

class SchemaError(ValueError):
    pass


def _require(obj: dict, key: str, typ, allow_empty: bool = False):
    if key not in obj:
        raise SchemaError(f"missing key: {key}")
    val = obj[key]
    if not isinstance(val, typ):
        raise SchemaError(f"{key} wrong type: expected {typ}, got {type(val)}")
    if not allow_empty and (val == [] or val == ""):
        raise SchemaError(f"{key} empty not allowed")
    return val


def validate_planner_output(data: dict[str, Any]) -> dict[str, Any]:
    _require(data, "schema_version", (str,))
    sections = _require(data, "sections", list)
    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise SchemaError(f"sections[{idx}] not object")
        _require(sec, "id", (str,))
        _require(sec, "title", (str,))
        qs = _require(sec, "questions", list, allow_empty=True)
        for q_i, q in enumerate(qs):
            if not isinstance(q, str) or not q.strip():
                raise SchemaError(f"sections[{idx}].questions[{q_i}] invalid")
    return data


def validate_writer_output(data: dict[str, Any]) -> dict[str, Any]:
    # Writer should return plain markdown draft text only (no JSON structure besides wrapper)
    draft = _require(data, "draft", (str,))
    if draft.strip().startswith("{"):
        raise SchemaError("writer draft appears to be JSON; expected markdown text")
    return data


def validate_reviser_output(data: dict[str, Any]) -> dict[str, Any]:
    _require(data, "revised", (str,))
    diff = _require(data, "diff", dict)
    # minimal diff structure expectations
    _require(diff, "added", list, allow_empty=True)
    _require(diff, "removed", list, allow_empty=True)
    return data


def validate_formatter_output(data: dict[str, Any]) -> dict[str, Any]:
    _require(data, "formatted_markdown", (str,))
    return data

ROLE_VALIDATORS = {
    "plan": validate_planner_output,
    "write": validate_writer_output,
    "revise": validate_reviser_output,
    "format": validate_formatter_output,
}


def validate_role_output(role: str, data: dict[str, Any]) -> dict[str, Any]:
    if role not in ROLE_VALIDATORS:
        raise SchemaError(f"unknown role {role}")
    return ROLE_VALIDATORS[role](data)
