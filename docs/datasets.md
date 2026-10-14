# Datasets and custom inputs

The bundled release has 348 cases: easy 146, medium 94 and open 108.
The raw file is pinned to HF revision
[`44de8a66c58cfd4cea03923bed9dbb8bd69d8f85`](https://huggingface.co/datasets/SII-liyang2024/AHAT-dataset/tree/44de8a66c58cfd4cea03923bed9dbb8bd69d8f85).
Source SHA-256:
`05cb4e725b5a8a93feb8c8609c768dc7a93371fb00c076f09ddaa104bdf8fc94`.
Data license: [CC BY-NC 4.0](../licenses/CC-BY-NC-4.0).

`ahat_eval_set.jsonl` is retained verbatim, including reference plans.
Runtime `ahat-{easy,medium,open}/cases.json` files split by source `type`,
preserve source order, and project to `id`, `instruction` and `scene_graph`.
Each split manifest records count, file hash, source revision and license.
`ahat-benchmark doctor` checks these snapshots. `benchmarks/hf_sync.json`
records source provenance and all local data/manifest hashes.

## Reference-plan compatibility

The pinned dataset and audited evaluation domain are separate snapshots.
Nine reference plans use actions absent from the audited domain: eight use
`light_on`, one uses `clean_item_with_faucet`. They span easy 2, medium 2 and
open 5. [Affected records](validation/reference_plan_val_failures.json) retain
the original failure evidence.

The audited original reviewer also reports these nine as invalid; the remaining
339 reference plans validate. Reference plans are not supplied to the LLM
reviewer. A new upstream domain or repaired data revision requires an explicit
protocol update and fresh evaluation.

## Custom dataset registry

Prepare an array of cases:

```json
[{"id": "stable-id", "instruction": "Pick up the cup.", "scene_graph": {}}]
```

Replace the empty scene above with a complete scene graph; empty scenes are
rejected. Put `cases.json` and `manifest.json` in the same directory:

```json
{"case_count": 1, "data_sha256": "SHA256_OF_CASES_JSON_BYTES"}
```

Write a registry YAML with paths relative to that YAML file:

```yaml
datasets:
  my-dataset: data/my-dataset/cases.json
```

Then run:

```bash
ahat-benchmark --registry path/to/datasets.yaml val \
  --dataset my-dataset --inference path/to/inference.json \
  --output-dir outputs/my-dataset-run1
```

The same registry must be supplied to `judge`, `summarize` or `run`.
`examples/datasets.yaml` and `examples/data/demo/` provide a complete working
fixture. The public registry contains only the three HF splits; additional
local datasets can be registered separately without changing bundled data.
