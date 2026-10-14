from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACKAGE_DIR.parents[1]
# Editable checkouts use the human-readable top-level directories. Wheels carry
# the same, hash-checked files inside the package and work from any directory.
PROJECT_DIR = (
    SOURCE_DIR
    if (SOURCE_DIR / "pyproject.toml").is_file()
    and (SOURCE_DIR / "src" / "ahat_benchmark").resolve() == PACKAGE_DIR
    else PACKAGE_DIR / "resources"
)


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or PROJECT_DIR / "configs" / "default.yaml").resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    config["_config_path"] = config_path
    return config


def resolve_project_path(value: str, config_path: Path | None = None) -> Path:
    path = Path(value)
    base = config_path.parent if config_path is not None else PROJECT_DIR
    return path if path.is_absolute() else (base / path).resolve()
