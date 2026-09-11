# Policy evaluation verification — 11 September 2026

Scope: portal issue #235. Implementation merged in EV kit PR #36 after #234
PR #35. The hosted code-evaluation evidence is now complete: #236 supplied editor
and native experiment verification, and the bounded historical UI batch below
completed on 11 September. Candidate model failures remain visible; this is
verification of the evaluator workflow, not an all-green candidate.

## Local evidence (10 September)

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
  fixed and re-reviewed; no remaining code findings. Cloud acceptance was still
  open at that review; the hosted evidence below now completes the code workflow.
- New automated regression tests were not added: the proposed TDD seams
  (`evaluate(ctx)`, package generation, coverage reporting) await user agreement.
  The checks above combine the existing suite and manual artifact execution.

## Initial experiment normalisation check (10 September)

After #234 Cloud rehearsal PR #35 merged, the initial local check used the
read-only experiment-items API to retrieve its 24 synthetic
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

## Hosted evidence reconciliation

[The #236 verification record](live-policy-verification-results.md) records
contrasting hosted editor tests, the exact evaluator version, and explicit manual
evaluation of the 24 frozen native experiment outputs. Its baseline results are
4 pass / 8 policy errors, and candidate results are 11 pass / 1 malformed output,
matching the earlier local check. It also retains two fresh BEV rejection-control
failures. No model output was repaired or replaced for this verification.

[Hosted evaluator](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/evals/6c9c5ded-401f-4f18-83aa-d9323e7f796f):
`policy_correctness`, version 1 (`cmtvs2pz701o5ad0f2ywor1n9`). Constants are
EUR 6,000, BEV price cap EUR 50,000, effective 2026-09-03.

### Bounded historical UI batch — 11 September

In the designated project's Tracing table, the search `name:credit_agent` uses
**contains**, so it also displays `credit_agent.assess_application` siblings.
Exactly four rows whose name is `credit_agent` were manually selected, one per
application, each with `execution=generated_history`. No select-all action was
used. The confirmation read **Evaluate 4 observations**. The existing
`policy_correctness` evaluator was attached explicitly, its panel confirmed that
code evaluators read observation data directly, and **Run Evaluation with 1
evaluator(s)** started the batch. The saved evaluator and incoming rule were not
edited; no model call or historical decision rewrite was made.

The four expected observation IDs were recorded before submission. Execution
spans and Boolean scores were then read through the API. Each execution's input
and output exactly match its selected observation's own application and Decision.
All four spans ended normally with level DEFAULT and an empty status message;
each has one matching score and execution ID. Scores arrived at
**14:38:51 UTC** (16:38:51 Europe/Berlin).

| Application | Observation | Vehicle | Price / line (EUR) | Hosted result |
|---|---|---|---|---|
| anon_0051 | `5aab02bcd2f345c0` | PHEV | 38,500 / 34,110 | true: correct rejection, grant 0 |
| anon_0031 | `579fbd4ca4428514` | BEV | 38,500 / 34,000 | false: grant 6,000 and principal 32,500 should produce approval |
| anon_0050 | `8aba670ee0ea87c1` | PHEV | 43,500 / 39,718 | true: correct rejection, grant 0 |
| anon_0030 | `1f9949aa8f6d07ba` | BEV | 45,500 / 42,500 | false: grant 6,000 and principal 39,500 should produce approval |

Coverage reporter: **4 expected, 4 scored, 2 pass, 2 policy failures; 0 malformed,
missing, pending, execution errors, invalid records, duplicates or unexpected
IDs.** This reports complete evaluation coverage, not four passing decisions.
Full selected inputs/outputs, scores, explanations and execution references are
in [the curated historical evidence](evidence/235-historical-policy.json). The
[anon_0031 trace](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/1ec00b2367152952125d508ace99ffe5)
was also inspected in the UI: its `credit_agent` shows `policy_correctness: False`
beside its own input and unchanged rejection output (grant 0, principal 38,500).

These manually requested scores carry job-configuration ID
`cmtvsbobx022iad0dtzdyubx5`, also used by #236's incoming rule. As with the manual
experiment batch, that ID alone does not establish an incoming-rule execution.
The UI selection and execution timeline establish historical batch provenance.

The optional LLM judge remains a documented alternative in the reusable
[setup guide](policy-evaluation.md); it was not run or presented as verified here.
The Companion fallback remains labelled decision agreement, separate from native
`policy_correctness` scores.
