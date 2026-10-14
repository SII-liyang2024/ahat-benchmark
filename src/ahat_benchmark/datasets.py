from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from .io import read_json
from .config import PROJECT_DIR
from .schemas import EvalCase, InferenceCase, SchemaError, normalize_plan, require_string


def load_dataset_registry(path: Path | None = None) -> dict[str, Path]:
    config_path = path or PROJECT_DIR / "configs" / "datasets.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    entries = raw.get("datasets", {})
    return {
        name: (config_path.parent / value).resolve()
        for name, value in entries.items()
    }


def load_eval_set(dataset: str, registry_path: Path | None = None) -> list[EvalCase]:
    registry = load_dataset_registry(registry_path)
    if dataset not in registry:
        raise SchemaError(f"unknown dataset {dataset!r}; choose from {sorted(registry)}")
    data_path = registry[dataset]
    _verify_manifest(data_path)
    raw = read_json(data_path)
    if not isinstance(raw, list):
        raise SchemaError("eval set root must be a JSON array")
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SchemaError(f"eval case {index} must be an object")
        case_id = require_string(item.get("id"), f"eval case {index}.id")
        if case_id in seen:
            raise SchemaError(f"duplicate eval id: {case_id}")
        seen.add(case_id)
        instruction = require_string(item.get("instruction"), f"eval case {index}.instruction")
        scene_graph = item.get("scene_graph")
        if not isinstance(scene_graph, dict) or not scene_graph:
            raise SchemaError(f"eval case {index}.scene_graph must be a non-empty object")
        cases.append(EvalCase(case_id, instruction, scene_graph))
    return cases


def _verify_manifest(data_path: Path) -> None:
    manifest_path = data_path.parent / "manifest.json"
    if not manifest_path.exists():
        raise SchemaError(f"benchmark manifest is missing: {manifest_path}")
    manifest = read_json(manifest_path)
    expected_hash = manifest.get("data_sha256")
    actual_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if expected_hash != actual_hash:
        raise SchemaError(
            f"benchmark data hash mismatch for {data_path}: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    raw = read_json(data_path)
    if not isinstance(raw, list) or len(raw) != manifest.get("case_count"):
        raise SchemaError(
            f"benchmark case count mismatch for {data_path}: "
            f"expected {manifest.get('case_count')}, got "
            f"{len(raw) if isinstance(raw, list) else 'non-array'}"
        )


def _extract_results(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("results"), list):
        return raw["results"]
    raise SchemaError("inference root must be an array or an object containing results[]")


def load_inference(path: Path) -> tuple[dict[str, Any], dict[str, InferenceCase]]:
    raw = read_json(path)
    meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    cases: dict[str, InferenceCase] = {}
    for index, item in enumerate(_extract_results(raw)):
        if not isinstance(item, dict):
            raise SchemaError(f"inference result {index} must be an object")
        case_id = item.get("id") or item.get("case_id")
        case_id = require_string(case_id, f"inference result {index}.id")
        if case_id in cases:
            raise SchemaError(f"duplicate inference id: {case_id}")
        cases[case_id] = InferenceCase(
            id=case_id,
            plan=normalize_plan(item.get("plan")),
            raw_response=item.get("raw_response"),
            error=item.get("error"),
        )
    return meta if isinstance(meta, dict) else {}, cases


def align_cases(
    eval_cases: list[EvalCase],
    inference_cases: dict[str, InferenceCase],
    *,
    allow_missing: bool = False,
) -> list[tuple[EvalCase, InferenceCase | None]]:
    eval_ids = {case.id for case in eval_cases}
    unexpected = sorted(set(inference_cases) - eval_ids)
    if unexpected:
        raise SchemaError(f"inference contains {len(unexpected)} unknown ids; first: {unexpected[0]}")
    missing = [case.id for case in eval_cases if case.id not in inference_cases]
    if missing and not allow_missing:
        raise SchemaError(f"inference is missing {len(missing)} eval ids; first: {missing[0]}")
    return [(case, inference_cases.get(case.id)) for case in eval_cases]
