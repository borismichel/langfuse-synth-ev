# EV demo — implementation specification

Current contract, 19 October 2026. This replaces the initial instruction-based design. The original specification remains in [the v0.7.2 source history](https://github.com/borismichel/langfuse-synth-ev/blob/2bb50460c584992bb42abbc91d383c18ae4f7dde/langfuse-demo-synth-spec.md); its prompt text and SDK-first presenter journey do not describe this repair.

## Purpose

Demonstrate an evidence-led investigation in Langfuse: a lender retrieves the right policy but omits one field when compiling the decision prompt. Halo helps investigate and curate the regression dataset. Native Playground and Prompt Experiments demonstrate the binding change. A fresh Companion submission verifies the promoted prompt and native policy monitoring.

This is a fictional lending policy, not a statement about a real subsidy programme. All history is generated and model-free. Real model executions and native UI results have separate evidence records.

## Policy and worked example

The default policy grants EUR 6,000 to BEVs with a list price at or below EUR 50,000 for applications on or after the run's effective date. Deduct the eligible grant from the list price, then approve if financed principal is at or below the approved credit line. PHEV/ICE, over-cap and earlier applications receive no grant. The deployment configuration controls the amount, cap and date offset; materialized documents and evaluator constants use the saved run anchor.

Flagship: BEV EUR 45,000, line EUR 40,000, effective date or later. Correct grant EUR 6,000, principal EUR 39,000, approve. A baseline that sees the handbook alone returns grant EUR 0, principal EUR 45,000, reject. The demonstration also requires genuine rejection controls, including a qualifying BEV at EUR 49,000 with line EUR 40,000: grant EUR 6,000, principal EUR 43,000, reject. Matching labels alone cannot establish correctness.

## Context assembly and prompts

A bundled local policy lookup returns a handbook and policy-update documents. This is actual local retrieval during live submissions and captured fixture evidence during historical generation. No external retrieval service or new infrastructure dependency is needed.

Every dataset item and live prompt-variable record contains the same three JSON strings:

| Field | Parsed content |
|---|---|
| `application` | Applicant ID, approved line, vehicle type/list price and application date |
| `handbook` | Handbook document ID, title, publication/effective dates and content |
| `policy_updates` | Array of policy amendment documents, including grant eligibility and arithmetic |

Both versions use the identical system message in `prompts/credit_decision.v1.txt` and `prompts/credit_decision.v2.txt`. Baseline user message:

```text
Application:
{{application}}

Lending handbook:
{{handbook}}
```

The candidate appends only:

```text
Policy updates:
{{policy_updates}}
```

The baseline contains no instruction to ignore a subsidy. The amendment is present in the retrieval result and full input record but absent from the compiled baseline model input. Same input, system instruction, model/settings and output schema are used for both variants. Numeric managed prompt versions are recorded; `production` and `development` labels can move.

## Decision contract

The shared structured-output schema requires one object with integer `list_price_eur`, `applied_grant_eur`, `financed_principal_eur`, `approved_line_eur`, string `reason` and enum `decision` (`approve` or `reject`), with no additional properties. The schema orders amounts before the decision. `seed.prompts.decision_schema()` is the source for the saved schema and live call; the complete schema is embedded in the generated Presenter Runbook.

The Companion validates exactly one answer, field types, unchanged application amounts, principal arithmetic and decision/line agreement. Contradictions or multiple answers are errors; no silent answer repair is allowed. Native UI experiments invoke the provider directly and do not run the Companion parser. Their independently configured policy evaluator must expose malformed or incorrect output.

The core model client is pinned to immutable commit `501519ec77ed885d594fb8270c44890ced40abd6` (package version 5.0.0), which adds optional provider-native `response_schema` support and suppresses duplicate provider telemetry when the application owns the generation. Workflow reuse remains independently pinned to core v5.0.0. No provider client fork lives in this kit.

## Historical data and live instrumentation

Seed emits deterministic backdated observations, sessions, prompt links and sampled synthetic quality/tone/disagreement scores. Historical fixtures include representative planner, retriever, eligibility/affordability tools, decision and explanation operations. They describe a generated application scene and make no model calls. Their eligibility evidence and decision input make the omitted binding inspectable.

Fresh Companion submissions record four actual observations:

```text
credit_agent.assess_application (root)
└── credit_agent (AGENT; application input, Decision output)
    ├── retrieve_policy (RETRIEVER; bundled lookup and returned documents)
    └── decision (GENERATION; exact compiled messages and actual provider output)
```

`decision` records the native managed prompt association, numeric version, all three `metadata.prompt_variables`, schema and actual usage. `credit_agent` carries the live evaluation scope. Compilation is not an extra tool call. Feedback targets the decision-bearing agent observation. Error/partial observations can exist when the customer request fails.

The Companion lending report is a cached generated-history snapshot. Its disagreement rate describes reviewed decisions, not the whole population. Fresh submissions, review requests and promotion do not rewrite that report or historical evidence.

## Datasets and independent policy evaluation

The configured regression dataset retains its existing size and eligible/control composition. A separate `<dataset-name>-demo` contains eight authored cases: flagship, before date, PHEV, above cap, qualifying but still above line, exact cap/date/line, eligible already affordable, and ineligible affordable. Reserved source-linked cases remain outside the seed datasets for assistant-led curation. Counts after curation are measured, not assumed.

Expected output comes from reviewed policy arithmetic, never copied from the observed erroneous response. Preserve source trace, decision observation and session links plus expectation provenance. All inputs contain all three strings in both versions, including ineligible cases. Freeze the actual dataset version after review and use it for both native runs.

The native Boolean `policy_correctness` Python evaluator reads the selected observation's own input/output and embedded deployment policy. It checks all four monetary fields plus decision. Malformed output is a distinct false result; invalid evaluator input/configuration is an execution error. A missing score is neither false nor success. Expected outputs calibrate the rubric; they do not replace observed output.

Historical evaluation is explicitly bounded to reviewed `credit_agent` IDs and controls. Native experiments explicitly select the evaluator in both run configurations. Incoming production rules select name `credit_agent`, type `AGENT`, environment `production`, and the deployment's exact `metadata.evaluation_scope`, at full sampling. No disagreement/tag requirement may exclude undisputed fresh decisions. Optional LLM judging stays separate from the arithmetic authority. Companion SDK fallback cards measure decision agreement only.

## Delivered presenter journey

The generated `DEMO_SCRIPT.md` is the single Presenter Runbook. It contains saved target links/policy/counts, neutral Halo investigation text, evidence checks, approved dataset curation, complete inputs/expected outputs, executable evaluator, shared schema, native comparison steps, production rule recipe, promotion and fresh monitoring. Supplemental documents are reference material, not extra required presenter downloads.

1. Open a disputed case and ask Halo to investigate without naming the root cause. Verify its actual citations and separate synthetic evidence from fresh execution.
2. Test the policy evaluator on a disputed case and correct rejection; inspect bounded history coverage.
3. Have Halo propose a source-linked regression item and dataset. Review the three fields and expected amounts, approve supported writes, reopen the saved object. Record unsupported actions or permission errors.
4. Open the generation in Playground. Explicitly choose the intended connection/model, 512-token limit and shared schema in each window. Do not assume prompt configuration is inherited. Compare identical complete input; confirm the candidate's compiled message includes the amendment.
5. Run fixed baseline/candidate versions on the same frozen cohort with identical settings and evaluator. Inspect all amounts, execution coverage and rejection controls. Rehearse five flagship attempts per version; retain all outcomes.
6. Activate the scoped incoming rule. Make a new undisputed baseline call after activation and inspect its automatic score.
7. Promote the tested numeric candidate once. Repeat the eligible application and a qualifying-but-unaffordable control; inspect the native prompt association and automatic agent score. Record failures and delays rather than retrying until green.

## Deployment, determinism and reset

The existing Manifest remains the only Depot integration surface. Preserve probe/plan/confirmation/generation/verify order, saved anchors, volume controls, model/provider choices, label behavior and existing pinned deployments. Seed and current-run verification use core transport/read seams. Source, package, SDK/core versions and model settings belong in the evidence record.

OTLP import appends and is not resumable. Never re-import an occupied project as a reset. Use a fresh authorized demo target. Re-rendering the runbook reads saved state and does not re-seed or move labels. Native UI runs replay captured retrieval context; the SDK/live path additionally exercises bundled retrieval and output parsing.

## Release gates and evidence

Maintain separate statuses for blocking offline checks, deterministic history, real provider trials, Halo/native rehearsal, live rule execution, admission and catalog delivery. Two inherited advisory conformance findings (`health_path: /` and the legacy Companion factory) are recorded migration debt; strict `local_ready` remains false while present. Do not describe advisory success as strict conformance. Actual model call/telemetry evidence supplements liveness-only smoke.

Release only the reviewed candidate: immutable kit tag/source, signed image digest, admission for that exact digest, EV catalog pin update, and one ordinary fresh deployment. Preserve unrelated kits and existing pins. [Current evidence](docs/ev-context-verification.md) records completed and pending gates; older September results are historical only.
