from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..datasets import align_cases, load_eval_set, load_inference
from ..io import read_json
from ..provenance import index_cases, make_provenance, require_compatible
from ..val.validator import validate_plan, validator_protocol
from .common import save_stage


def run_val_stage(
    *, dataset: str, inference_path: Path, output_path: Path, domain_path: Path,
    val_executable: Path, timeout_seconds: float, workers: int,
    resume: bool = True, allow_missing: bool = False,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    eval_cases = load_eval_set(dataset, registry_path=registry_path)
    inference_meta, inference_cases = load_inference(inference_path)
    aligned = align_cases(eval_cases, inference_cases, allow_missing=allow_missing)
    provenance = make_provenance(
        stage="val", dataset=dataset, eval_cases=eval_cases, inference_path=inference_path,
        domain_path=domain_path, protocol=validator_protocol(val_executable, timeout_seconds, allow_missing),
    )
    completed = {}
    if resume and output_path.exists():
        previous = read_json(output_path)
        require_compatible(previous, provenance)
        completed = {
            key: value for key, value in index_cases(previous, eval_cases).items()
            if value.get("status") in {"valid", "invalid", "missing_plan", "malformed_plan"}
        }
    results = dict(completed)

    def save():
        return save_stage(dataset, inference_path, inference_meta, eval_cases, results, output_path, provenance, domain_path)

    def evaluate(pair):
        eval_case, inference_case = pair
        plan = inference_case.plan if inference_case else []
        result = validate_plan(
            scene_graph=eval_case.scene_graph, plan=plan, domain_path=domain_path,
            val_executable=val_executable, timeout_seconds=timeout_seconds,
        )
        if inference_case is None:
            result["fail_reason"] = "inference result is missing"
        return eval_case.id, {"id": eval_case.id, "plan": plan, **result}

    save()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(evaluate, pair) for pair in aligned if pair[0].id not in completed]
        for future in as_completed(futures):
            case_id, result = future.result()
            results[case_id] = result
            save()
    return save()
