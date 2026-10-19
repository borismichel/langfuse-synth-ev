# Missing policy context implementation

The baseline and candidate share system instructions, model settings and the response
schema. Both compile the same `application`, `handbook`, `policy_updates` dictionary.
Only the candidate binds the last variable. The policy documents are bundled in
`src/synth/fixtures/policy.json`; their publication/effective dates are offsets from
the existing deployment policy anchor. `policy_updates="[]"` is valid.

Live submissions execute the bundled lookup before compilation and execute the model
inside its generation observation. The live graph contains the request root,
`credit_agent`, `retrieve_policy`, and `decision`. Retrieval contains the actual
handbook and amendment; generation input contains the compiled messages. Its metadata
retains all three input variables for Playground replay and dataset curation. Usage
and model identifier come from the actual provider client. Validation preserves raw
failed output on the generation and rejects incomplete or contradictory decisions.
There are no fabricated live extraction, eligibility, affordability or explanation calls.
Historical auxiliary observations remain synthetic; the historical decision and
retrieval use the same prompt/lookup contract as live execution.

The deliberate golden update preserves scenario IDs, policy-window decisions,
disputes and quality signals. Changed bytes represent the new policy documents,
compiled messages, prompt-variable metadata and corresponding sampled token floors.
The old `ignored_by_agent` diagnosis is removed. The Spool remains model-free.

## Evidence

- `accepted-simulation/`: the accepted fourth author-time experiment, copied from
  its original 2026-10-19 run. It includes the exact prompt templates, captured inputs,
  schema, manifest, all 38 responses and summary. These static dates belong to the
  historical experiment, not runtime fixture generation. Baseline failed all five
  flagship repetitions; candidate passed five flagship and fourteen control calls.
  This is direct-provider evidence, not a completed Langfuse UI rehearsal.
- Behavioral tests cover complete prompt context, the single-binding difference,
  strict response validation, actual live operation ordering, seed/live context,
  production-label promotion without prompt-cache delay, deployment anchors, and
  the installed Langfuse SDK's exported observations.
- 170 tests passed locally, including the deterministic Spool golden gate.
- The shared provider seam needs the coordinated `response_schema` core change;
  this kit adds no provider transport. Compatible core pin and native UI/provider
  rehearsal are integration/release checks, not established by fake-provider tests.

## Product guidance

Read on 2026-10-19:

- https://langfuse.com/docs/prompt-management/get-started
- https://langfuse.com/docs/prompt-management/features/config
- https://langfuse.com/docs/observability/features/observation-types

Applied the linked Langfuse skill at
`author-langfuse-demo-kit/dependencies/langfuse/SKILL.md`, SHA-256
`e8908ea1c924374ba7bc5e82b220709d107db6a3450a0c4d72228a91a2a7534a`.

## Pending delivered checks

Repeated provider calls through the new shared-core path; Playground replay;
native Experiments; integrated-assistant investigation and dataset curation;
promotion followed by a fresh Companion request; live readback; release/admission.
Tickets 358 and 359 own the remaining workflow and delivery evidence.

Offline authoring result: manifest validation and all 170 tests passed. Conformance
remains failed on two pre-existing target-shape findings: `health_path: /` collides
with the index, and the required `synth.companion.app:create_app` factory is absent.
Running conformance against unchanged integration base `2bb5046` confirmed the same
findings. Consequently `local_ready` is false; this implementation does not claim
full offline readiness or erase that migration debt.

## Native diagnosis correction

The first native Halo investigation correctly identified an additional inconsistency
in the synthetic history: `check_subsidy_eligibility` returned a grant, but the later
`compute_affordability` fixture copied the baseline decision's gross principal.
That made the first wrong step appear before prompt assembly and weakened the claim
that binding the missing variable alone repairs the demonstrated defect.

The historical affordability fixture now consumes the grants from the eligibility
result and calculates net principal independently of the baseline decision. For the
EUR 45,000 / EUR 40,000 flagship, it records EUR 39,000 and `within_line=true`, while
the baseline generation still receives no bulletin and rejects EUR 45,000. The
first divergence is therefore the decision's missing policy context. Tests include
an exact-line approval, still-unaffordable net principal, above-cap BEV, PHEV, ICE,
pre-effective applications and a future effective date. Live operations are unchanged.

The deliberate re-freeze preserves all 3,344 golden records and changes only the
300 `compute_affordability` observations: their correct policy-derived values and
explicit `execution=generated_history` metadata. No seeded project was changed or
re-imported; final native diagnosis must be rehearsed on a fresh target. The first
native investigation remains evidence of the defect found, not final acceptance.

## Provider SDK observation correction

Actual Companion readback found that Anthropic SDK 1.15 emitted an automatic
`anthropic.messages.create` child under the manually recorded decision. Both
observations carried the same 664 input / 96 output tokens, duplicating usage and
cost. The manual generation remains the authoritative decision observation because
it includes the managed prompt association, exact input, validation and outcome.

Both EV manual wrappers now request `provider_tracing=False` through the shared
completion client. Core uses the provider's public client-copy option for that
call; it does not change global tracing or filter unrelated observations. This
follows the [Anthropic SDK telemetry guidance](https://platform.claude.com/docs/en/manage-claude/opentelemetry/sdk)
for SDK calls already traced by another library. The shared-core option defaults
to the previous behavior for other callers and preserves older SDK compatibility.

The regression test executes the real Anthropic SDK with a local HTTP fixture and
the real Langfuse exporter. It first reproduced the fifth span, then verified the
correct four-observation graph, one usage record and the prompt link. A subsequent
standalone call on the original SDK client still exports its automatic span,
proving tracing was disabled only for the manually instrumented request. Updated
live readback remains a separate check; no historical fixture/golden changed.
