# Implemented-kit direct-provider trial — 19 October 2026

These are **24 real Anthropic calls using the implemented kit** at source `ecd8f59f5aab0ba5511e23191906855aaf556ddb`, core `8372f442e51e12234cb8b18ebd73c01b6cf0ff5a` (package 5.0.0), model `claude-sonnet-4-6`, max tokens 512 and the shared structured-output schema. The effective policy date for this trial was 12 October 2026. No credential values are stored here.

| Variant | Calls | Valid single Decision | Five-field policy correctness |
|---|---:|---:|---:|
| Baseline, missing update binding | 12 | 12 | 4 |
| Candidate, update binding added | 12 | 12 | 12 |

The eight reviewed cases include five repetitions of the flagship in each variant, with every other case executed once per variant. All flagship baseline outputs fail the complete policy check and all flagship candidate outputs pass. Both versions use identical system instruction, complete case input, model settings and schema. The candidate user template adds the update section. Responses retain every attempt, output and usage; no retry was removed.

- `manifest.json`: source/core identities, policy, schema, all inputs, expectations and compiled messages.
- `responses.jsonl`: all outputs, strict parser result, usage and independent five-field comparisons.
- `summary.json`: recorded totals.
- `run.py`: original trial harness, with its required accepted simulation case file included under `simulation/native-ui-assets/`.

This evidence is **not** a native Playground run, Prompt Experiment, Halo interaction, automatic production evaluation, admission or deployed-package proof. Those gates have separate records in [current verification status](../../ev-context-verification.md). The fixed identifiers inside this historical harness describe the trial above, not a later run made with changed installed source.

To repeat the original trial in developer mode, install the exact kit and core commits above with their provider dependencies, supply `ANTHROPIC_API_KEY` in the local environment, then execute `python run.py` from this directory. This makes 24 paid provider requests and writes a new timestamped result directory. Do not use its fixed source identifiers to label results from another revision. The fixture's original October dates are normalized to the recorded trial policy; deployed kits derive dates from saved run anchors.
