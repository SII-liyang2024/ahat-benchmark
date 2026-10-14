# Changelog

## 2.1.0 — 2026-10-14

- Package all registered datasets, configuration, domain, prompts and VAL assets
  in a Linux x86-64 wheel. Installed evaluation works outside a source checkout.
- Require an explicit judge endpoint; remove the internal serving address from
  public configuration. Support a working-directory `.env` and model override.
- Expose custom dataset registries, case workers and dimension workers in the CLI.
- Add an offline end-to-end example, contribution guide, licensing, citation,
  release checks and CI. Archive local audit tools and experimental materials.
- Keep the audited full-scene validation, prompts, scoring and final-state
  computation from 2.0.0. Data and VAL/domain/prompt bytes are unchanged.

## 2.0.0 — 2026-10-14

- Pin the 348-case HF evaluation data at
  `44de8a66c58cfd4cea03923bed9dbb8bd69d8f85`.
- Match the audited AHAT reviewer: four original paper prompts, strict scores,
  weights `0.4/0.2/0.2/0.2`, critical-failure cap `0.2`, deterministic full-scene
  VAL and exact simultaneous STRIPS state updates.
- Sign inputs and protocols, checkpoint individual dimensions and distinguish
  infrastructure errors from invalid plans.
- Reject unknown actions and wrong argument counts before calling native VAL.
- Verify parity on 348 reference plans and 696 saved GPT plans, with fresh
  ds-v4.1 review. See [validation evidence](docs/validation/parity.md).
