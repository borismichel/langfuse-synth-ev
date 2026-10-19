# Native EV prompt experiments — portal #234

Current release evidence: [19 October verification and delivery](ev-context-verification.md). The released-image rehearsal in Cloud 4.64.0 includes Halo curation, five valid Playground pairs, native policy scores **4/9 → 9/9** and automatic live baseline/candidate/control scores. Use the generated Presenter Runbook for this deployment’s links and policy constants.

The hosted regression dataset keeps its configured name and all 24 default cases.
Seeding additionally creates `<dataset-name>-demo` with eight authored policy cases.
Fixture generation and dataset creation make no model calls. The deployment artifact
`NATIVE_EXPERIMENT_ITEMS.json` contains the demonstration inputs and the three reserved
curation payloads, including policy arithmetic to review before use.

## Prerequisite and comparison settings

In the **target Langfuse project's Settings → LLM Connections**, verify a working
connection for the model you will select. A provider key injected into the Companion
App is a separate credential and does not establish this connection. Check the model
with a single Playground request before the presentation. Record project URL,
connection name, provider, model and result; never record the key.
[LLM Connection documentation](https://langfuse.com/docs/administration/llm-connection)

Keep provider, model, sampling settings and output schema identical across both runs. Opening a managed prompt in a fresh Playground can choose the connection’s default model and leave the schema unset. Explicitly select the intended task model, 512-token limit and shared schema in each window before running.
Use the deployment task model when that model is available through the connection;
otherwise record the deliberate alternative. Use temperature 0 when supported, and
512 output tokens. If the provider/model does not support a sampling parameter, omit
it in both runs. Select fixed numeric prompt versions, rather than a label someone
might move during the comparison. Both versions receive identical dataset input. The baseline binds `application` and
`handbook`; the candidate appends only `policy_updates`. Dates and policy values
live in the captured documents, anchored to this deployment.

Check the actual experiment form for a **Dataset Version** selector. If present,
record and reuse the same timestamp. If absent, finish curation first and keep the
cohort unchanged until both runs finish: no seeding, adding, editing, archiving or
deleting items. Record item IDs, inputs and expected outputs before and after.
Current Prompt Experiment documentation supports version selection. Record the actual selected version in both runs; an Items-tab history alone does not prove which version a run used.
[Dataset versioning](https://langfuse.com/docs/evaluation/experiments/datasets#versioning)

## Input contract and reserved observation curation

Each item input contains three JSON **strings**: `application`, `handbook`,
`policy_updates`. The latter two replay the captured local retrieval result. The
application string contains `applicant_id`, `approved_line_eur`, `vehicle` and
`application_date`, just like the live caller's `Application.model_dump_json()`.
Expected output is a structured Decision object, not a JSON string or the stale
rejection. Scenario information belongs in metadata. Hosted schemas reject a missing
variable, a non-string application and incorrectly shaped expected output. The SDK
fallback also validates the JSON contents before making any model call and identifies
the invalid item. Hosted validation checks the canonical field order and JSON field types as emitted
by the live caller (including vehicle fields `type`, then `list_price_eur`). Paste
the generated input unchanged; reordered objects must be serialised through the
Application model first. Inspect the mapping preview and policy date before running.
The schema checks date shape, not calendar validity (for example February 31).

Use Halo as the primary investigation and curation path in the generated Presenter
Runbook. Start from disputed decisions without revealing the root cause; verify its
citations to retrieval, compiled generation input and managed prompt. Ask it to
create a dataset and curate a reserved source case after reviewing the input and
expected output. Record actual approvals and supported actions. In the current rehearsal, multi-item writes became empty; explicit single-item calls succeeded and produced nine verified items (the eight authored cases plus one source-linked reserved case). Ask Halo for one item per call and read back before continuing. Halo could not start native Prompt Experiments; the presenter launches those through the UI with the evaluator explicitly selected. Missing capabilities
require a scope decision, not an unlabelled script replacement.

The complete three-field input is available in the generation's
`metadata.prompt_variables` and the generated curation artifact. Do not map the
whole compiled user message to `application`, or use only the baseline's rendered
context: both would lose the captured update. Keep source trace, decision observation
and session provenance. If an item was already curated, inspect it rather than adding
a duplicate. Freeze the final dataset version only after this review.

## Reviewed default cases

Dates use D, this deployment's grant effective date. Expectations are hand-worked
from the fictional EUR 6,000 grant / EUR 50,000 cap; no model output supplies truth.
All cases carry the same three-field contract, including ineligible controls.

| Case | Vehicle / price EUR | Line EUR | Date | Grant EUR | Principal EUR | Decision |
|---|---|---:|---|---:|---:|---|
| Eligible flagship | BEV / 45,000 | 40,000 | D | 6,000 | 39,000 | approve |
| Before date | BEV / 45,000 | 40,000 | D−1 | 0 | 45,000 | reject |
| PHEV control | PHEV / 45,000 | 40,000 | D | 0 | 45,000 | reject |
| Above cap | BEV / 50,001 | 40,000 | D | 0 | 50,001 | reject |
| Grant still above line | BEV / 49,000 | 40,000 | D | 6,000 | 43,000 | reject |
| Exact cap, date and line | BEV / 50,000 | 44,000 | D | 6,000 | 44,000 | approve |
| Eligible already affordable | BEV / 39,000 | 40,000 | D | 6,000 | 33,000 | approve |
| Ineligible affordable | ICE / 35,000 | 40,000 | D | 0 | 35,000 | approve |

For overridden policies, review the generated artifact instead of this default table.
The deterministic evaluator checks all five fields: list price, grant, principal,
approved line and decision. Baseline rejection labels can match while amounts fail.
Native experiments test context assembly and decisions over captured retrieval;
they do not measure retrieval-algorithm quality. Keep system/model/schema settings
and the frozen dataset version identical. Repeat the flagship Playground comparison
five times per version during rehearsal and retain every outcome.

## SDK / Companion fallback

The existing presenter tools and `synth experiment --label production` /
`--label development` still use the hosted regression dataset. Both legacy bare
application inputs and the new wrapper are accepted; expected outputs remain objects.
For the small cohort from the CLI, set
`--set golden_path.dataset.name=ev-grant-disputed-rejections-demo`.
The offline `--gate` path accepts the wrapper as well.

## Historical Cloud verification — superseded story

The record below describes the earlier instruction-based demo. It is retained as
prior evidence only and does not verify the missing-binding repair, eight-case
cohort, new evaluator or Halo workflow. Current released-image evidence is linked above. The [earlier 19 October native record](evidence/359-native-ui/README.md) remains the development rehearsal, with its own projects and retained failures.

### Prior record

Rehearsed on 2026-09-10 in Langfuse Cloud v4.33.0, project
[new-ev-demo](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp).
The project's Anthropic connection passed a Playground smoke request with
`claude-sonnet-4-6` (response: `OK.`). The seed uploaded 100 deterministic,
model-free traces, registered `credit_decision` versions 1 and 2, retained the
24-item regression dataset, and created the 11-item demonstration cohort.

The reserved observation was curated through **Add to datasets**, making 12 demo
items. Its raw chat-message input initially failed hosted schema validation;
the exact user-message content mapped to `application` passed. The expectation was
reviewed against the fictional policy: EUR 40,000 BEV price, EUR 6,000 grant,
EUR 34,000 financed principal, EUR 38,500 line, decision `approve`.
API verification confirmed the input remained a string, the expected output an
object, and the scenario/basis metadata and both source IDs were retained.

- [Curated item](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/datasets/cmtvqkwdv015nad0dfnit60qm/items/483c6fdf-dc3e-45f8-b2b3-1f1a3d7633ff)
- [Source decision observation](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/traces/bc4afcbe0e4090193a387b52af8d8229?observation=e6ac976ced90f67b)

The actual native experiment wizard exposed **Dataset Version (Optional)** and
reported `application: 12 / 12`. Both initial runs pinned
`2026-09-10T16:26:15.856Z`, confirmed through experiment metadata. The UI displayed
the local 18:26 time with an `(UTC)` label; use the API timestamp in recorded evidence.
Both used Anthropic / Sonnet 4.6, temperature 0, max tokens 512, with structured
output disabled. The generated user message matched the stored application string
byte-for-byte for all 24 executions. No Companion or terminal trigger was used.

| Initial native run | Items / API errors | Decision + numeric fields | Format |
|---|---:|---|---|
| [v1](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/experiments/results?baseline=cmtvqtv8e01c3ad0f1567evze) | 12 / 0 | 4/12 fully match; 6/12 decision labels match | All 12 wrapped in Markdown fences |
| [v2](https://cloud.langfuse.com/project/cmtvq2l5x00u8ad0d7rpc0uvp/experiments/results?baseline=cmtvqx0za01c1ad0dpecjjt61) | 12 / 0 | 11/12 unambiguous matches | 11 single fenced objects; one conflicting two-object response |

These are independent API comparisons against the reviewed expectations, excluding
free-text reason wording, not hosted evaluator scores. The one ambiguous candidate
was the EUR 35,999 line / EUR 36,000 principal case: it first emitted `approve`, then
corrected itself to `reject`. It is counted as a failure, not silently repaired.

The 12-item snapshot (IDs, status, input, expectation, metadata and source links)
was identical before and after both runs. Canonical JSON SHA-256:
`1fa2d91f46eff4274e14f580a5c87930a240d089b55f489375cf0f514459968a`.

The initial unstructured failures remain part of the evidence. On 11 September,
the `ev_credit_decision` schema was saved and native reruns scored all 12 outputs:
baseline v1 had 4 passes / 8 policy failures, and v2 had 12 passes. The live
Companion still reproduced an over-limit approval, so the release candidate moves
the output's `decision` after the amounts and explanation. That revised prompt
(numeric v3 in the rehearsal project) also passed all 12 native checks and the
fresh live approval/rejection checks. See the [release rehearsal record](ev-ui-release.md)
for exact versions, settings, links, remaining delivery gates and reset guidance.
