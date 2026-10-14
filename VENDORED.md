# Vendored components

Evaluation imports only this package; it needs no AHAT checkout or external
scene-graph adapter. Component licenses are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

| File | Original source | Changes |
| --- | --- | --- |
| `src/ahat_benchmark/vendor/scene_graph.py` | embodied-agent-interface AHAT adapter: `fix_plan_pddl/update_sg/dynamic_sg.py` | Byte-exact copy |
| `src/ahat_benchmark/vendor/problem_generator.py` | Adapter: `fix_plan_pddl/goal_solver/problem_generator_plan.py` | Package-local imports; unused solver dependency removed; retained utility, unused by the full-scene evaluator |
| `src/ahat_benchmark/pddl.py` | AHAT: `baseline/llm/run_eval_rubric.py` | Port of full-scene generation and simultaneous STRIPS simulation |
| `src/ahat_benchmark/val/validator.py` | AHAT audited reviewer and `baseline/llm/review_luna_benchmark.py` | Standalone wrapper; pre-VAL action/arity checks |
| `src/ahat_benchmark/judge/scene_summary.py` | Audited adapter's `sum_sg_content` | Port of the D2 inventory/location format |
| `src/ahat_benchmark/judge/paper_rubric/*.txt` | AHAT: `baseline/llm/prompts/paper_rubric/` | Four byte-exact original prompts, including placeholder examples |
| `vendor/pddl/domain_0102_test.pddl` | AHAT: `baseline/sayplan/pddl/domain_0102_test.pddl` | Audited domain snapshot |
| `vendor/val/Validate`, `vendor/val/libVAL.so` | Runtime selected by AHAT's audited reviewer | Byte-exact Linux x86-64 binary snapshot |

The audited reviewer source SHA-256 is
`831327119172acf20f231d3e396ef4e97fe452f04a082fefbeef10dff5eec7c7`.
Domain, native runtime and prompt fingerprints are in
`benchmark_manifest.json` and checked by `ahat-benchmark doctor`.
Native binaries require Linux x86-64, glibc 2.34+ and a C++ runtime exporting
`GLIBCXX_3.4.29` (GCC 11 runtime or newer).
Wheel distributions are tagged `py3-none-linux_x86_64`.

Build with `python -m build`. `setup.py` copies the top-level public runtime
assets into `ahat_benchmark/resources` during wheel construction.
Source/editable installs use the top-level copies. This keeps a single source
copy of the data and excludes local outputs, credentials and audit tools.

The HF dataset is pinned independently of the audited domain. In this snapshot,
nine reference plans use actions absent from that domain. See
[dataset notes](docs/datasets.md); a different domain is a different protocol.
