# Missing policy binding — verification record

Updated 19 October 2026 after release and ordinary Depot delivery. Tickets [357](https://github.com/borismichel/langfuse-demo-depot/issues/357), [358](https://github.com/borismichel/langfuse-demo-depot/issues/358) and [359](https://github.com/borismichel/langfuse-demo-depot/issues/359) are closed. The documentation refresh carries forward the unchanged v0.8.0 execution evidence below; it does not claim another model rehearsal.

## Released identity

- EV **v0.8.0**, source **9c6410f1bfd1fe7ac2c91fb7916eeca9355cdbc7**.
- Signed image `ghcr.io/borismichel/langfuse-synth-ev@sha256:e140f66a20393f83e2c1e304b26586dba9e3964cf50f6cdce8a9d6f8eafdc89d`.
- Core **501519ec77ed885d594fb8270c44890ced40abd6**, package 5.0.0; Langfuse Python SDK **5.0.1**.
- Ordinary deployment **697035a5-c5a2-4c32-97a1-6a4652e19258**; [project](https://cloud.langfuse.com/project/cmvfnhw3l00cyad0miroa0t9k); Cloud **4.64.0**. Seed 42, 120 traces over 30 days, as-of 2026-10-19, ambient incidents disabled, 1,354 imported events.
- The reference project's `production` label now selects v2. New deployments start with the baseline; existing histories remain intact.

## Evidence and gates

| Gate | Status | Scope and evidence |
|---|---|---|
| Failure mechanism | Passed | Baseline omits retrieved `policy_updates`; candidate adds only that binding, with identical system/model/schema. |
| Direct-provider trial | Passed | [24 calls](evidence/359-implemented-model/README.md): valid 24/24, baseline 4/12, candidate 12/12. Separate from native UI evidence. |
| Offline checks for v0.8.0 | Passed | 194 kit tests, manifest validation and established advisory conformance. |
| Strict authoring readiness | Pending inherited migration | `local_ready:false`: root health path and legacy Companion factory findings. No claim that these were fixed by this story or documentation change. |
| Signed release | Passed | Immutable source and digest above; signature verification retained with admission. |
| Admission | Passed | Run **48a08fd7-ffda-401e-ba6a-d8ae7f4b6582**, six gates, separate disposable target. First failed naming-guard attempt retained; zero events imported there. |
| Catalog and ordinary delivery | Passed | Catalog PR360 merged; ordinary probe/plan/seed/verify succeeded, nine artifacts readable and deployed Companion inspected. |
| Halo | Passed for investigation and curation | Neutral diagnosis cites omitted compiled context. One reserved item added to existing cohort, then independently read back. New-dataset creation is not claimed for this final project. |
| Playground | Passed with retained setup failures | Five valid pairs per version; baseline rejects at €45,000, candidate approves at €39,000. Two earlier empty-object schema-setup outputs retained separately. |
| Native Prompt Experiments | Passed | [Comparison](https://cloud.langfuse.com/project/cmvfnhw3l00cyad0miroa0t9k/experiments/results?baseline=cmvfnu53u00dgad0elletj4pa&c=cmvfnvpen00qgad0e9zbn9txv): v1 **4/9**, v2 **9/9**, all 18 automatic scores and monetary outputs verified against frozen version **2026-10-19T19:39:47.535Z**. |
| Automatic live scores | Passed | Undisputed baseline false, eligible promoted v2 true, PHEV rejection v2 true. Four observations, one generation/usage record and one agent score per trace; all four incoming-rule filters inspected. |
| Documentation refresh | Current source and captures | [Fresh screenshots](img/presenter-20261019/README.md) and revised runbook use the final same-project evidence. Any later documentation-only release has its own admission/delivery receipt; it does not change this v0.8.0 execution identity. |

The [complete delivery record](https://github.com/borismichel/langfuse-demo-depot/blob/b294cbe418eb03b5a66fbbbc6e6a8abe9d892aac/docs/release-evidence/ev-context-359/delivery/README.md) contains sanitized receipts, exact object IDs, both reviews, per-item readbacks and image provenance. A screenshot is supporting evidence, not a replacement for score coverage.

## Current UI setup checks

Choose Sonnet 4.6, 512 output tokens and the same six-field structured output schema explicitly in each Playground window and native experiment. Temperature was omitted in both final runs. A fresh Playground may select the connection's default model and no schema. Save and reopen the schema to verify the complete definition persisted before running; an empty-object output is not a valid comparison. Native experiments must explicitly select `policy_correctness`.

## First native rehearsal attempt — retained finding

The coordinator observed a native Playground pair with baseline grant0/principal45000/reject and candidate grant6000/principal39000/approve. Halo reached the intended missing-binding diagnosis after two turns, but also identified a separate synthetic-history defect: the affordability tool used the gross amount despite an eligibility result containing the grant. That first target is not clean end-to-end proof. The fixture was corrected so the synthetic tool calculates the correct net amount independently and the decision input omission is the first divergence. Halo in the second fresh project then identified that exact sequence. Both the first failure and corrected diagnosis are retained in the [native record](evidence/359-native-ui/README.md).

## Historical provenance

[September native experiments](native-prompt-experiments.md#historical-cloud-verification--superseded-story), [release rehearsal](ev-ui-release.md), [presenter verification](presenter-runbook-verification.md), [policy-evaluation verification](policy-evaluation-verification.md) and [live results](live-policy-verification-results.md) retain their original dates and failures. Their images/results describe an earlier prompt design. Current inspected captures and safe exports are in [359 native evidence](evidence/359-native-ui/README.md), with explicit project/object scope.

The historical Spool golden changed with #357 to expose actual policy documents, full prompt variables and compiled omission while keeping generated data model-free. UI golden differences in #359 correct labels and remove claims of simulated live steps, guaranteed label outcomes and promised human review. No visual redesign or extra execution infrastructure was introduced.
