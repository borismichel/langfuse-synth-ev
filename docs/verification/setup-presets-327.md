# Setup presets (Depot #327)

Candidate evidence, 14 October 2026. The release candidate is EV 0.7.1 on published core v4.3.0. Signed image publication remains pending. This record is offline evidence only; no live readback or production catalog update was performed.

## Presentation defaults

The released `usecase.yaml` declares `config_schema.properties.generation.target_traces.default: 800`. Before this change both Depot forms send schema defaults for every declared operator field (`DeployWizard` seeds `defaultConfigValue(schema)`; `ManagedProjectForm` uses saved/draft values or `defaultConfigValue(schema)`) independently of host. Presentation therefore preserves the existing effective operator value 800 on Cloud EU, Cloud US and self-hosted. `config/demo.yaml`'s internal `generation.total_traces: 4000` is distinct from the released operator default: the declared target override is applied by the kit's existing derivation hook. Explicit `setup.host_defaults` removes that ambiguity.

An exploratory 4000-trace, 14-day run failed the existing `disagreement_drift` verifier (baseline0.01, drift0.15; required drift>0.2). This is an existing supported Custom-volume limitation, not a reason to weaken the verifier or rewrite cohorts. No verifier or scenario generation code changes are made by this preset slice.

## Authored rehearsal

Quick rehearsal declares only `generation.target_traces: 300`. This is the kit's existing documented golden-gate walkthrough volume, not a percentage or schema minimum. It retains the fixed24-item policy dataset, three reserved curation examples, disputed decisions, prompt linkage, chat inputs and score contrasts. History, generation seed and incident choices are retained when switching into rehearsal. All three incident controls remain visible. Enabled ambient incidents are sampled; the existing golden documentation (`tests/test_determinism.py`, golden-gate boundary, and `VERIFICATION.md`) explicitly does not guarantee a rare error burst at this volume. Scenario control descriptions state that they enable sampling and low trace counts may produce no incident.

## Executed checks

`tests/test_setup_presets.py` runs the real model-free seed generation, all six existing `run_verify` checks through the core read transport against the emitted events, and delivered artifact checks at Presentation800 and rehearsal300 for both14-day and30-day schedules. It checks explicit Cloud/self-hosted Presentation inputs, dataset count24, reserved count3, prompt-v1 linkage, decision chat input, elevated disagreement and green quality, plus all Manifest artifacts and curation payload. It does not claim remote ingestion, live evaluator execution or presenter rehearsal.

Dedicated candidate environment: `/private/tmp/depot-327-kit-env`, local editable core/kit candidates; production credentials and shared runtime environments untouched. Langfuse authoring guidance read at `/Users/bmichel/.agents/skills/author-langfuse-demo-kit/dependencies/langfuse/SKILL.md`; no changes to native surfaces, evaluators or instrumentation were made.

## Release candidate verification

All three dependency pins and the publish-workflow pin were updated with `synth-authoring repin v4.3.0`. The annotated core tag resolves to commit `ba4a4a276079ed49865becffc7955acde148147a`. A fresh isolated install used that published tag, EV 0.7.1 and the existing SDK-v4 dependency range (resolved Langfuse 4.18.0).

The full suite passes: **154 passed**, including byte-identical deterministic Spool, date-window boundaries, actual generated-range artifact, authored rehearsal readback, and Companion UI goldens. The first release run identified an existing exact-description assertion still containing the removed promotional copy; its expected wording now matches the approved factual Manifest description. Numeric bounds/default assertions are unchanged.

Manifest validation passes. The repository's `conformance --advisory` CI gate passes with its two existing migration advisories: Companion health path `/` and legacy app-factory location. The aggregate `synth-authoring check` reports `local_ready: false` because it runs strict conformance; its validation and test stages pass. Those unchanged migration items are not reported as resolved by this schedule/preset release. The two existing runbook developer-mode advisories also remain. No new Companion migration or live verification is included.

## Review correction: sparse selected-day activity

The Spec review found a valid Custom configuration whose weighted traffic missed
the selected day: target 100, seed 10, history 30, Data as of 2026-10-18 (Sunday).
The regression was reproduced through `run_seed(dry_run=True, persist=False,
do_import=False)` and actual emitted Spool timestamps before changing generation.
Its latest observation ended at 2026-10-17T19:38:32.125087Z.

When both ambient sampling and the fixed golden cohort miss the selected date,
generation now moves the latest ambient request to that date, keeping its sampled
time of day. The normal trace builder materializes its whole graph and the existing
end-boundary policy still applies. No trace is added, no cohort is resized, and no
verifier threshold or score policy changes. Application dates follow the moved
request; sessions are assigned after the timestamp is selected.

The corrected reproduction's reported range is 2026-09-20T13:42:40.039Z through
2026-10-18T16:19:05.847Z. Before and after contain 100 traces and 1159 Spool records.
Only trace `7868aae3ad34d1144dc88e0d8bb395c6` changes: its 10 observations and one
score timestamp move exactly one day. Graph IDs, parent relationships, durations,
decisions, score values and fixed golden records are unchanged. Propagated
application dates and completion timestamps move with the graph.

The public seed/Spool regression covers 18 sparse configurations: seeds 0/10/42,
14/30-day histories, and Friday/Saturday/Sunday end dates. It verifies the selected
day has a root observation, all observation endpoints stay in the inclusive window,
the actual generated range ends on that date, volume remains 100, and the 24-item
dataset and three reserved examples remain present. Existing presentation boundary,
midnight-overflow, authored-preset verifier and byte-for-byte golden tests pass.
Full result: **172 passed**, using published core v4.3.0 and Langfuse 4.18.0.
Manifest validation and advisory conformance pass with the unchanged advisories above.
No golden refresh, remote import, provider request or new live-verification claim
was needed for this calendar-policy correction.

Authoring guidance was re-read from the same linked Langfuse skill noted above;
the current [observability data model](https://langfuse.com/docs/observability/data-model)
was checked on 2026-10-14. This change preserves the existing trace/observation
relationships and transport rather than choosing a new native surface.
