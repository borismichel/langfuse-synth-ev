# Missing policy binding — verification record

Current change: Depot tickets [357](https://github.com/borismichel/langfuse-demo-depot/issues/357), [358](https://github.com/borismichel/langfuse-demo-depot/issues/358), [359](https://github.com/borismichel/langfuse-demo-depot/issues/359). This record separates evidence from completion claims. Earlier September records tested the instruction-based story and do not verify this repair.

## Candidate identity

- Package version remains 0.7.2 during implementation; no new release is claimed here.
- Core dependency: immutable `501519ec77ed885d594fb8270c44890ced40abd6`, package version 5.0.0; shared CI workflow separately remains v5.0.0.
- Langfuse Python SDK is pinned to `5.0.1`; record the installed version with each live/release run.
- Default task model: Anthropic `claude-sonnet-4-6`, 512 output tokens, shared Decision schema. Native UI settings must be selected explicitly.
- Source revision, project, prompt/dataset/evaluator versions, image digest and deployment IDs belong to each completed run below; unexecuted gates have no invented identifiers.

## Evidence and gates

| Gate | Status | Scope/evidence |
|---|---|---|
| Accepted failure mechanism | Passed | Retrieved amendment omitted by baseline template; candidate adds `policy_updates`. Three complete input fields and the same system/model/schema are preserved. |
| Portable prototype evidence | Passed | [357 evidence](evidence/357-policy-context/README.md), labelled direct-provider simulation. |
| Implemented-kit provider trial | Passed | [24 calls](evidence/359-implemented-model/README.md): valid24/24, baseline policy-correct4/12, candidate12/12. Not native UI proof. |
| Self-contained runbook | Implemented | Generated from saved anchors with evaluator source, response schema, three-field reviewed cases, source-linked curation, rule recipe and recovery. Test execution of its embedded evaluator uses overridden saved policy constants. |
| Blocking offline gates | Passed on reviewed integration plus evidence changes | 194 tests passed, including deterministic/golden checks; manifest validation passed; established advisory conformance passed with the two inherited findings below. |
| Strict authoring readiness | Pending migration | Two inherited advisory findings: root health path and legacy Companion factory. Strict `local_ready:false` is retained; no broad adapter migration in this change. |
| Halo and native UI rehearsal | Partial, actual evidence captured | [Native record](evidence/359-native-ui/README.md): eight-item native baseline 4/8 versus candidate 8/8; Halo-created nine-item cohort baseline 4/9 versus candidate 9/9 with all 18 automatic scores independently verified and identical frozen settings. Corrected fresh-project Halo diagnosis identifies the final generation omission. Corrected local live monitoring is verified below; signed-release admission and Depot delivery remain pending. |
| Automatic live policy scores | Passed local Companion rehearsal | Corrected EV bcfe894 / core 501519: baseline v1 false, promoted eligible v2 true, PHEV rejection v2 true. Each has exactly 4 observations, 1 generation/usage record and 1 automatic EVAL score; no feedback required. Earlier duplicated provider span is retained as a resolved finding. [Exact evidence](evidence/359-native-ui/README.md#corrected-live-comparison-and-promotion). |
| Immutable release and signed image | Pending | No new tag or digest yet. |
| Admission and catalog pin | Pending | Must identify exact reviewed artifact. Existing deployments stay pinned. |
| Ordinary fresh Depot deployment | Pending | Must verify delivered artifacts and real Companion turn through the new catalog pin. |

## Known UI behavior

On the current Cloud rehearsal target, opening a managed prompt in a fresh Playground selected the organization's default `Anthropic:claude-sonnet-5` and left structured output unselected. This is setup behavior, not evidence of a model run. The runbook requires explicitly choosing the intended model, token limit and shared schema in each window and confirming the same settings in native experiments.

## First native rehearsal attempt — retained finding

The coordinator observed a native Playground pair with baseline grant0/principal45000/reject and candidate grant6000/principal39000/approve. Halo reached the intended missing-binding diagnosis after two turns, but also identified a separate synthetic-history defect: the affordability tool used the gross amount despite an eligibility result containing the grant. That first target is not clean end-to-end proof. The fixture was corrected so the synthetic tool calculates the correct net amount independently and the decision input omission is the first divergence. Halo in the second fresh project then identified that exact sequence. Both the first failure and corrected diagnosis are retained in the [native record](evidence/359-native-ui/README.md).

## Historical provenance

[September native experiments](native-prompt-experiments.md#historical-cloud-verification--superseded-story), [release rehearsal](ev-ui-release.md), [presenter verification](presenter-runbook-verification.md), [policy-evaluation verification](policy-evaluation-verification.md) and [live results](live-policy-verification-results.md) retain their original dates and failures. Their images/results describe an earlier prompt design. Current inspected captures and safe exports are in [359 native evidence](evidence/359-native-ui/README.md), with explicit project/object scope.

The historical Spool golden changed with #357 to expose actual policy documents, full prompt variables and compiled omission while keeping generated data model-free. UI golden differences in #359 correct labels and remove claims of simulated live steps, guaranteed label outcomes and promised human review. No visual redesign or extra execution infrastructure was introduced.
