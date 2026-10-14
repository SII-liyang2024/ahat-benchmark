#!/usr/bin/env python3
"""Create a clean public source copy, including CI, with no local artifacts."""
import argparse
from pathlib import Path
import shutil
import tempfile

from check_release import ROOT, check_source, public_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/open-source-preview")
    args = parser.parse_args()
    files = public_files()
    errors = check_source()
    if errors:
        raise SystemExit("Public-source check failed:\n" + "\n".join(errors))
    target = args.output_dir.resolve()
    if target == ROOT or target in ROOT.parents:
        raise SystemExit("Export destination must not be the source or one of its parents")
    if target.exists() and any(target.iterdir()):
        raise SystemExit("Export destination must be absent or empty")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ahat-public-export-", dir=target.parent) as temporary:
        staged = Path(temporary) / "ahat-benchmark"
        staged.mkdir()
        for path in files:
            destination = staged / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, destination)
        if target.exists():
            target.rmdir()  # Only the empty destination accepted above.
        staged.rename(target)
    print(f"Exported {len(files)} public files to {target}")


if __name__ == "__main__":
    main()
