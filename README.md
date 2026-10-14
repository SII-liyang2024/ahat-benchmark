# AHAT Benchmark

Standalone evaluation of household robot plans with **VAL validation** and the
**four-dimension AHAT LLM rubric**. It includes the evaluation data, PDDL domain,
original paper prompts and a pinned Linux VAL runtime.

[Project page](https://tgpo2026.github.io/TGPO/) ·
[Paper](https://arxiv.org/html/2602.12244v2) ·
[Dataset](https://huggingface.co/datasets/SII-liyang2024/AHAT-dataset) ·
[Evaluation protocol](docs/evaluation.md) ·
[Validation evidence](docs/validation/parity.md)

## Install

Use **Python 3.10+ on Linux x86-64**, with **glibc 2.34+** and a C++ runtime
providing `GLIBCXX_3.4.29` (for example, Ubuntu 22.04+ with `libstdc++6`).
From this repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ahat-benchmark doctor
```

For a regular installation, use `python -m pip install .` or install a built
wheel. Registered data, configuration, prompts, domain and VAL are included;
evaluation also works outside the repository directory.

## Offline example

Run a complete two-case example without an API or credentials:

```bash
python examples/offline_demo.py
```

The example calls the real VAL runtime, then supplies **mock judge replies**.
One plan is valid and one is blocked by the full scene. It checks all four
rubric dimensions, the zero for the invalid plan, and the full-case denominator.
Its synthetic score is `0.5`; this is a software example, not a model result.
Outputs are written to `outputs/offline-demo/`.

## Evaluate model plans

Copy `.env.example` to `.env` in your working directory and fill in your
OpenAI-compatible chat-completions endpoint and key:

```dotenv
RUBRIC_EVAL_OPENAI_BASE_URL=https://your-endpoint.example/v1
RUBRIC_EVAL_OPENAI_API_KEY=your-api-key
RUBRIC_EVAL_MODEL=ds-v4.1-flash-w8a8
```

The judge model must be available at your endpoint. Sampling and reasoning
parameters use the API defaults. Shell variables override `.env`.
`API_BASE_URL`, `INF_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_KEY` and `API_MODEL`
are also accepted. No internal endpoint or credential is supplied by this repo.

Evaluate an inference file whose IDs cover the chosen split:

```bash
ahat-benchmark run \
  --dataset ahat-easy \
  --inference path/to/inference.json \
  --output-dir outputs/easy-run1 \
  --workers 16 --dimension-workers 4
```

This configuration permits up to **64 simultaneous judge requests** in one run
(16 cases × 4 dimensions). The default is 8 cases × 4 dimensions = 32.

Stages can also be run separately in the same output directory:

```bash
ahat-benchmark val --dataset ahat-easy --inference path/to/inference.json --output-dir outputs/easy-run1
ahat-benchmark judge --dataset ahat-easy --inference path/to/inference.json --output-dir outputs/easy-run1
ahat-benchmark summarize --dataset ahat-easy --inference path/to/inference.json --output-dir outputs/easy-run1
```

`val` and `summarize` do not make API calls. See `ahat-benchmark --help` and
`ahat-benchmark run --help` for options. Custom `--config` and `--registry`
arguments go **before** the subcommand; paths in those YAML files are resolved
relative to each YAML file.

## Input format

Inference is a JSON array or an object containing `results`:

```json
{
  "meta": {"model": "your-planner", "method": "your-method"},
  "results": [
    {"id": "dataset-case-id", "plan": ["(navigate agent_0 room_1 cup_1)"]}
  ]
}
```

Use the exact case IDs and entity names from the selected dataset. The example
above illustrates the format; it is not a complete split submission.
Plans can be lists of action strings or newline-separated strings. Duplicate,
unknown or missing IDs are rejected; `val` and `run` support `--allow-missing`
when intentionally scoring absent plans as zero. The
[JSON Schema](schemas/inference.schema.json) documents both input forms.

An optional planning example can generate your inference file:

```bash
python scripts/generate_inference.py --dataset ahat-easy --limit 0 --model YOUR_PLANNER_MODEL
```

`--limit 0` covers the entire split. The default one-case run is a connectivity
example and does not cover the full evaluation set.

## Data and metric

| Dataset | Cases |
| --- | ---: |
| `ahat-easy` | 146 |
| `ahat-medium` | 94 |
| `ahat-open` | 108 |
| Total | **348** |

Data are pinned to HF revision
[`44de8a66c58cfd4cea03923bed9dbb8bd69d8f85`](https://huggingface.co/datasets/SII-liyang2024/AHAT-dataset/tree/44de8a66c58cfd4cea03923bed9dbb8bd69d8f85).
The original `benchmarks/ahat_eval_set.jsonl` retains reference plans; runtime
split files expose only IDs, instructions and scenes. Hashes and source
provenance are bundled. [Dataset notes](docs/datasets.md) explain the nine
reference plans incompatible with this audited domain and custom registries.

| Dimension | Weight |
| --- | ---: |
| D1 Goal Achievement | 0.40 |
| D2 Intent Understanding | 0.20 |
| D3 Completeness | 0.20 |
| D4 Execution Quality | 0.20 |

Scores must be `0`, `0.25`, `0.5`, `0.75` or `1`. D1 critical failure caps the
weighted total at `0.2`. VAL uses a deterministic full scene; D1 receives the
exact final state derived from the validated initial PDDL and domain effects.

The split score is `sum(case scores) / all split cases`. Invalid, malformed and
empty plans score zero. Infrastructure failures and failed judge calls remain
unscored and make the report non-publishable.

## Results and recovery

Each run writes `val_results.json`, `judge_results.json` and
`final_results.json`. The judge stores per-dimension raw replies, returned
model, usage and attempt history. Repeating the same command resumes successful
dimensions and retries failed ones.

Checkpoints sign the data, inference, code, domain, native runtime, prompts,
judge model, endpoint and scoring settings. After an input or evaluator update,
use a new output directory or explicitly recompute with `--no-resume`.

## Repository layout

```text
benchmarks/       pinned 348-case data and manifests
configs/          public defaults and dataset registry
docs/             protocol, data and validation evidence
examples/         offline example and small input fixtures
licenses/         original third-party license texts
schemas/          inference JSON Schema
scripts/          inference and release utilities
src/ahat_benchmark/  evaluation package
tests/            offline regression suite
vendor/           audited PDDL domain and Linux VAL snapshot
```

Local credentials, outputs, archives, caches and crash dumps are excluded from
Git and distribution packages. See [CONTRIBUTING.md](CONTRIBUTING.md) for tests
and [release preparation](docs/releasing.md) for clean exports and builds.

## License and citation

Own code: **MIT**. Evaluation data: **CC BY-NC 4.0**. VAL: **BSD-3-Clause**.
Paper rubric: attributed to the AHAT paper, **CC BY 4.0**. See
[all third-party notices](THIRD_PARTY_NOTICES.md) for exact scope and terms.

```bibtex
@article{liu2026ahat,
  title={Any House Any Task: Scalable Long-Horizon Planning for Abstract Human Tasks},
  author={Liu, Zhihong and Li, Yang and Huang, Rengming and Lu, Cewu and Cai, Panpan},
  journal={arXiv preprint arXiv:2602.12244},
  year={2026}
}
```
