# Decision metadata contract

Status, 4 November 2026: implementation prepared for **0.8.2**, not released or
deployed. Keep the locally patched companions running through the recording.
This implements the format and release preparation for Depot issue #389; the
issue remains open until the released-image readback and rollout gates below pass.

## Persisted shape

Historical seeds, Companion decisions and SDK experiments share this contract on
the **decision generation**, independent of the prompt version used by the agent:

| Metadata path | Value returned by a full observation read |
| --- | --- |
| `$.prompt_variables` | Object |
| `$.prompt_variables.application` | JSON string encoding the application object |
| `$.prompt_variables.handbook` | JSON string encoding the handbook document |
| `$.prompt_variables.policy_updates` | JSON string encoding the array of published policy documents |
| `$.response_schema` | Object containing the decision JSON Schema |

These are the existing historical paths and value types. Do not change them to
literal dotted keys or silently switch the three prompt-variable values to objects.
An explicit string `"[]"` for policy updates means the lookup found no published
updates for that application. A missing field, `null`, blank value or malformed
JSON is missing evidence, **not** an empty policy list. The readback gate rejects it.

The shared `decision_metadata()` serializer is used by the historical trace
builder, `emit_live_trace()` and the live path of `decide()`. It serializes only
the two structured evidence fields. Existing execution metadata, observation
hierarchy, prompt messages, model parameters, outputs and scores keep their current
behavior. There is no SDK monkey patch or global tracing customization.

## Why serialization differs from a nested Python dictionary

The [Langfuse metadata documentation](https://langfuse.com/docs/observability/features/metadata)
describes nested-object flattening with Python SDK v5 and server 4.59.0+.
The pinned [Python SDK 5.0.1 implementation](https://github.com/langfuse/langfuse-python/blob/v5.0.1/langfuse/_client/attributes.py#L164)
JSON-encodes every metadata value, including strings. The server decodes that layer
once before flattening objects. Sending a JSON string through the public metadata
API therefore preserves it as one leaf; sending a dictionary flattens its children.

| Producer | Value supplied to emitter | Exported OTLP value | After ingestion |
| --- | --- | --- | --- |
| Raw historical OTLP | JSON string | Same JSON string | JSON string leaf |
| SDK 5.0.1 | Same JSON string | SDK JSON-encodes the string | Same JSON string leaf |

Langfuse's full metadata read returns the outer JSON object from that leaf, while
the inner prompt variables retain their historical JSON-string types. This is
verified against Cloud 4.75.0. Keep SDK 5.0.1 pinned until this gate is rerun against
any proposed SDK/server upgrade; this is not a claim that all future ingestion
versions preserve the behavior.

The raw writer is `langfuse_synth_core.seed.otlp._json_value()` / `_metadata_attrs()`
in core 5.1.1: strings pass through; structured values use compact JSON. The shared
serializer uses that compact format, so the existing full historical spool golden
passes without a rebaseline. The earlier local patch on core 5.0.0 used the same
mechanism with insignificant JSON whitespace.

## Policy evidence and prompt selection

The companion looks up the handbook and policy updates separately, then attaches
all three variables to the decision even when prompt v1 omits the update binding.
The judge can therefore inspect the policy the agent failed to include. SDK
experiments preserve captured dataset variables when supplied; application-only
inputs use the existing policy lookup. This change does not replace captured
policy text or rewrite effective dates.

`submit()` already fetches `credit_decision` with `label="production"`,
`cache_ttl_seconds=0` and no `version`. SDK experiment calls also fetch their
requested label without caching or pinning. No prompt-fetch change is needed.
A recorded v1 is valid if production pointed at v1 at the time of that call.
Existing promotion tests cover the next submission switching from v1 to v2.

## Existing-data compatibility

| Existing data | Treatment |
| --- | --- |
| Historical nested metadata | Preserve; selectors keep working |
| Locally patched companion metadata | Preserve; same parsed contract |
| Live traces written with literal dotted keys before the patch | Retain as legacy; this producer fix does not repair those observations |

No migration runs on startup or deployment. Do not reseed an occupied project,
re-import old OTLP, delete history, copy old scores to new observations, or remap
evaluators as part of this change. The ordinary rollout replaces only the companion
image while retaining the deployment's stored policy state and project settings.

If old dotted-key observations must later be re-evaluated, first produce a read-only
inventory by project and observation ID. Agree a separate, explicit migration or
legacy-evaluator run, including score provenance and validation, before making any
writes. They must not be treated as newly compatible merely because a new companion
has been deployed. Existing nested history needs no migration.

## Verification

Offline checks use the actual pinned SDK and raw OTLP writer. Only external model
responses and HTTP prompt reads are controlled:

```sh
pytest -q tests/test_companion_metadata_compatibility.py tests/test_metadata_readback.py tests/test_live_emission.py
pytest -q tests/test_determinism.py::test_full_payload_golden_is_byte_identical
```

The SDK export cases cover companion and experiment calls, both prompt versions,
and applications before/after bulletin publication. They require identical stored
JSON leaves, independent policy evidence, an explicit empty list when appropriate,
and the recorded prompt version. The golden gate independently protects existing
historical bytes. The readback checker rejects dotted, absent, null, malformed and
truncated evidence; it does not normalize those errors away.

For actual persisted observations, use the supported Langfuse CLI with credentials
already in the environment. Export exactly one decision per file and expand both
metadata fields (the API otherwise truncates large values):

```sh
langfuse api observations list --trace-id "$HISTORICAL_TRACE_ID" --name decision \
  --fields core,basic,metadata,prompt --expand-metadata prompt_variables,response_schema \
  --json > historical.json
langfuse api observations list --trace-id "$COMPANION_TRACE_ID" --name decision \
  --fields core,basic,metadata,prompt --expand-metadata prompt_variables,response_schema \
  --json > companion.json
langfuse api observations list --trace-id "$EXPERIMENT_TRACE_ID" --name decision \
  --fields core,basic,metadata,prompt --expand-metadata prompt_variables,response_schema \
  --json > experiment.json
python -m synth.verify_metadata historical.json companion.json experiment.json
```

The checker is read-only and needs no credentials. It validates the exports and
prints IDs, prompt versions and policy-update counts, without printing policy text
or connection metadata. It does not invoke an evaluator or claim to verify a score.
Keep raw exports local; do not publish credentials or project-specific evidence.

On 4 November, read-only checks passed for six existing observations (one historical
and one locally patched companion decision in each of the three demo projects).
The original failing live trace was rejected for literal dotted keys. Those receipts
verify the compatibility mechanism on Cloud 4.75.0 / SDK 5.0.1; they are **not** a
new released-image or SDK-experiment persistence rehearsal. Private project IDs and
trace links remain in the Depot issue's local recovery receipts.

## Release and deployment after the recording

1. Review and merge the implementation, run the full suite and existing contract
   conformance check. No tag, registry publication or companion replacement occurs
   as part of implementation preparation.
2. After the recording, tag the reviewed `0.8.2` commit as `v0.8.2`. The existing
   GitHub Publish workflow builds, pushes and signs the ordinary companion image.
   Check the immutable digest and source revision; do not reuse a locally patched
   container as the published image.
3. In an isolated rehearsal target, run that image to produce new historical,
   companion and SDK-experiment decisions. Read them back with the commands above,
   check v1/v2 evidence and the explicit-empty case, and compare the companion's
   recorded version with `get_prompt(label="production")` at submission time.
   A deliberately mismatched historical date must retain its own policy evidence.
4. Verify the existing evaluator's variable preview sees all three nested values
   and a fresh eligible wrongful rejection is scored correctly. An absent score
   with a disabled/unassigned rule is not evidence of metadata failure; do not
   silently enable or modify the rule.
5. Replace each companion through the supported companion-only deployment flow,
   retaining its project and policy state. Do not run the seed pipeline. Confirm
   the new digest, four live observations, nested metadata, current production
   prompt version and expected automatic score in each target. Repeat after a
   companion recreation: the fix must come from the image, not a writable layer.
6. Keep #389 open until these gates pass. Rollback is an image replacement with no
   data migration; the original unpatched image reproduces the metadata bug, so
   retain the current patched companions until the candidate has passed rehearsal.
