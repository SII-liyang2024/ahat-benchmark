from __future__ import annotations

import json
import math
import re
from typing import Any


DEFAULT_WEIGHTS = {"D1": 0.4, "D2": 0.2, "D3": 0.2, "D4": 0.2}
VALID_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)


def snap_score(value: Any) -> float:
    """Compatibility name: validate exact paper scores without rounding."""
    if type(value) not in (int, float) or value not in VALID_SCORES:
        raise ValueError("Score must be one of 0/.25/.5/.75/1")
    return float(value)


def validate_review(result: Any, dimension: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("Review must be a JSON object")
    snap_score(result.get("score"))
    if not isinstance(result.get("rationale"), str) or not result["rationale"].strip():
        raise ValueError("Missing rationale")
    if dimension == "D1" and type(result.get("critical_failure")) is not bool:
        raise ValueError("D1 critical_failure must be boolean")
    return result


def parse_review(raw: str, dimension: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return validate_review(json.loads(text), dimension)


def validate_scoring(weights: dict[str, float], critical_failure_cap: float) -> None:
    if set(weights) != set(DEFAULT_WEIGHTS):
        raise ValueError("Weights must include exactly D1, D2, D3 and D4")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in weights.values()) or not math.isclose(sum(weights.values()), 1):
        raise ValueError("Weights must be finite, nonnegative and sum to 1")
    if type(critical_failure_cap) not in (int, float) or not 0 <= critical_failure_cap <= 1:
        raise ValueError("critical_failure_cap must be between 0 and 1")


def aggregate(
    dimensions: dict[str, dict[str, Any]],
    *,
    weights: dict[str, float] | None = None,
    critical_failure_cap: float = 0.2,
    good_threshold: float = 0.75,
    normal_threshold: float = 0.40,
) -> dict[str, Any]:
    weights = DEFAULT_WEIGHTS if weights is None else weights
    validate_scoring(weights, critical_failure_cap)
    missing = [key for key in weights if dimensions.get(key, {}).get("status") != "success"]
    error = f"unsuccessful dimensions: {', '.join(missing)}" if missing else None
    if not error:
        try:
            if set(dimensions) != set(weights):
                raise ValueError("All four successful dimensions required")
            for key in weights:
                validate_review(dimensions[key], key)
        except ValueError as exc:
            error = str(exc)
    if error:
        return {
            "status": "incomplete",
            "score": None,
            "result": None,
            "dimension_scores": {},
            "critical_failure": None,
            "error": error,
        }
    scores = {key: snap_score(dimensions[key]["score"]) for key in weights}
    score = sum(weights[key] * scores[key] for key in weights)
    critical = dimensions["D1"]["critical_failure"]
    if critical:
        score = min(score, critical_failure_cap)
    label = "Good" if score >= good_threshold else "Normal" if score >= normal_threshold else "Bad"
    return {
        "status": "success",
        "score": round(score, 8),
        "result": label,
        "dimension_scores": scores,
        "critical_failure": critical,
        "error": None,
    }
