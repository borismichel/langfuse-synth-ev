# Policy evaluation verification — 10 September 2026

Scope: portal issue #235, rebased onto EV kit `78b5e3d` after #234 PR #35. Local implementation is reviewed;
Cloud acceptance is **pending**. Do not close the issue based on this report.

## Local evidence

- Existing full suite: **140 passed** (one existing Starlette/AnyIO deprecation warning).
- Changed evaluator/package/coverage/script/Companion modules: pyright **0 errors**.
  Including `seed/run.py` reports two existing diagnostics at the `get_langfuse`
  Config protocol boundary and optional `lf.flush()`. Neither line changed here.
- Manifest conformance passes its blocking checks. Two existing advisories remain:
  health path `/` and the companion factory migration.
- Generated standalone evaluator executed outside repository imports on all 13
  reviewed examples: 11 policy-correct boundary/control outputs pass, the
  correct-reject/wrong-amounts output fails with `policy_error`, and non-JSON output
  fails with `malformed_output`. Invalid calendar input raises an execution error
  without substituting a policy score.
- Model-free historical fixture selection: **6 expected, 6 scored, 4 pass, 2 policy
  failures, 0 malformed, 0 missing, 0 execution errors, 0 duplicates**. Selected
  `credit_agent` input and output belong to each same observation. These results
  are local executions on generated fixtures, not Cloud evaluations.
- Coverage reporter accepts numeric Boolean exports `0.0`/`1.0`. An incomplete
  two-item example with one execution error reports both missing score IDs and
  separately identifies the execution-error ID. Missing-score and error/pending
  lists overlap when the failed/pending item has no score; do not sum them.
- Standards review: no findings. Spec review: the numeric Boolean coverage bug was
  fixed and re-reviewed; no remaining code findings. Cloud acceptance remains open.
- New automated regression tests were not added: the proposed TDD seams
  (`evaluate(ctx)`, package generation, coverage reporting) await user agreement.
  The checks above combine the existing suite and manual artifact execution.

## Remaining Cloud evidence

The #234 Cloud rehearsal is now merged in PR #35. This session left Chrome
untouched and used the read-only experiment-items API to retrieve its 24 synthetic
items (12 per run; no further cursor). All inputs were JSON-encoded chat arrays.
The evaluator now decodes that envelope before selecting the sole user message,
then parses the application JSON. This also supports already-decoded runtime arrays.

Executing the standalone source locally on the actual exported inputs/outputs, with
the deployment policy EUR 6,000 / EUR 50,000 / effective 2026-09-03, produced:

| Native run | Expected / locally scored | Pass | Policy failure | Malformed | Execution error |
|---|---:|---:|---:|---:|---:|
| `cmtvqtv8e01c3ad0f1567evze` (v1) | 12 / 12 | 4 | 8 | 0 | 0 |
| `cmtvqx0za01c1ad0dpecjjt61` (v2) | 12 / 12 | 11 | 0 | 1 | 0 |

The candidate's item `bc564606-4899-5301-92cd-4c2d3b95f0f2` contains two
conflicting fenced Decision objects. It is rejected as malformed rather than
silently choosing a corrected answer. These results match #234's independently
reviewed expectations. Both runs contain the same 12 item IDs; there are no missing
or duplicate local results. These are **local evaluations of actual Cloud outputs**,
not hosted `policy_correctness` scores or proof of the Cloud evaluator runtime.
See [the native rehearsal record](native-prompt-experiments.md#cloud-verification-record)
for experiment URLs, source provenance and pinned model/dataset settings.

Still required:

1. Successful execution in Langfuse's evaluator runtime; the real exported
   payloads are now checked locally but do not establish hosted execution.
2. Contrasting editor tests, evaluator URL/version and explanations.
3. A deliberately bounded historical UI batch, with one `credit_agent` per
   application and reconciled expected/scored/missing/execution-error coverage.
4. Explicit baseline and candidate evaluator selection, experiment URLs, matching
   settings/cohort, scores beside outputs, and preserved rejection controls.
5. Optional LLM judge calibration and explicit mappings if that method is shown.

The reusable setup guide records the steps and evidence to collect. The Companion
fallback is labelled decision agreement and is never reported as a native score.
