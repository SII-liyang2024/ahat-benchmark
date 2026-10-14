from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from ..pddl import final_state, full_problem
from ..provenance import digest
from ..val.validator import normalize_action
from .aggregator import DEFAULT_WEIGHTS, aggregate, parse_review, validate_review, validate_scoring
from .prompts import PROMPTS, PROMPT_VERSION
from .scene_summary import summarize_scene


def compute_final_state(
    scene_graph: dict[str, Any], plan: list[str], domain_path: Path, *,
    problem_text: str | None = None,
) -> list[list[str]]:
    problem = full_problem(scene_graph, domain_path) if problem_text is None else problem_text
    return final_state(problem, [normalize_action(action) for action in plan], domain_path)


def format_state(predicates: list[list[str]]) -> str:
    return "\n".join("(" + " ".join(pred) + ")" for pred in predicates)


def build_inputs(instruction: str, scene_graph: dict[str, Any], plan: list[str], state: list[list[str]]) -> dict[str, str]:
    plan_text = "\n".join(plan)
    return {
        "D1": f"PDDL_Final_State:\n{format_state(state)}\n\nInstruction: {instruction}",
        "D2": f"House_content:\n{summarize_scene(scene_graph)}\n\nPlan:\n{plan_text}\n\nInstruction: {instruction}",
        "D3": f"Plan:\n{plan_text}\n\nInstruction: {instruction}",
        "D4": f"Plan:\n{plan_text}\n\nInstruction: {instruction}",
    }


class RubricEvaluator:
    def __init__(
        self, *, client: OpenAI, model: str, domain_path: Path,
        max_attempts: int = 3, dimension_workers: int = 4,
        weights: dict[str, float] | None = None, critical_failure_cap: float = 0.2,
        good_threshold: float = 0.75, normal_threshold: float = 0.40,
    ):
        self.client = client
        self.model = model
        self.domain_path = domain_path
        self.max_attempts = max_attempts
        self.dimension_workers = dimension_workers
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
        self.critical_failure_cap = critical_failure_cap
        self.good_threshold = good_threshold
        self.normal_threshold = normal_threshold
        validate_scoring(self.weights, self.critical_failure_cap)

    def protocol(self) -> dict[str, Any]:
        return {
            "version": PROMPT_VERSION, "paper": "https://arxiv.org/html/2602.12244v2#A3",
            "judge": self.model, "base_url": str(getattr(self.client, "base_url", "")),
            "judge_kwargs": {}, "weights": self.weights, "critical_failure_cap": self.critical_failure_cap,
            "good_threshold": self.good_threshold, "normal_threshold": self.normal_threshold,
            "prompt_hashes": {key: digest(prompt.encode()) for key, prompt in PROMPTS.items()},
            "state_method": "Full-scene initial facts plus simultaneous STRIPS delete/add effects",
            "initial_fact_policy": "Drop and record facts incompatible with predicate types or PDDL identifiers",
        }

    def evaluate(
        self, instruction: str, scene_graph: dict[str, Any], plan: list[str], *,
        problem_text: str | None = None, previous_dimensions: dict[str, Any] | None = None,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        try:
            normalized = [normalize_action(action) for action in plan]
            state = compute_final_state(scene_graph, normalized, self.domain_path, problem_text=problem_text)
            inputs = build_inputs(instruction, scene_graph, normalized, state)
        except Exception as exc:
            return {"status": "forward_error", "score": None, "result": None, "dimensions": {},
                    "pddl_end_state": None, "error": str(exc),
                    "duration_seconds": round(time.monotonic() - started, 6)}
        previous = previous_dimensions or {}
        dimensions = {}
        for key, content in inputs.items():
            record = previous.get(key, {})
            if record.get("status") == "success" and record.get("input_sha256") == digest(content.encode()):
                try:
                    validate_review(record, key)
                except ValueError:
                    continue
                dimensions[key] = record

        def result():
            scoring = aggregate(
                dimensions, weights=self.weights, critical_failure_cap=self.critical_failure_cap,
                good_threshold=self.good_threshold, normal_threshold=self.normal_threshold,
            )
            return {
                **scoring, "dimensions": dict(dimensions), "pddl_end_state": state,
                "inputs": inputs, "prompt_version": PROMPT_VERSION,
                "duration_seconds": round(time.monotonic() - started, 6),
            }

        with ThreadPoolExecutor(max_workers=max(1, self.dimension_workers)) as executor:
            futures = {
                executor.submit(self._evaluate_dimension, key, content, previous.get(key, {})): key
                for key, content in inputs.items() if key not in dimensions
            }
            for future in as_completed(futures):
                dimensions[futures[future]] = future.result()
                if on_update:
                    on_update(result())
        return result()

    def _evaluate_dimension(self, key: str, content: str, previous: dict[str, Any]) -> dict[str, Any]:
        history = list(previous.get("attempt_history", []))
        last_raw, last_error, status = "", "", "parse_error"
        for attempt in range(1, self.max_attempts + 1):
            record: dict[str, Any] = {"raw_response": None}
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": PROMPTS[key]}, {"role": "user", "content": content}],
                )
                last_raw = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                record.update(
                    raw_response=last_raw, response_id=getattr(response, "id", None),
                    returned_model=getattr(response, "model", None),
                    usage=usage.model_dump() if usage is not None else None,
                )
            except Exception as exc:
                last_error, status = type(exc).__name__, "llm_error"
                record["error_type"] = last_error
            else:
                try:
                    parsed = parse_review(last_raw, key)
                except (ValueError, TypeError) as exc:
                    last_error, status = type(exc).__name__, "parse_error"
                    record["error_type"] = last_error
                else:
                    history.append(record)
                    return {
                        **parsed, "status": "success", "attempts": len(history), "attempt_history": history,
                        "raw_response": last_raw, "response_id": record["response_id"],
                        "returned_model": record["returned_model"], "usage": record["usage"],
                        "input_sha256": digest(content.encode()), "error": None,
                    }
            history.append(record)
            if attempt < self.max_attempts:
                time.sleep(min(2 ** (attempt - 1), 4))
        return {
            "status": status, "score": None, "attempts": len(history), "attempt_history": history,
            "raw_response": last_raw, "input_sha256": digest(content.encode()),
            "error": last_error or "unable to parse response",
        }
