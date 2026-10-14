from __future__ import annotations

import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..datasets import align_cases, load_eval_set, load_inference
from ..io import read_json, write_json_atomic
from ..judge.aggregator import aggregate
from ..provenance import index_cases, verify_stage_context
from .judge_stage import ZERO_STATUSES


def summarize(
    *, dataset: str, inference_path: Path, val_results_path: Path,
    judge_results_path: Path, output_path: Path, domain_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    eval_cases = load_eval_set(dataset, registry_path=registry_path)
    _, inference = load_inference(inference_path)
    val_data, judge_data = read_json(val_results_path), read_json(judge_results_path)
    if domain_path is None:
        stored_domain = val_data.get("meta", {}).get("domain_file")
        if not isinstance(stored_domain, str):
            raise ValueError("Unversioned VAL results; rerun evaluation in a new output directory")
        domain_path = Path(stored_domain)
    val_provenance = verify_stage_context(
        val_data, stage="val", dataset=dataset, eval_cases=eval_cases,
        inference_path=inference_path, domain_path=domain_path,
    )
    judge_provenance = verify_stage_context(
        judge_data, stage="judge", dataset=dataset, eval_cases=eval_cases,
        inference_path=inference_path, domain_path=domain_path,
        parent_signature=val_provenance["signature"],
    )
    align_cases(eval_cases, inference, allow_missing=val_provenance["protocol"].get("allow_missing", False))
    val_by_id, judge_by_id = index_cases(val_data, eval_cases), index_cases(judge_data, eval_cases)
    scoring = judge_provenance["protocol"]
    case_results, valid_judged, dimension_values = [], [], {}
    system_errors = 0
    for case in eval_cases:
        val = val_by_id.get(case.id, {"status": "missing"})
        judge = judge_by_id.get(case.id, {"status": "missing"})
        score = None
        if val.get("status") in ZERO_STATUSES:
            score = 0.0
        elif val.get("status") == "valid" and judge.get("status") == "success":
            checked = aggregate(
                judge.get("dimensions", {}), weights=scoring["weights"],
                critical_failure_cap=scoring["critical_failure_cap"],
                good_threshold=scoring["good_threshold"], normal_threshold=scoring["normal_threshold"],
            )
            if checked["status"] == "success":
                score = checked["score"]
                valid_judged.append(score)
                for key, value in checked["dimension_scores"].items():
                    dimension_values.setdefault(key, []).append(value)
        if score is None:
            system_errors += 1
        case_results.append({
            "id": case.id, "instruction": case.instruction,
            "plan": inference[case.id].plan if case.id in inference else [],
            "val": val, "judge": judge, "final_score": score,
        })
    publishable = system_errors == 0 and bool(eval_cases)
    scores = [item["final_score"] for item in case_results if item["final_score"] is not None]
    summary_stats = {
        "total_cases": len(eval_cases),
        "plans_present": sum(bool(item["plan"]) for item in case_results),
        "val_valid": sum(item["val"].get("status") == "valid" for item in case_results),
        "val_invalid": sum(item["val"].get("status") == "invalid" for item in case_results),
        "judge_success": len(valid_judged), "system_errors": system_errors, "publishable": publishable,
        "final_score": sum(scores) / len(eval_cases) if publishable else None,
        "rubric_mean_on_valid": statistics.fmean(valid_judged) if valid_judged else None,
        "dimension_means": {key: statistics.fmean(values) for key, values in dimension_values.items()},
    }
    if len(valid_judged) > 1:
        summary_stats["rubric_std_dev_on_valid"] = statistics.stdev(valid_judged)
    output = {
        "meta": {
            "stage": "final", "schema_version": "2.0", "dataset": dataset,
            "inference_file": str(inference_path.resolve()),
            "val_signature": val_provenance["signature"], "judge_signature": judge_provenance["signature"],
            "protocol": judge_provenance["protocol"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "statistics": summary_stats, "cases": case_results,
    }
    write_json_atomic(output_path, output)
    return output
