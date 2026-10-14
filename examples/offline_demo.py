#!/usr/bin/env python3
"""Exercise real VAL and a mock four-dimension judge without network calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from ahat_benchmark.config import load_config, resolve_project_path
from ahat_benchmark.judge.evaluator import RubricEvaluator
from ahat_benchmark.pipeline.judge_stage import run_judge_stage
from ahat_benchmark.pipeline.summarize import summarize
from ahat_benchmark.pipeline.val_stage import run_val_stage


EXAMPLES = Path(__file__).resolve().parent


class MockJudge:
    base_url = "https://mock.example/v1"

    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="offline-demo", model="offline-demo-mock", usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "score": 1, "rationale": "Synthetic reply for the offline software example.",
                "critical_failure": False,
            })))],
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/offline-demo"))
    args = parser.parse_args()
    config = load_config()
    domain = resolve_project_path(config["domain"], config["_config_path"])
    executable = resolve_project_path(config["val_executable"], config["_config_path"])
    common = dict(dataset="demo", registry_path=EXAMPLES / "datasets.yaml",
                  inference_path=EXAMPLES / "inference.json")
    val_path = args.output_dir / "val_results.json"
    judge_path = args.output_dir / "judge_results.json"
    final_path = args.output_dir / "final_results.json"
    val = run_val_stage(**common, output_path=val_path, domain_path=domain,
                        val_executable=executable, timeout_seconds=10, workers=2,
                        resume=False)
    assert [case["status"] for case in val["cases"]] == ["valid", "invalid"], val["statistics"]
    client = MockJudge()
    evaluator = RubricEvaluator(client=client, model="offline-demo-mock", domain_path=domain)
    judged = run_judge_stage(**common, val_results_path=val_path, output_path=judge_path,
                            evaluator=evaluator, workers=2, resume=False)
    assert len(client.calls) == 4
    assert set(judged["cases"][0]["dimensions"]) == {"D1", "D2", "D3", "D4"}
    result = summarize(**common, val_results_path=val_path, judge_results_path=judge_path,
                       output_path=final_path, domain_path=domain)
    assert result["statistics"]["publishable"]
    assert result["statistics"]["final_score"] == 0.5
    print(f"Offline example passed: real VAL, four mock replies, synthetic score 0.5.\n{final_path}")


if __name__ == "__main__":
    main()
