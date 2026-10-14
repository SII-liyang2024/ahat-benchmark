from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class EvalCase:
    id: str
    instruction: str
    scene_graph: dict[str, Any]


@dataclass(frozen=True)
class InferenceCase:
    id: str
    plan: list[str]
    raw_response: str | None = None
    error: str | None = None


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field} must be a non-empty string")
    return value


def normalize_plan(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [item.strip() for item in value if item.strip()]
    raise SchemaError("plan must be a list of strings or a newline-delimited string")
