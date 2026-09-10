# Live policy verification — portal #236

Verified on 10 September 2026 in
[new-ev-demo](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp), using
EV kit revision `78b96c2`. The incoming rule automatically evaluated five fresh,
undisputed Companion submissions, once each on their `credit_agent` observation.
The same application changed from a v1 rejection with policy score false to a v2
approval with policy score true. A correct PHEV rejection also scored true.

**The candidate is not uniformly correct.** Two BEV rejection controls returned
`approve` despite explanations saying their net principal exceeded the line. The
rule correctly scored both false. These failures are retained below; there was
no prompt repair, re-promotion, or retry to replace their evidence. The native
candidate experiment also contains one malformed response. This verifies the
production evaluation workflow, not an all-green candidate or full #235 closure.

## Execution and scope

The user authorised using a local deployment's model access. An isolated copy of
the kit ran inside an existing local EV container with the designated project's
saved policy state. FastAPI `TestClient` invoked the actual Companion `/submit`
route with real model, prompt retrieval and Langfuse emission. This was an
in-process HTTP rehearsal, not a browser form submission or deployment of the
branch to the existing portal server. That server's code, configuration and state
were not overwritten; model credentials were not copied out of the container.
The temporary result pages were retained locally. Removing the copied rehearsal
source directory was denied by the container's filesystem permissions, so that
isolated `/tmp/ev-236-rehearsal` directory remains; it contains no model key.

The policy was EUR 6,000, BEV cap EUR 50,000, effective 2026-09-03. All live
applications were dated 2026-09-10. Local model access used the kit's existing
Anthropic configuration and a 512-token limit. The kit requested/logged
temperature 0, but inspection of the container's core v4.1.1 adapter confirmed
it omits Anthropic sampling parameters; temperature 0 is not a provider-effective
guarantee for these live calls.

[Hosted evaluator](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/evals/6c9c5ded-401f-4f18-83aa-d9323e7f796f):
`policy_correctness`, version 1 (`cmtvs2pz701o5ad0f2ywor1n9`). The exact packaged
Python evaluator successfully executed in Cloud, including its policy-context
guard. Hosted editor checks demonstrated both true and false before activation.

Rule `cmtvsbobx022iad0dtzdyubx5`, named
`ev_live_decision_5f1f890e74cc436b`, remains **Active**, at 100% sampling, with one
evaluator. All four conditions are joined with AND:

- Name: exactly `credit_agent`.
- Type: `AGENT`.
- Environment: `production`.
- Metadata `evaluation_scope`: equals `ev_live_decision_5f1f890e74cc436b`.

Before activation the actual picker matched one undisputed scope-review sample,
trace `6dab942573658d486c9e9779ea6abc91`, agent `aedabd7b03a556f8`. Activation
occurred after that sample at 17:08:23 UTC and before the baseline at 17:12:29 UTC;
the exact activation timestamp was not retained. Final UI inspection showed six
matches: that sample and the five submissions below. The initial sample has no
automatic score because it predates activation.

Each live trace contains nine observations; only its agent has the scope marker.
The final export separately contains 18 production generations, 12 tools, six
retrievers, 12 spans and 29 `langfuse-code-eval` spans; none match. The 24 native
experiment observations have environment `langfuse-prompt-experiment` and do not
match. Staging is excluded by the required production environment; no extra
staging submission was manufactured for this rehearsal.

Each scored agent carries its own application, policy and complete Decision.
No expected-output dataset, dispute tag or feedback score was needed. All five
trace score sets contain exactly one observation-linked policy score and zero
`user_disagreement` scores. Tags are `ev-grant` and `playground`.

## Candidate review and one promotion

The existing frozen native comparison used 12 items per version, the same dataset
version `2026-09-10T16:26:15.856Z`, Anthropic Sonnet 4.6, configured temperature 0, 512 tokens,
and no structured-output schema. A single manual code-evaluation batch scored
those 24 existing outputs; it did not repeat model calls or broaden the live rule.

- Baseline experiment `cmtvqtv8e01c3ad0f1567evze`: 4 pass, 8 policy errors.
- Candidate experiment `cmtvqx0za01c1ad0dpecjjt61`: 11 pass, 1 malformed output.
- Malformed candidate observation `8209528a47bcac79`, dataset item
  `bc564606-4899-5301-92cd-4c2d3b95f0f2`: two conflicting fenced Decision objects.

The failure was reviewed before proceeding with this bounded demo. Langfuse
recorded the one `production` label move from `credit_decision` v1 to v2 at
**17:18:44.780 UTC**. Existing v2/development labels were preserved. A subsequent
read confirmed production v2. Every live child `decision` generation has a native
managed prompt ID and numeric version, checked against the agent's metadata.

The manual experiment scores reuse the evaluator's job-configuration ID in their
metadata. That ID alone therefore does **not** prove an incoming-rule execution:
use the subject observation, environment, submission timeline and execution
provenance together. None of the five live subjects was manually evaluated.

## Fresh submissions and native scores

Amounts are EUR; all applications include the policy above. Trace links open in
the designated project. Full observation, generation, score and execution IDs,
inputs, outputs and explanations are in the [curated JSON evidence](evidence/236-live-policy.json).

| Case / trace | Price / line | Version | Actual grant / principal / decision | Policy score |
|---|---|---|---|---|
| [Baseline](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/a8599b575bcdc4b6be1b472583a6e94d) BEV | 38,000 / 32,000 | 1 | 0 / 38,000 / reject | false: grant, principal and decision wrong |
| [Same application](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/b750d570dcb2a81e42830cdb1405714e) BEV | 38,000 / 32,000 | 2 | 6,000 / 32,000 / approve | true |
| [Nearby rejection control](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/115382be9948757875e1ee2539891705) BEV | 38,000 / 31,000 | 2 | 6,000 / 32,000 / approve | false: expected reject |
| [Package rejection control](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/325483789efd1b2b981961ca4d6ab2ba) BEV | 48,000 / 40,000 | 2 | 6,000 / 42,000 / approve | false: expected reject |
| [Correct rejection](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/f5d6af752d0598af48a84752eb3f770a) PHEV | 42,000 / 40,000 | 2 | 0 / 42,000 / reject | true |

`POLICY_COVERAGE.py` over these five expected agent IDs and their exported scores:
**5 expected, 5 scored, 2 pass, 3 policy failures; 0 malformed, missing, pending,
execution errors, invalid records, duplicates or unexpected IDs.** Complete
coverage means every expected observation was scored, not that every decision
passed. The procedure separately explains pending, execution failure, policy
failure and malformed output; no production runtime failure was induced.

The baseline's historical output, native v1 prompt link and false score remained
unchanged after promotion. No re-seed, historical trace update, feedback change or
cached analytics refresh was performed. Historical appeal rates remain historical;
they were not measured again as evidence of a prompt fix.

## Optional alert and local checks

No alert or notification destination was created. The independent
[live procedure](live-policy-verification.md) documents the optional Boolean
average, 1-hour window, threshold below 0.95, explicit NO_DATA behavior and opt-in
notification destinations. This is a walkthrough, not evidence of an active alert.

Existing full suite: **140 passed** (one existing Starlette/AnyIO deprecation).
Targeted live-emission/presentation suite: **17 passed**. Pyright: **0 errors**.
Authoring conformance: blocking checks passed, two existing advisories (health
endpoint and Companion factory migration). Generated standalone evaluator:
**13/13 examples matched expectations**. Manual live-emitter checks covered scope
uniqueness, both prompt versions, correct rejection and policy-context mismatch.

Parallel reviews of the implementation: **Standards 0 findings; Spec 0 findings**.
Final evidence review found one wording issue about requested versus effective
Anthropic temperature; it was corrected after inspecting the actual adapter.
No unresolved Standards or Spec findings remain. The Cloud results and candidate
limitations above are part of the final evidence.
