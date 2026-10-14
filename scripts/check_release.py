#!/usr/bin/env python3
"""Check public source and distributions without printing sensitive matches."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIRS = (".github", "benchmarks", "configs", "docs", "examples", "licenses",
               "schemas", "scripts", "src", "tests", "vendor")
PUBLIC_FILES = (".env.example", ".gitignore", "README.md", "LICENSE", "CITATION.cff",
                "CHANGELOG.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md", "VENDORED.md",
                "pyproject.toml", "setup.py", "MANIFEST.in", "benchmark_manifest.json")
PRIVATE_PARTS = {".local", "outputs", ".venv", "__pycache__", ".pytest_cache", ".git"}
PRIVATE_TEXT = re.compile(r"/(?:inspire|home)/|https?://[^\s/]*openapi-[^\s/]*\.sii\.edu\.cn")
SECRETS = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,})\b|"
    r"(?im:^[ \t]*(?:INF_API_KEY|OPENAI_API_KEY|RUBRIC_EVAL_OPENAI_API_KEY|api_key)"
    r"[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9/+_-]{16,})"
)
PROMPT_NAMES = {"D1": "Goal_Achievement", "D2": "Intent_Understanding",
                "D3": "Completeness", "D4": "Execution_Quality"}


def excluded(path: Path) -> bool:
    return bool(PRIVATE_PARTS.intersection(path.parts)) or any(
        part.endswith(".egg-info") for part in path.parts
    ) or path.suffix in {".pyc", ".pyo", ".log"}


def public_files(root: Path = ROOT) -> list[Path]:
    if (root / ".git").exists():
        output = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        return sorted({Path(name.decode()) for name in output.split(b"\0") if name})
    files = {Path(name) for name in PUBLIC_FILES if (root / name).is_file()}
    for name in PUBLIC_DIRS:
        files.update(p.relative_to(root) for p in (root / name).rglob("*") if p.is_file())
    return sorted(path for path in files if not excluded(path))


def inspect_file(name: str, data: bytes) -> list[str]:
    path = PurePosixPath(name)
    issues = []
    if PRIVATE_PARTS.intersection(path.parts) or any(p.endswith(".egg-info") for p in path.parts):
        issues.append("local/generated file")
    if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
        issues.append("credential file")
    if path.name == "core" or path.name.startswith("core.") or path.suffix in {".key", ".pem", ".log", ".pyc", ".pyo"}:
        issues.append("private or generated artifact")
    if "\0" not in data[:8000].decode("utf-8", errors="replace"):
        text = data.decode("utf-8", errors="replace")
        if PRIVATE_TEXT.search(text):
            issues.append("local path or internal deployment address")
        if SECRETS.search(text):
            issues.append("possible credential")
    return issues


def check_assets(files: dict[str, bytes], wheel: bool = False) -> list[str]:
    errors = []
    prefix = "ahat_benchmark/resources/" if wheel else ""
    def get(name):
        value = files.get(prefix + name)
        if value is None:
            errors.append(f"missing {prefix + name}")
        return value
    raw = get("benchmark_manifest.json")
    if raw is None:
        return errors
    manifest = json.loads(raw)
    expected = [(manifest["domain"]["path"], manifest["domain"]["sha256"]),
                (manifest["validator"]["path"], manifest["validator"]["sha256"]),
                (manifest["validator"]["library_path"], manifest["validator"]["library_sha256"])]
    for name, sha in expected:
        data = get(name)
        if data is not None and hashlib.sha256(data).hexdigest() != sha:
            errors.append(f"snapshot hash mismatch: {name}")
    prompt_prefix = "ahat_benchmark/" if wheel else "src/ahat_benchmark/"
    for key, name in PROMPT_NAMES.items():
        path = prompt_prefix + f"judge/paper_rubric/{name}.txt"
        if path not in files or hashlib.sha256(files[path]).hexdigest() != manifest["judge"]["prompt_hashes"][key]:
            errors.append(f"missing/changed prompt: {key}")
    count = 0
    for dataset in manifest["benchmarks"]:
        data = get(f"benchmarks/{dataset}/cases.json")
        split_raw = get(f"benchmarks/{dataset}/manifest.json")
        if data is not None and split_raw is not None:
            split = json.loads(split_raw)
            count += len(json.loads(data))
            if hashlib.sha256(data).hexdigest() != split["data_sha256"] or len(json.loads(data)) != split["case_count"]:
                errors.append(f"data manifest mismatch: {dataset}")
    if count != 348:
        errors.append("public dataset count must be 348")
    provenance = get("benchmarks/hf_sync.json")
    source = get("benchmarks/ahat_eval_set.jsonl")
    if provenance is not None and source is not None:
        if hashlib.sha256(source).hexdigest() != json.loads(provenance)["source"]["sha256"]:
            errors.append("raw HF source hash mismatch")
    for name in ("configs/default.yaml", "configs/datasets.yaml", "schemas/inference.schema.json",
                 "THIRD_PARTY_NOTICES.md", "licenses/AHAT-MIT", "licenses/VAL-BSD-3-Clause",
                 "licenses/EMBODIED-AGENT-INTERFACE-MIT", "licenses/CC-BY-NC-4.0", "licenses/CC-BY-4.0"):
        get(name)
    return errors


def check_source(root: Path = ROOT) -> list[str]:
    files = {}
    errors = []
    for path in public_files(root):
        file = root / path
        if file.is_symlink():
            errors.append(f"{path}: symlink in public source")
            continue
        if not file.is_file():
            errors.append(f"{path}: missing public file")
            continue
        data = file.read_bytes()
        files[path.as_posix()] = data
        errors.extend(f"{path}: {issue}" for issue in inspect_file(path.as_posix(), data))
    errors.extend(check_assets(files))
    version = json.loads(files["benchmark_manifest.json"])["version"]
    for path, pattern in [("pyproject.toml", r'version\s*=\s*"([^"]+)"'),
                          ("src/ahat_benchmark/__init__.py", r'__version__\s*=\s*"([^"]+)"'),
                          ("CITATION.cff", r'(?m)^version:\s*(\S+)')]:
        match = re.search(pattern, files[path].decode())
        if not match or match.group(1) != version:
            errors.append(f"{path}: version mismatch")
    return errors


def check_artifact(path: Path) -> list[str]:
    files = {}
    errors = []
    wheel = path.suffix == ".whl"
    if wheel:
        with zipfile.ZipFile(path) as archive:
            files = {info.filename: archive.read(info) for info in archive.infolist() if not info.is_dir()}
        metadata = next((data.decode() for name, data in files.items() if name.endswith(".dist-info/WHEEL")), "")
        if "Root-Is-Purelib: false" not in metadata or "Tag: py3-none-linux_x86_64" not in metadata:
            errors.append("incorrect native-runtime wheel platform tag")
    else:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    errors.append(f"{member.name}: archive link")
                elif member.isfile():
                    name = member.name.split("/", 1)[1]
                    files[name] = archive.extractfile(member).read()
    for name, data in files.items():
        issues = inspect_file(name, data)
        # The expected sdist metadata is allowed, but its content is still
        # checked for credentials and private addresses/paths.
        if not wheel and name.startswith("src/ahat_benchmark.egg-info/"):
            issues = [issue for issue in issues if issue != "local/generated file"]
        errors.extend(f"{name}: {issue}" for issue in issues)
    # Platform wheels may put this pure-Python wrapper in .data/purelib;
    # pip installs that scheme into site-packages just like a root package.
    installed_files = {}
    for name, data in files.items():
        parts = name.split("/", 2)
        if wheel and len(parts) == 3 and parts[0].endswith(".data") and parts[1] in {"purelib", "platlib"}:
            name = parts[2]
        installed_files[name] = data
    errors.extend(check_assets(installed_files, wheel=wheel))
    return [f"{path.name}: {error}" for error in errors]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", nargs="*", type=Path, default=[])
    args = parser.parse_args()
    errors = check_source()
    for artifact in args.artifacts:
        errors.extend(check_artifact(artifact))
    if errors:
        for error in errors:
            print("[FAIL]", error)
        return 1
    print(f"Release checks passed: {len(public_files())} public files, {len(args.artifacts)} distributions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
