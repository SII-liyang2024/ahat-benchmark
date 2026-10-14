# Evaluation protocol

The protocol matches AHAT's `baseline/llm/run_eval_rubric.py` reviewer used for
saved GPT results, with the action/arity guard from `review_luna_benchmark.py`.
The four original paper prompts, domain and VAL snapshots are fingerprinted in
`benchmark_manifest.json`. [Parity evidence](validation/parity.md) records the
implementation comparison.

## Deterministic validation

VAL receives a **full-scene**, deterministically sorted PDDL problem. It is
independent of the plan's mentioned entities. This matters when a negative
existential precondition depends on an otherwise unmentioned object.
Facts incompatible with domain types or PDDL identifiers are dropped and
recorded in `excluded_ill_typed_initial_facts`.

Empty and malformed plans are rejected. Unknown actions and incorrect argument
counts are checked before native VAL, because missing arguments can crash the
native runtime. The default timeout is 10 seconds. `invalid` requires a native
invalid verdict; process failures without a verdict are `val_error`.

## Rubric evidence and score

Each valid plan receives four independent chat-completions calls:

| Dimension | Input | Weight |
| --- | --- | ---: |
| D1 Goal Achievement | Instruction and exact final PDDL state | 0.40 |
| D2 Intent Understanding | Instruction, inventory/location summary and plan | 0.20 |
| D3 Completeness | Instruction and plan | 0.20 |
| D4 Execution Quality | Instruction and plan | 0.20 |

The final state starts from the initial PDDL persisted by VAL and applies the
domain's simultaneous STRIPS delete/add effects. No additional effects are
inferred by mutating the scene graph. The domain's declared semantics, including
omissions, determine D1 evidence.

Replies require a nonempty rationale and exactly one score from
`{0, 0.25, 0.5, 0.75, 1}`. Boolean and arbitrary numeric scores are rejected.
D1 also requires a real boolean `critical_failure`. A critical failure caps the
weighted score at `0.2`, even if the weighted score is higher. Good/Normal/Bad
labels supplement the numeric metric.

YAML weights, cap and label thresholds are passed to the evaluator and included
in the signed protocol. Changing these settings changes the evaluation
protocol. API sampling/reasoning parameters are omitted, preserving deployment
defaults. Judge output can vary between runs even with identical input.

## Denominator and failures

All dataset cases are in the denominator. `invalid`, `missing_plan` and
`malformed_plan` receive zero. `val_timeout`, `val_error`, incomplete reviews,
API failures and malformed judge replies produce no score. A final report is
publishable only when no such system errors remain.

`final_results.json` includes per-case scores, VAL status, the publishable flag,
full-case mean and descriptive statistics across valid judged tasks. A single
run's task variation is not a confidence interval across repeated judge runs.

## Checkpoints and parallelism

Stages write atomic checkpoints after each case; judge dimensions also checkpoint
individually. Resume reuses successful dimensions and retries failed ones.
Inputs and protocol signatures include code, data, inference, domain, native
runtime, prompts, model, endpoint, scoring and upstream signatures. Changed or
unversioned checkpoints are rejected. Use a new directory after upgrades.

`--workers` controls concurrent cases, and `--dimension-workers` controls
concurrent dimensions within a case. For a single CLI run, 16 × 4 permits at
most 64 concurrent chat-completions requests. Independently launched processes
each have their own limit. Retries remain inside a dimension's worker slot.
