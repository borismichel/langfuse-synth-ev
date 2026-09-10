# Native EV prompt experiments — portal #234

The hosted regression dataset keeps its configured name and all 24 default cases.
Seeding additionally creates `<dataset-name>-demo` with 11 authored policy cases.
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

Keep provider, model, sampling settings and output schema identical across both runs.
Use the deployment task model when that model is available through the connection;
otherwise record the deliberate alternative. Use temperature 0 when supported, and
512 output tokens. If the provider/model does not support a sampling parameter, omit
it in both runs. Select fixed numeric prompt versions, rather than a label someone
might move during the comparison. Both stored versions need only `application`;
the grant date in v2 has already been resolved during registration.

Check the actual experiment form for a **Dataset Version** selector. If present,
record and reuse the same timestamp. If absent, finish curation first and keep the
cohort unchanged until both runs finish: no seeding, adding, editing, archiving or
deleting items. Record item IDs, inputs and expected outputs before and after.
The documentation currently differs on UI version selection, so an Items-tab version
history alone is not evidence that experiment setup supports pinning.
[Dataset versioning](https://langfuse.com/docs/evaluation/experiments/datasets#versioning)

## Input contract and reserved observation curation

Each item input is an object containing exactly one key, `application`, whose value
is a JSON **string**. It contains `applicant_id`, `approved_line_eur`, `vehicle` and
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

For one of the reserved trace IDs in the artifact:

1. Open its **decision** observation and use **Add to dataset**. This retains the
   source trace and observation links. Choose the demo cohort for a short rehearsal,
   or the full regression dataset for the complete run.
2. The decision input is chat messages: the user message at `input[1].content`
   contains the application JSON string. Map that value to the new object's
   `application` field. Check the preview against the artifact's `input`. If the
   editor cannot build that object, paste the artifact's complete input object into
   the add-item editor while retaining the source observation link.
3. Paste the artifact's `expected_output` and `metadata`. Review its arithmetic:
   BEV, date on/after the effective date, price at/below the cap; deduct the grant,
   then approve only if principal is at/below the line. Record the reviewer's name
   and date in metadata. Never use the observation's rejection as ground truth.
4. Save and reopen the item. Verify the application string, structured expectation,
   scenario metadata, and clickable source observation before launching either run.

The authored cohort has fixture provenance, not fabricated observation IDs. The
reserved item is the observation-linked addition used to demonstrate curation.
[Observation mapping](https://langfuse.com/docs/evaluation/experiments/datasets#batch-add-observations-to-datasets)

## Execute and compare inside Langfuse

Open the chosen dataset's **Experiments → Run experiment → via User Interface → Configure**. Select
`credit_decision`'s baseline numeric version and the verified connection/settings.
Preview a compiled item: there must be no unresolved `{{application}}`. Start the
baseline, then repeat with the candidate version and the same frozen dataset/settings.
No terminal or Companion trigger is involved in either native execution.
Compare generated outputs side by side, including all numeric Decision fields;
matching approve/reject alone does not prove grant correctness.

Enable **Structured output** with a Decision JSON schema for both runs. Require
`decision` (enum `approve`, `reject`), integer `list_price_eur`, `applied_grant_eur`,
`financed_principal_eur`, `approved_line_eur`, and string `reason`; disallow additional
properties. Saving a reusable schema makes it available to all project members.
Prompt instructions alone did not guarantee JSON-only responses in the Cloud rehearsal:
Sonnet 4.6 added Markdown fences and one response contained two conflicting decisions.
[Native experiment workflow](https://langfuse.com/docs/evaluation/experiments/experiments-via-ui)

For the default fictional EUR 6,000 grant, EUR 50,000 cap (D = effective date), the
independently worked cohort is:

| Scenario | Vehicle / price | Line | Date | Grant | Principal | Decision |
|---|---|---:|---|---:|---:|---|
| False negative | BEV / 42,000 | 40,000 | D | 6,000 | 36,000 | approve |
| Still above line | BEV / 48,000 | 40,000 | D | 6,000 | 42,000 | reject |
| At cap | BEV / 50,000 | 44,000 | D | 6,000 | 44,000 | approve |
| Above cap | BEV / 50,001 | 49,000 | D | 0 | 50,001 | reject |
| PHEV control | PHEV / 42,000 | 40,000 | D | 0 | 42,000 | reject |
| ICE control | ICE / 42,000 | 42,000 | D | 0 | 42,000 | approve |
| Before date | BEV / 42,000 | 40,000 | D−1 | 0 | 42,000 | reject |
| On date / equal line | BEV / 42,000 | 36,000 | D | 6,000 | 36,000 | approve |
| After date / below line | BEV / 42,000 | 35,999 | D+1 | 6,000 | 36,000 | reject |
| Below cap | BEV / 49,999 | 44,000 | D | 6,000 | 43,999 | approve |
| Above line | BEV / 42,000 | 36,001 | D | 6,000 | 36,000 | approve |

For overridden policy values use the generated artifact, not this default table.
Baselines can reject correctly yet report the wrong grant/principal (the still-above-line
case is intentional). The Companion's immediate verdict compares decision labels;
review amounts separately in Langfuse. The candidate must not approve every BEV.

## SDK / Companion fallback

The existing presenter tools and `synth experiment --label production` /
`--label development` still use the hosted regression dataset. Both legacy bare
application inputs and the new wrapper are accepted; expected outputs remain objects.
For the small cohort from the CLI, set
`--set golden_path.dataset.name=ev-grant-disputed-rejections-demo`.
The offline `--gate` path accepts the wrapper as well.

## Cloud verification record

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

Schema-enforced reruns are pending approval to save the prepared shared
`ev_credit_decision` schema. The initial native workflow, mapping, pinned version,
source-linked curation and actual outputs are verified; strict candidate output
acceptance is not yet complete.
