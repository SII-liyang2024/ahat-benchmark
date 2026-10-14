# Preparing a release

The 2.1.0 preparation passed 36 offline tests, the 348-case audited comparison,
1,250 scoring combinations, and an isolated installed-wheel end-to-end check.
The [validation record](validation/release_check_summary.json) identifies the
tested environment and confirms that the source and installed code agree.

Run the offline checks and build from a source checkout:

```bash
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
ahat-benchmark doctor
python examples/offline_demo.py
python scripts/check_release.py
python -m build
python scripts/check_release.py --artifacts dist/*
```

`check_release.py` checks public files and distribution contents for accidental
credentials, internal deployment addresses, local absolute paths, archives,
outputs and crash dumps. It also verifies bundled assets and wheel platform
metadata. It prints file paths and issue categories, never matching values.

Produce a clean copy of the public repository, including CI:

```bash
python scripts/export_public.py --output-dir outputs/open-source-preview
```

This copies Git-visible files only (or the explicit public directories/files
when there is no `.git`). It preserves executable permissions and excludes
`.env`, `.local/`, outputs, build artifacts and Git metadata. The destination
must be absent or empty. Review this directory when creating an external repo;
Git and package exclusions do not apply to blindly uploading the workspace.

Before distributing a wheel, install it in a separate virtual environment and
run `ahat-benchmark doctor` from a directory outside the source checkout.
Then copy `examples/` from the source distribution and run its offline demo.
CI performs this installation check. The wheel is Linux x86-64 only because it
includes VAL native binaries; it does not claim a manylinux ABI.

Keep code, manifest and citation versions in agreement. Published evaluation
results should state the package version, HF revision, domain/runtime/prompt
hashes, judge model/endpoint and scoring settings. Credentials must stay local.
Code is MIT; data remains CC BY-NC 4.0; see the third-party notices.
