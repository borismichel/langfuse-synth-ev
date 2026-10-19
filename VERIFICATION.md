# Verification checks

Current release evidence: [19 October verification and delivery](docs/ev-context-verification.md). The released-image rehearsal in Cloud 4.64.0 includes Halo curation, five valid Playground pairs, native policy scores **4/9 → 9/9** and automatic live baseline/candidate/control scores. Use the generated Presenter Runbook for this deployment’s links and policy constants.

Use the same configuration, target and saved run state as the initial deployment. Verify the project identity before reading results. Credentials stay in the configured environment; never copy them into evidence.

## Current-run verification

```bash
synth verify --config config/demo.yaml
```

Inspect every reported check. Counts, prompt versions, policy dates and reserved IDs come from this run's saved state; do not compare them with a hardcoded example from another deployment. Allow bounded ingestion/indexing delay and repeat reads if needed. A missing observation or failed read is not a passed check.

Verify the hosted regression and demonstration dataset schemas, source links, all three string inputs (`application`, `handbook`, `policy_updates`) and structured expected outputs. The short cohort starts with eight authored cases; curated items change its count and version. Reserved cases must remain absent until deliberately added.

For a disputed historical case, inspect the amendment in `retrieve_policy`, the same full context in the generation metadata, and its absence from the baseline's compiled input. Check the actual prompt version association and decision amounts. Historical quality and disagreement scores are generated fixtures; they are not newly executed policy evaluations.

## Native and live verification

Follow the delivered Presenter Runbook. Save actual Halo investigation/approval evidence, the selected project connection/model, shared output schema, fixed prompt versions and frozen dataset version. Check both experiments' complete score coverage and monetary outputs, including rejection controls.

A fresh successful Companion trace contains root, agent, real bundled retrieval and one real decision generation. Confirm the generation's exact compiled input, native prompt version, actual output/usage and all three `metadata.prompt_variables`. After enabling the scoped incoming rule, verify a new undisputed agent observation is automatically scored. Following promotion, verify both an eligible approval and a genuine rejection.

Record missing/pending scores, execution errors, malformed output and policy failures separately. No HTTP-success, local test or SDK decision-agreement card substitutes for native policy-score evidence.

## Offline and delivery checks

Run the repository's tests, manifest validation and established advisory conformance gate before release. Preserve intentional historical golden changes with their causal explanation. Strict authoring check currently reports inherited Companion migration findings; see the current evidence record rather than claiming strict readiness.

Admission must identify the exact immutable release and signed image digest. Catalog publication then requires one ordinary fresh deployment, its delivered artifacts and real live verification. Existing deployment projects are not reset or overwritten.

[Current verification status](docs/ev-context-verification.md) distinguishes these gates. September verification records retain their dates and apply only to the prior story.

## Reset

Use a fresh demo project for another import. OTLP appends; `import-spool` is non-resumable. Do not re-seed an occupied project. `synth script` only regenerates the runbook from saved state and does not change historical data or prompt labels.
