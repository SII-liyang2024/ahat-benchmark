from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..io import write_json_atomic
from ..schemas import EvalCase


def save_stage(
    dataset: str, inference_path: Path, inference_meta: dict[str, Any], eval_cases: list[EvalCase],
    results: dict[str, dict[str, Any]], output_path: Path, provenance: dict[str, Any],
    domain_path: Path, extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered = [results[case.id] for case in eval_cases if case.id in results]
    counts: dict[str, int] = {}
    for item in ordered:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    output = {
        "meta": {
            **provenance, "dataset": dataset, "domain_file": str(domain_path.resolve()),
            "inference_file": str(inference_path.resolve()), "inference_meta": inference_meta,
            **(extra_meta or {}), "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "statistics": {"total_cases": len(eval_cases), "completed_cases": len(ordered), **counts},
        "cases": ordered,
    }
    write_json_atomic(output_path, output)
    return output
