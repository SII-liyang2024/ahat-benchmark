from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..pddl import full_problem, sexpr
from ..provenance import digest, file_digest
from ..vendor.scene_graph import PDDLDomainParser


VALIDATOR_VERSION = "full-scene-val-audited-v1"


def validator_protocol(val_executable: Path, timeout_seconds: float, allow_missing: bool = False) -> dict[str, Any]:
    return {
        "version": VALIDATOR_VERSION, "val_executable": str(val_executable.resolve()),
        "validator_sha256": file_digest(val_executable),
        "validator_library_sha256": file_digest(val_executable.parent / "libVAL.so"),
        "timeout_seconds": timeout_seconds, "allow_missing": allow_missing,
    }


def normalize_action(action: str) -> str:
    value = action.strip()
    if not value:
        raise ValueError("empty action")
    if not (value.startswith("(") and value.endswith(")")):
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*)\s*\(([^()]*)\)", value)
        if not match:
            raise ValueError(f"cannot parse action: {action!r}")
        arguments = match.group(2).replace(",", " ").split()
        value = f"({' '.join([match.group(1), *arguments])})"
    parsed = sexpr(value)
    if not parsed or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"cannot parse action: {action!r}")
    return value


def build_problem(scene_graph: dict[str, Any], plan: list[str], domain_path: Path) -> str:
    """The initial world is independent of the proposed plan."""
    return full_problem(scene_graph, domain_path)


def validate_plan(
    *,
    scene_graph: dict[str, Any],
    plan: list[str],
    domain_path: Path,
    val_executable: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    if not plan:
        return {
            "status": "missing_plan",
            "validate_result": False,
            "fail_reason": "plan is empty",
            "plan_repair_advice": None,
            "duration_seconds": 0.0,
        }
    try:
        normalized = [normalize_action(action) for action in plan]
    except Exception as exc:
        return {
            "status": "malformed_plan",
            "validate_result": False,
            "fail_reason": str(exc),
            "plan_repair_advice": None,
            "duration_seconds": round(time.monotonic() - started, 6),
        }
    try:
        domain_text = domain_path.read_text(encoding="utf-8")
        action_specs = PDDLDomainParser(domain_text).actions
        dropped: list[list[str]] = []
        problem_text = full_problem(scene_graph, domain_path, dropped)
    except Exception as exc:
        return {
            "status": "val_error",
            "validate_result": False,
            "fail_reason": f"failed to build PDDL problem: {exc}",
            "plan_repair_advice": None,
            "duration_seconds": round(time.monotonic() - started, 6),
        }

    prepared = {
        "plan": normalized,
        "problem_pddl": problem_text,
        "problem_sha256": digest(problem_text.encode()),
        "excluded_ill_typed_initial_facts": dropped,
    }
    # Native VAL can segfault on wrong-arity actions. AHAT's saved Luna
    # evaluator checks these domain constraints before calling the process.
    for text in normalized:
        action = sexpr(text)
        failure = None
        if action[0] not in action_specs:
            failure = "Unknown domain action"
        elif len(action) - 1 != len(action_specs[action[0]]["parameters"]):
            failure = "Wrong action argument count"
        if failure:
            return {
                "status": "invalid", "validate_result": False, "fail_reason": failure,
                "invalid_action": text, "plan_repair_advice": None, **prepared,
                "duration_seconds": round(time.monotonic() - started, 6),
            }
    with tempfile.TemporaryDirectory(prefix="ahat-val-") as temp_dir:
        temp = Path(temp_dir)
        domain_file = temp / "domain.pddl"
        problem_file = temp / "problem.pddl"
        plan_file = temp / "plan.txt"
        domain_file.write_text(domain_text, encoding="utf-8")
        problem_file.write_text(problem_text, encoding="utf-8")
        plan_file.write_text("\n".join(normalized), encoding="utf-8")
        env = os.environ.copy()
        lib_dir = str(val_executable.parent)
        env["LD_LIBRARY_PATH"] = (
            f"{lib_dir}:{env['LD_LIBRARY_PATH']}" if env.get("LD_LIBRARY_PATH") else lib_dir
        )
        try:
            completed = subprocess.run(
                [str(val_executable), "-v", str(domain_file), str(problem_file), str(plan_file)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "val_timeout",
                "validate_result": False,
                "fail_reason": f"VAL timed out after {timeout_seconds}s",
                "plan_repair_advice": None,
                "stdout": _as_text(exc.stdout),
                "stderr": _as_text(exc.stderr),
                **prepared,
                "duration_seconds": round(time.monotonic() - started, 6),
            }
        except Exception as exc:
            return {
                "status": "val_error",
                "validate_result": False,
                "fail_reason": str(exc),
                "plan_repair_advice": None,
                **prepared,
                "duration_seconds": round(time.monotonic() - started, 6),
            }

    output = (completed.stdout or "") + (completed.stderr or "")
    valid = completed.returncode == 0 and "Successful plans:" in output
    invalid = any(marker in output for marker in (
        "Plan failed", "Plan invalid", "Failed plans:", "Type-checking plan failed"
    ))
    status = "valid" if valid else ("invalid" if invalid else "val_error")
    repair_marker = "Plan Repair Advice:"
    repair = output.split(repair_marker, 1)[1].strip() if repair_marker in output else None
    return {
        "status": status,
        "validate_result": valid,
        "fail_reason": None if valid else (
            output.strip() if invalid else f"VAL did not produce a plan verdict: {output[-1500:]}"
        ),
        "plan_repair_advice": repair,
        "return_code": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        **prepared,
        "duration_seconds": round(time.monotonic() - started, 6),
    }


def _as_text(value: str | bytes | None) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
