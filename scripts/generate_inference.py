#!/usr/bin/env python3
"""Run a small planning inference and save benchmark-compatible results."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from dotenv import load_dotenv  # noqa: E402
from openai import OpenAI  # noqa: E402

from ahat_benchmark.config import load_config, resolve_project_path  # noqa: E402
from ahat_benchmark.datasets import load_eval_set  # noqa: E402
from ahat_benchmark.io import write_json_atomic  # noqa: E402
from ahat_benchmark.schemas import normalize_plan  # noqa: E402


BASE_URL_ENV = "RUBRIC_EVAL_OPENAI_BASE_URL"
API_KEY_ENV = "RUBRIC_EVAL_OPENAI_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use the configured model to generate AHAT plans."
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dataset", default="ahat-easy")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="number of cases to infer; use 0 for the complete dataset (default: 1)",
    )
    parser.add_argument("--model", help="override judge.model from the config")
    parser.add_argument("--base-url", help=f"override {BASE_URL_ENV}")
    parser.add_argument("--api-key", help=f"override {API_KEY_ENV}")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def parse_plan(response: str) -> list[str]:
    text = response.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
        if match:
            text = match.group(1).strip()

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    parsed: Any = json.loads(text)
    if not isinstance(parsed, dict) or "plan" not in parsed:
        raise ValueError('response must be a JSON object containing a "plan" field')
    return normalize_plan(parsed["plan"])


def build_messages(
    instruction: str, scene_graph: dict[str, Any], domain: str
) -> list[dict[str, str]]:
    system_prompt = """You are a household robot task planner.
Generate a valid, executable PDDL action sequence that fulfills the instruction.
Use only actions from the supplied domain and exact entity names from the scene graph.
Respect every action precondition and keep the plan concise.
Treat agent_at literally: before picking up an object, navigate to the object
itself (not merely its surface or receptacle); before handing an object over,
navigate to the person. The navigate action can move directly between any two
location-typed entities and does not require intermediate rooms.
Return JSON only, with this exact shape:
{"plan": ["(action arg1 arg2)", "(action arg1 arg2 arg3)"]}
Do not include explanations or Markdown."""
    user_prompt = (
        f"Instruction:\n{instruction}\n\n"
        f"Scene graph:\n{json.dumps(scene_graph, ensure_ascii=False)}\n\n"
        f"PDDL domain:\n{domain}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-") or "model"


def main() -> int:
    args = parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be zero or greater")

    load_dotenv(PROJECT_DIR / ".env")
    config = load_config(args.config)
    model = args.model or os.getenv("RUBRIC_EVAL_MODEL") or os.getenv("API_MODEL") or config["judge"]["model"]
    base_url = args.base_url or os.getenv(BASE_URL_ENV) or os.getenv("API_BASE_URL") or os.getenv("OPENAI_BASE_URL") or config["judge"].get("base_url")
    api_key = args.api_key or os.getenv(API_KEY_ENV) or os.getenv("INF_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            f"missing API key: set {API_KEY_ENV} in .env or pass --api-key"
        )
    if not base_url:
        raise SystemExit(f"missing endpoint: set {BASE_URL_ENV} or pass --base-url")

    output_path = args.output or (
        PROJECT_DIR
        / "outputs"
        / f"inference-{args.dataset}-{safe_model_name(model)}.json"
    )
    domain_path = resolve_project_path(config["domain"], config["_config_path"])
    domain = domain_path.read_text(encoding="utf-8")
    cases = load_eval_set(args.dataset)
    selected_cases = cases if args.limit == 0 else cases[: args.limit]
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=float(config["judge"]["request_timeout_seconds"]),
    )

    output: dict[str, Any] = {
        "meta": {
            "dataset": args.dataset,
            "model": model,
            "method": "openai-chat-planning",
        },
        "results": [],
    }
    for index, case in enumerate(selected_cases, start=1):
        print(f"[{index}/{len(selected_cases)}] inferring {case.id}...", flush=True)
        raw_response: str | None = None
        error: str | None = None
        plan: list[str] = []
        try:
            response = client.chat.completions.create(
                model=model,
                messages=build_messages(case.instruction, case.scene_graph, domain),
                stream=False,
            )
            raw_response = response.choices[0].message.content or ""
            plan = parse_plan(raw_response)
        except Exception as exc:
            # Transport exceptions may contain endpoint or authentication text.
            error = type(exc).__name__
            print(f"  failed: {error}", file=sys.stderr)

        output["results"].append(
            {
                "id": case.id,
                "plan": plan,
                "raw_response": raw_response,
                "error": error,
            }
        )
        # Persist after every case so a partial run survives interruption.
        write_json_atomic(output_path, output)

    print(f"Inference results: {output_path}")
    return 1 if any(item["error"] for item in output["results"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
