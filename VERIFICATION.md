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

Seeded, companion and SDK experiment `decision` generations use metadata contract
`decision_metadata_version = 1`. These are literal keys in the persisted metadata:

| Evidence | JSONPath on observation metadata |
| --- | --- |
| Application | `$['prompt_variables.application']` |
| Lending handbook | `$['prompt_variables.handbook']` |
| Policy updates | `$['prompt_variables.policy_updates']` |

The writers use the same builder before either raw OTLP or SDK ingestion. The
prompt-variable values remain the original JSON strings at the writer interface;
Langfuse's observation read API exposes their parsed objects/array. Response-schema
properties use explicit dotted keys as well. An explicit empty policy-update array
means no document was published at the application date; a missing metadata key
is invalid evidence, not proof that no grant exists. Actual model input remains
the compiled prompt, including the baseline's deliberately omitted amendment.

Verify one marked synthetic trace and one fresh live request in each target
project: read both back through the observations API, assert the same evidence
key names and value types, and check the deployment's own policy dates and amounts.
Check the live generation's managed prompt version against the production label.
The offline seed-versus-SDK export regression is necessary but does not replace
this persisted-data check.

Existing imported history retains the old nested format. Updating a companion
does not migrate historical records. Do not re-import an existing spool: OTLP
appends duplicate observations. Rebuild history only in a fresh target, or after
explicit approval to clear and regenerate the affected deployment data. Keep
prompt labels, curated datasets, evaluators and feedback out of any automatic
cleanup. Evaluator configuration is not changed by this producer fix.

Follow the delivered Presenter Runbook. Save actual Halo investigation/approval evidence, the selected project connection/model, shared output schema, fixed prompt versions and frozen dataset version. Check both experiments' complete score coverage and monetary outputs, including rejection controls.

A fresh successful Companion trace contains root, agent, real bundled retrieval and one real decision generation. Confirm the generation's exact compiled input, native prompt version, actual output/usage and all three literal `prompt_variables.*` metadata keys. After enabling the scoped incoming rule, verify a new undisputed agent observation is automatically scored. Following promotion, verify both an eligible approval and a genuine rejection.

Record missing/pending scores, execution errors, malformed output and policy failures separately. No HTTP-success, local test or SDK decision-agreement card substitutes for native policy-score evidence.

## Offline and delivery checks

Run the repository's tests, manifest validation and established advisory conformance gate before release. Preserve intentional historical golden changes with their causal explanation. Strict authoring check currently reports inherited Companion migration findings; see the current evidence record rather than claiming strict readiness.

Admission must identify the exact immutable release and signed image digest. Catalog publication then requires one ordinary fresh deployment, its delivered artifacts and real live verification. Existing deployment projects are not reset or overwritten.

[Current verification status](docs/ev-context-verification.md) distinguishes these gates. September verification records retain their dates and apply only to the prior story.

## Reset

Use a fresh demo project for another import. OTLP appends; `import-spool` is non-resumable. Do not re-seed an occupied project. `synth script` only regenerates the runbook from saved state and does not change historical data or prompt labels.
