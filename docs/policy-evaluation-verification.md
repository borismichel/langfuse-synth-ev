# Policy evaluation verification — 10 September 2026

Scope: portal issue #235, EV kit base `afc3131`. Local implementation is reviewed;
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

The prerequisite #234 session owns Chrome. No browser changes or historical/model
runs were performed for #235. The read-only experiments endpoint returned no runs
on 10 September at 16:26 UTC; this does not establish current or eventual results.

Still required:

1. Actual native experiment item input/output shapes and successful normalization
   in Langfuse's runtime (local fixtures do not prove this).
2. Contrasting editor tests, evaluator URL/version and explanations.
3. A deliberately bounded historical UI batch, with one `credit_agent` per
   application and reconciled expected/scored/missing/execution-error coverage.
4. Explicit baseline and candidate evaluator selection, experiment URLs, matching
   settings/cohort, scores beside outputs, and preserved rejection controls.
5. Optional LLM judge calibration and explicit mappings if that method is shown.

The reusable setup guide records the steps and evidence to collect. The Companion
fallback is labelled decision agreement and is never reported as a native score.
