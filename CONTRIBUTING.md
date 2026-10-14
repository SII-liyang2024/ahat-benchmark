# Contributing

Use Python 3.10 or newer on Linux x86-64:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
ahat-benchmark doctor
python examples/offline_demo.py
python scripts/check_release.py
python -m build
python scripts/check_release.py --artifacts dist/*
```

Tests and the offline demo use mock judge replies and do not need credentials.
CI repeats these checks and installs the wheel in a separate environment before
running the example. For an actual judge run, configure your own endpoint in
`.env`; the CLI keeps shell variables ahead of `.env` values.

Keep case IDs stable. A dataset change must update the corresponding manifest
hash/count and source revision. A protocol change must update its version and
documentation; changes to prompts, scoring, domain or VAL must be explicit.
Checkpoints are signed and deliberately reject changed inputs or code.
Use a new output directory after upgrading the evaluator.

For a bug report, include the package version, dataset revision, command, VAL
status or dimension status, and a minimal scene/plan if available. Remove
credentials before attaching any files. Please add a regression check when a
fix changes validation, score calculation or checkpoint recovery.

Proposals should explain the changed behavior and relevant verification.
Third-party notices and the data's CC BY-NC 4.0 license must remain intact.
