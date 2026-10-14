# Validation against AHAT

The 2026-10-14 comparison verified the 2.0.0 evaluation implementation against
AHAT's reviewer for saved `gpt-6-luna` and `gpt-6.1-sol` plans. Version 2.1.0
changes packaging and CLI integration; the audited evaluation modules, native
runtime, domain and four prompts retain their original bytes.

## Deterministic agreement

- All 348 pinned HF reference cases matched initial PDDL, excluded facts and
  VAL verdicts. The 339 valid reference plans matched final states and all four
  dimension inputs.
- All 1,250 discrete score/critical-flag combinations matched weighted scoring
  and the critical-failure cap.
- All 696 saved GPT plans matched historical VAL verdicts. The 405 valid plans
  matched final states and all 1,620 judge inputs exactly.
- Replaying all 1,620 historical raw responses through this implementation
  reproduced dimensions, case scores and group means.

## Fresh ds-v4.1 comparison

A fresh review used `ds-v4.1-flash-w8a8`, API defaults and a global concurrency
limit of 64 (observed peak 64). All 1,620 dimensions succeeded with the expected
returned model. Two server errors recovered on retry; no final system errors
remained. A standard-library verifier independently recomputed the weights,
critical caps and full-case denominators.

| Planner | Split | AHAT historical | Fresh benchmark | Difference, percentage points |
| --- | --- | ---: | ---: | ---: |
| gpt-6-luna | easy | 33.90% | 34.62% | +0.72 |
| gpt-6-luna | medium | 15.05% | 15.74% | +0.69 |
| gpt-6-luna | open | 14.17% | 14.68% | +0.51 |
| gpt-6.1-sol | easy | 84.25% | 85.21% | +0.96 |
| gpt-6.1-sol | medium | 65.64% | 65.74% | +0.11 |
| gpt-6.1-sol | open | 63.98% | 63.61% | −0.37 |

Across all 348 cases per model: Luna 22.69% → 23.33%; Sol 72.93% → 73.25%.
All six group means are within one percentage point. Individual case scores
changed in 180 of 696 cases; three D1 critical flags changed. This is consistent
with judge variability, while deterministic checks and historical-response
replay directly support implementation parity.

These comparisons use **historical scenes saved with the inference**, because
newer bundled HF scenes differ. The numbers are an implementation comparison,
not performance measurements on the newly synchronized scenes.

The [public numeric summary](gpt6_parity_summary.json) includes group means,
counts, signatures and the original comparison-file hash. Full inference,
request logs, credentials and internal endpoint configuration are not part of
this distribution. The repository tests and offline example require no external
AHAT checkout or API.
