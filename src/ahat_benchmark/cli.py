from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from .config import PROJECT_DIR, load_config, resolve_project_path
from . import __version__
from .datasets import load_dataset_registry, load_eval_set
from .judge.evaluator import RubricEvaluator
from .judge.prompts import PROMPTS
from .io import read_json
from .provenance import digest, file_digest
from .pipeline.judge_stage import run_judge_stage
from .pipeline.summarize import summarize
from .pipeline.val_stage import run_val_stage


BASE_URL_ENV = "RUBRIC_EVAL_OPENAI_BASE_URL"
API_KEY_ENV = "RUBRIC_EVAL_OPENAI_API_KEY"


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ahat-benchmark",
        description="Versioned AHAT benchmark with two-stage evaluation",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--registry", type=Path, help="custom dataset registry YAML")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="verify benchmark data, domain, and VAL runtime")

    def common(subparser):
        subparser.add_argument("--dataset", required=True)
        subparser.add_argument("--inference", type=Path, required=True)
        subparser.add_argument("--output-dir", type=Path, required=True)
        subparser.add_argument("--workers", type=positive_int, help="parallel cases (config default: 8)")

    val_parser = subparsers.add_parser("val", help="run deterministic VAL validation")
    common(val_parser)
    val_parser.add_argument("--allow-missing", action="store_true")
    val_parser.add_argument("--no-resume", action="store_true")

    judge_parser = subparsers.add_parser("judge", help="judge VAL-valid plans with an LLM")
    common(judge_parser)
    judge_parser.add_argument("--model")
    judge_parser.add_argument("--base-url")
    judge_parser.add_argument("--api-key")
    judge_parser.add_argument("--dimension-workers", type=positive_int, help="parallel rubric dimensions per case")
    judge_parser.add_argument("--no-resume", action="store_true")

    summary_parser = subparsers.add_parser("summarize", help="build final results")
    common(summary_parser)

    run_parser = subparsers.add_parser("run", help="run VAL, judge, and summary")
    common(run_parser)
    run_parser.add_argument("--model")
    run_parser.add_argument("--base-url")
    run_parser.add_argument("--api-key")
    run_parser.add_argument("--dimension-workers", type=positive_int, help="parallel rubric dimensions per case")
    run_parser.add_argument("--allow-missing", action="store_true")
    run_parser.add_argument("--no-resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Keep secrets out of versioned YAML while allowing local, zero-setup runs.
    # Existing shell/CI environment variables take precedence over .env values.
    load_dotenv(Path.cwd() / ".env")
    if Path.cwd() != PROJECT_DIR:
        load_dotenv(PROJECT_DIR / ".env")
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "doctor":
        return run_doctor(config, registry_path=args.registry)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    val_path = args.output_dir / "val_results.json"
    judge_path = args.output_dir / "judge_results.json"
    final_path = args.output_dir / "final_results.json"
    domain_path = resolve_project_path(config["domain"], config["_config_path"])
    val_executable = resolve_project_path(config["val_executable"], config["_config_path"])
    workers = args.workers or int(config["workers"])
    resume = not getattr(args, "no_resume", False)

    if args.command in {"val", "run"}:
        run_val_stage(
            dataset=args.dataset,
            inference_path=args.inference,
            output_path=val_path,
            domain_path=domain_path,
            val_executable=val_executable,
            timeout_seconds=float(config["val_timeout_seconds"]),
            workers=workers,
            registry_path=args.registry,
            resume=resume,
            allow_missing=getattr(args, "allow_missing", False),
        )
        print(f"VAL results: {val_path}")
    if args.command in {"judge", "run"}:
        judge_config = config["judge"]
        base_url = args.base_url or os.getenv(judge_config.get("base_url_env", BASE_URL_ENV)) or os.getenv("API_BASE_URL") or os.getenv("OPENAI_BASE_URL") or judge_config.get("base_url")
        api_key = args.api_key or os.getenv(judge_config.get("api_key_env", API_KEY_ENV)) or os.getenv("INF_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = args.model or os.getenv("RUBRIC_EVAL_MODEL") or os.getenv("API_MODEL") or judge_config["model"]
        if not api_key:
            print(f"missing API key: set {API_KEY_ENV} or pass --api-key", file=sys.stderr)
            return 2
        if not base_url:
            print(f"missing judge endpoint: set {BASE_URL_ENV} or pass --base-url", file=sys.stderr)
            return 2
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(judge_config["request_timeout_seconds"]),
        )
        evaluator = RubricEvaluator(
            client=client,
            model=model,
            domain_path=domain_path,
            max_attempts=int(judge_config["max_attempts"]),
            dimension_workers=args.dimension_workers or int(judge_config["dimension_workers"]),
            weights=config["scoring"]["weights"],
            critical_failure_cap=config["scoring"]["critical_failure_cap"],
            good_threshold=config["scoring"]["good_threshold"],
            normal_threshold=config["scoring"]["normal_threshold"],
        )
        run_judge_stage(
            dataset=args.dataset,
            inference_path=args.inference,
            val_results_path=val_path,
            output_path=judge_path,
            evaluator=evaluator,
            workers=workers,
            registry_path=args.registry,
            resume=resume,
        )
        print(f"Judge results: {judge_path}")
    if args.command in {"summarize", "run"}:
        result = summarize(
            dataset=args.dataset,
            inference_path=args.inference,
            val_results_path=val_path,
            judge_results_path=judge_path,
            output_path=final_path,
            domain_path=domain_path,
            registry_path=args.registry,
        )
        print(f"Final results: {final_path}")
        print(f"Publishable: {result['statistics']['publishable']}")
        print(f"Final score: {result['statistics']['final_score']}")
    return 0


def run_doctor(config: dict, registry_path: Path | None = None) -> int:
    failures = 0
    manifest = read_json(PROJECT_DIR / "benchmark_manifest.json")
    for name in load_dataset_registry(registry_path):
        try:
            cases = load_eval_set(name, registry_path=registry_path)
            print(f"[OK] {name}: {len(cases)} cases, manifest and SHA-256 valid")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {name}: {exc}", file=sys.stderr)
    for label, path in (
        ("PDDL domain", resolve_project_path(config["domain"], config["_config_path"])),
        ("VAL executable", resolve_project_path(config["val_executable"], config["_config_path"])),
    ):
        if path.is_file() and (label != "VAL executable" or os.access(path, os.X_OK)):
            print(f"[OK] {label}: {path}")
        else:
            failures += 1
            print(f"[FAIL] {label}: {path}", file=sys.stderr)
    for label, path, expected in (
        ("PDDL domain hash", resolve_project_path(config["domain"], config["_config_path"]), manifest["domain"]["sha256"]),
        ("VAL runtime hash", resolve_project_path(config["val_executable"], config["_config_path"]), manifest["validator"]["sha256"]),
        ("VAL library hash", resolve_project_path(config["val_executable"], config["_config_path"]).parent / "libVAL.so", manifest["validator"]["library_sha256"]),
    ):
        if file_digest(path) == expected:
            print(f"[OK] {label}")
        else:
            failures += 1
            print(f"[FAIL] {label}: snapshot has changed", file=sys.stderr)
    if {key: digest(value.encode()) for key, value in PROMPTS.items()} == manifest["judge"]["prompt_hashes"]:
        print("[OK] four verbatim paper rubric prompt hashes")
    else:
        failures += 1
        print("[FAIL] paper rubric prompt hashes", file=sys.stderr)
    print("Doctor passed" if failures == 0 else f"Doctor found {failures} problem(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
