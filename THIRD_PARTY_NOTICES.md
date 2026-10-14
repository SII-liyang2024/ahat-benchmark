# Third-party components and data

The root [MIT license](LICENSE) applies to AHAT Benchmark's own code.
The following components retain their original terms. Bundling data does not
relicense it under MIT.

| Component | Location | License / attribution |
| --- | --- | --- |
| AHAT evaluation code, domain and prompts | `src/ahat_benchmark/`, `vendor/pddl/` | MIT; copyright 2026 Sii-liuzhihong; [original text](licenses/AHAT-MIT), [upstream](https://github.com/Sii-liuzhihong/AHAT) |
| Scene-graph and PDDL utilities | `src/ahat_benchmark/vendor/` | MIT; copyright 2024 embodied-agent-interface; [original text](licenses/EMBODIED-AGENT-INTERFACE-MIT) |
| VAL executable and shared library | `vendor/val/` | BSD-3-Clause; copyright 2019 University of Strathclyde, King's College London and Schlumberger Ltd; [original text](licenses/VAL-BSD-3-Clause), [upstream](https://github.com/KCL-Planning/VAL) |
| Paper rubric text | `src/ahat_benchmark/judge/paper_rubric/` | Copied from AHAT; also attributed to Liu, Li, Huang, Lu and Cai, *Any House Any Task*, [Appendix A.3](https://arxiv.org/html/2602.12244v2#A3); paper CC BY 4.0, [terms](licenses/CC-BY-4.0) |
| AHAT evaluation data and derived split files | `benchmarks/` | **CC BY-NC 4.0**; noncommercial use with attribution; [terms](licenses/CC-BY-NC-4.0), [pinned dataset card](licenses/AHAT-DATASET-CARD.md) |

The 348-case dataset is from
[`SII-liyang2024/AHAT-dataset`](https://huggingface.co/datasets/SII-liyang2024/AHAT-dataset/tree/44de8a66c58cfd4cea03923bed9dbb8bd69d8f85),
revision `44de8a66c58cfd4cea03923bed9dbb8bd69d8f85`.
The source JSONL is unchanged. Runtime split files project each record to
`id`, `instruction` and `scene_graph`; reference plans are not evaluator inputs.
Source hashes and transformations are recorded in `benchmarks/hf_sync.json`.
Please retain the dataset attribution and cite the paper when using it.

VAL binary hashes identify the exact audited runtime. The local upstream source
checkout reports revision `3c7a1f330bdab0ba28a4762bb45c3f06c27fb6d4`;
the original binary build flags are not recorded. See [VENDORED.md](VENDORED.md)
for file provenance. Rebuilt VAL binaries are a different evaluation protocol.

Python dependencies are installed separately and keep their own licenses.
