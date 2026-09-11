# EV UI refresh: release rehearsal — portal #238

Status on 11 September 2026: **Cloud comparison and live policy checks passed;
signed release/registration and the complete depot-delivered rehearsal remain pending.**
Version `0.7.0` is prepared in `pyproject.toml`; this is not evidence that its tag,
image or signature exists. Keep the depot registered to `v0.6.2` until the gates
below pass. Do not close portal #238 based on these component checks alone.

## Revisions and target

- Kit base: `ca1b4458160652322c2c0f333a27158023dddbca`, fetched from `origin/main`.
  The release change moves `decision` after the amounts and reason in
  `prompts/credit_decision.v2.txt`. Policy arithmetic, parser and dataset expectations
  are unchanged. All core pins remain `v4.1.1`, the latest core tag checked.
- Depot base: `cc31f3e`, fetched from `origin/main`. Current registration and both
  inspected local Companion images are `v0.6.2`, kit revision
  `d20ce2f8e34d9cb104fd49f96acf4d6b82c5df99`.
- Cloud EU: [new-ev-demo](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp),
  project `cmtvq2l5x00u8ad0d7rpc0uvp`.
- Saved seed: 100 deterministic/model-free traces, seed 42, effective date
  `2026-09-03`, grant EUR 6,000, BEV price cap EUR 50,000. The prior seed and its
  state were reused; no history was re-ingested. This does not certify a fresh
  focused deployment with the current runbook anchors.
- Regression dataset: 24 items. [Short cohort](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/datasets/cmtvqkwdv015nad0dfnit60qm/items):
  11 authored cases plus one previously curated source-linked observation, 12 total.
- Native model: existing Anthropic connection, `claude-sonnet-4-6`, temperature 0,
  maximum 512 output tokens, `ev_credit_decision` structured-output schema in all
  three runs. The schema requires all six Decision fields and rejects additional
  properties; it does not encode policy outcomes.
- [Hosted policy evaluator](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/evals/6c9c5ded-401f-4f18-83aa-d9323e7f796f):
  existing `policy_correctness` version 1 (`cmtvs2pz701o5ad0f2ywor1n9`). Its policy
  constants and code were not changed.

No credentials are part of this record. [Curated machine-readable evidence](evidence/238-rehearsal.json)
contains run settings, item IDs, actual applications/outputs, hosted scores,
prompt-version links and the unsuccessful pre-fix live submission.

## Native UI observations and comparison

The observed path is **Datasets → Experiments → Run experiment → via User
Interface → Configure**. The wizard steps are **Prompt & Model**, **Dataset**,
**Evaluators**, **Experiment run details**, and **Review**. The final button is
**Run Experiment**. The completion notification links to **View experiment**.

**Dataset Version (Optional) is available in this target's experiment wizard.**
Every run below pins `2026-09-10T16:26:15.856Z`; this is confirmed in each run's
API metadata. The UI presents 18:26 with an `(UTC)` suffix on this Berlin browser;
record the API's UTC timestamp. The [current UI documentation](https://langfuse.com/docs/evaluation/experiments/experiments-via-ui)
still says only the latest dataset version is supported. For this target, the
observed selector and recorded run metadata resolve that conflict. Other targets
must be checked rather than assuming parity.

The wizard reported `application: 12 / 12`. Every compiled user message equals
the dataset item's JSON application string; both expected numeric amounts and
decision were reviewed. No unresolved prompt variable was used. The source item
and its `application` mapping are recorded in the [earlier curation verification](native-prompt-experiments.md#cloud-verification-record).
This session did not add a second reserved item or claim a second live-add exercise.

**Attach evaluator → policy_correctness** exposes the text “Observation data is
available directly in code evaluators, so no variable mapping is required.” It
remained attached for subsequent native runs. This dataset attachment is separate
from the existing scoped incoming-observation rule. Historical/editor checks are
in [#235's evidence](policy-evaluation-verification.md); they were not repeated here.

| Native run | Numeric prompt | Expected / scored | Pass | Policy failures | Malformed / execution errors |
|---|---:|---:|---:|---:|---:|
| [Baseline](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/experiments/results?baseline=cmtx38jwh000lad0dcq3hgm4s) | 1 | 12 / 12 | 4 | 8 | 0 / 0 |
| [Format-only check](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/experiments/results?baseline=cmtx35mp302uzad0lz76asphm) | 2 | 12 / 12 | 12 | 0 | 0 / 0 |
| [Revised release candidate](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/experiments/results?baseline=cmtx3cuah002dad0ditu06doy) | 3 | 12 / 12 | 12 | 0 | 0 / 0 |

These are three diagnostic/rehearsal runs; the presentation uses only the baseline
and final candidate. Candidate v3 matches every reviewed decision and numeric field,
including eligible repairs, the EUR 35,999 / 36,000 boundary, the still-over-limit
BEV, cap/date boundaries, and non-BEV controls. Baseline policy failures include
correct rejections with wrong grant/principal; they are not execution failures.

All item IDs, status, inputs, expectations, metadata and source links remain
identical to the 10 September snapshot. Canonical SHA-256, sorting by item ID:
`1fa2d91f46eff4274e14f580a5c87930a240d089b55f489375cf0f514459968a`.
Run metadata independently confirms the same pinned dataset version.

The completed baseline/format-only comparison was opened through its normal
results URL: the table displayed 33% versus 100% true and per-item false → true
changes. This exercises retrieval of a completed comparison. For a presentation,
bookmark the [baseline/final-candidate comparison](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/experiments/results?baseline=cmtx38jwh000lad0dcq3hgm4s&c=cmtx3cuah002dad0ditu06doy).
Say that it is a completed rehearsal when using it. Missing scores or temporarily
empty outputs during ingestion are pending evidence, not a failed policy check;
wait for all expected IDs, outputs and scores. Do not infer success from an average.

## Live failure, repair and one promotion

The real Companion `/submit` route reproduced the existing v2 failure on a BEV
priced EUR 48,000 with line EUR 40,000: grant 6,000, financed 42,000, **approve**.
The existing incoming rule scored it false, explaining that rejection was expected.
[Failed trace](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/b016c9dda07ce9a35477eec02d373a06)
is retained; no output or score was repaired.

The prompt change addresses premature decision emission by requesting the amounts
and explanation before the decision field. A separate candidate label first tested
five cases through the real live model-call/parsing path: repaired eligible loan,
both known BEV rejection controls, the EUR 1 boundary, and PHEV rejection. All five
matched policy. Raw responses still used single Markdown fences, which the existing
live parser accepts. No parser or deterministic-oracle change manufactured a pass.
The model probe finished all five checks; its redundant file save inside the
container hit a permission error. Its complete stdout was retained locally and
curated into the linked evidence, without repeating the model calls.

After the native v3 run passed, the UI path **Add prompt label → production → Save
and promote to production** moved production from v2 to v3 exactly once at
`2026-09-11T15:10:30.598Z`. The project was already on v2 from #236; it was not reset
to v1 to manufacture a new baseline. Numeric v3 in this reused project corresponds
to the kit's revised candidate template; fresh projects can assign different numbers.
Always use the deployment's recorded numeric versions.

| Fresh route submission | Version | Grant / principal / decision | Hosted policy score |
|---|---:|---|---|
| [BEV EUR 38,000, line 32,000](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/9e940598d73625937e39284071af13ef) | 3 | 6,000 / 32,000 / approve | true |
| [BEV EUR 48,000, line 40,000](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/033fd54ad0c212fab212b2ae33a2c10d) | 3 | 6,000 / 42,000 / reject | true |

Both undisputed submissions carry native managed-prompt version 3 on their
`decision` generation and one observation-linked policy score on `credit_agent`.
They were not manually evaluated. The scoped rule from #236 was not edited.

**Execution scope:** FastAPI TestClient invoked `/submit` using isolated current
kit source inside an existing local EV container, its existing model access and
the designated project's saved policy state. This was not a browser form check
or deployment of the candidate through the depot. Live calls use the core v4.1.1
Anthropic adapter, which omits sampling parameters even though the kit requests
temperature 0. Native and live settings are therefore not provider-identical.

## Local checks and remaining release gates

Current kit tests: 143 passed (one existing Starlette/AnyIO warning). The
determinism/native-experiment subset also passed after the prompt edit, with no
golden rewrite. Contract conformance passed all blocking checks; the existing
health-path and companion-factory advisories remain. The full 143-test suite and
blocking conformance checks passed again with the complete release-preparation
diff; the runbook generated from saved state without network calls. Parallel
review of commit `270ec32` found Standards: 0 findings and Spec: 0 actionable
defects, with release/registration and the delivered timed rehearsal explicitly
remaining incomplete. Recheck the final release commit before tagging if it changes.

The operator selected `new-ev-demo` and the local depot at
`http://localhost:3009`. This is an update to the already registered EV kit.
The depot's [kit author guide](https://github.com/borismichel/langfuse-demo-depot/blob/cc31f3e/docs/user/kit-author-guide.md#1-register--sync)
defines the existing-kit path as release → registry ref bump → sync; scratch
admission gates a **new** kit. The `AdmissionVerdict.eligible_to_pin` contract
likewise keeps routine re-sync on validate → resolve published image → upsert.
No new scratch admission run is required for this existing-kit update.
The local depot has no scratch target configured; do not point its seed ladder
at the already seeded `new-ev-demo` project.

The remaining sequence uses the existing kit/depot process:

1. Complete review and merge the candidate; cut `v0.7.0` only at its reviewed
   release commit. The existing Publish workflow builds, pushes to GHCR and
   cosign-signs the image using core v4.1.1. Record the workflow URL and immutable
   digest; verify the signature through normal admission/sync.
2. Validate the released manifest, resolve its published digest and verify its
   signature using the worker's `verify_image_signature` check directly, without
   starting a seed job, before changing the registration.
   Scratch admission is not applicable to this already registered kit update.
3. Update only the EV `registry.yaml` reference after its gates pass. Respect the
   depot's CI/merge gate; a stalled private-repo CI needs the user's explicit
   go-ahead. Sync the updated reference into the selected local depot and retain its validation
   and image-resolution result. Preserve the existing seeded project and
   its deployment: a registry sync does not upgrade existing deployments. A fresh
   full seed requires an empty presentation project; it must not silently replay
   history into the operator-selected `new-ev-demo` project.
4. Candidate artifact validation remains blocked for the selected seeded project:
   the depot has no supported in-place image/artifact upgrade operation. An empty
   project and a normal candidate deployment are needed before opening its new
   delivered Presenter Runbook and Companion links. The old deployment's artifacts
   cannot certify delivery of the candidate. Once that deployment exists,
   Configure the Cloud model/evaluator and scoped rule; complete and time the
   12–15 minute native loop, including one reserved live addition, two native
   comparisons, one promotion and final scored browser submission. Record the
   deployment ID, artifact links, immutable image, full settings and elapsed time.
   Exercise the completed-run fallback within that delivered flow.

Until these steps are recorded, artifact delivery, timing, signature
verification and final registration are **unverified**. Scratch admission is not
required for this existing-kit update. Optional Assistant and
alert actions were not exercised. Generated history and cached Companion analytics
remain historical, not measurements of the newly promoted policy.

## Rollback and presenter reset

The prior known-good registration is `v0.6.2` at
`d20ce2f8e34d9cb104fd49f96acf4d6b82c5df99`. Before replacing it, record the deployed
old image digest and deployment ID. For a release rollback, restore that registry
tag through the normal merge/sync path, then use the recorded signed image and
normal deployment controls. A registry rollback does not rewrite existing live
containers or move Cloud prompt labels.

For a fresh presentation, create a fresh demo project and deploy/seed once. Do
not re-ingest the same OTLP spool, clear its import marker, or describe reseeding
as an idempotent reset: ingestion appends. An interrupted import follows the
established recovery contract, with fresh-project recovery when necessary.
If deliberately reusing a project, retain its evidence and explicitly record any
prompt-label change outside the timed demo; that changes only future prompt
selection, not history, dataset contents, scores or cached analytics. Check the
baseline label, exact dataset version and current item count before presenting.

Presenter-visible changes prepared by this release are the native investigation,
code policy evaluation, source-linked curation, scored prompt comparison and
production-proof runbook from #233–#237, plus the candidate's corrected live
rejection behavior verified here. Model reliability is supported by these bounded
checks, not guaranteed for every possible application.
