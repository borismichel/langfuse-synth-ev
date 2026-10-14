# Setup presets (Depot #327)

Candidate evidence, 14 October 2026. Release, signed image, live readback and Depot admission remain pending the coordinated core/EV release. This record is offline evidence only.

## Presentation defaults

The released `usecase.yaml` declares `config_schema.properties.generation.target_traces.default: 800`. Before this change both Depot forms send schema defaults for every declared operator field (`DeployWizard` seeds `defaultConfigValue(schema)`; `ManagedProjectForm` uses saved/draft values or `defaultConfigValue(schema)`) independently of host. Presentation therefore preserves the existing effective operator value 800 on Cloud EU, Cloud US and self-hosted. `config/demo.yaml`'s internal `generation.total_traces: 4000` is distinct from the released operator default: the declared target override is applied by the kit's existing derivation hook. Explicit `setup.host_defaults` removes that ambiguity.

An exploratory 4000-trace, 14-day run failed the existing `disagreement_drift` verifier (baseline0.01, drift0.15; required drift>0.2). This is an existing supported Custom-volume limitation, not a reason to weaken the verifier or rewrite cohorts. No verifier or scenario generation code changes are made by this preset slice.

## Authored rehearsal

Quick rehearsal declares only `generation.target_traces: 300`. This is the kit's existing documented golden-gate walkthrough volume, not a percentage or schema minimum. It retains the fixed24-item policy dataset, three reserved curation examples, disputed decisions, prompt linkage, chat inputs and score contrasts. History, generation seed and incident choices are retained when switching into rehearsal. All three incident controls remain visible. Enabled ambient incidents are sampled; the existing golden documentation explicitly does not guarantee a rare error burst at this volume.

## Executed checks

`tests/test_setup_presets.py` runs the real model-free seed generation, all six existing `run_verify` checks through the core read transport against the emitted events, and delivered artifact checks at Presentation800 and rehearsal300 for both14-day and30-day schedules. It checks explicit Cloud/self-hosted Presentation inputs, dataset count24, reserved count3, prompt-v1 linkage, decision chat input, elevated disagreement and green quality, plus all Manifest artifacts and curation payload. It does not claim remote ingestion, live evaluator execution or presenter rehearsal.

Dedicated candidate environment: `/private/tmp/depot-327-kit-env`, local editable core/kit candidates; production credentials and shared runtime environments untouched. Langfuse authoring guidance read at `/Users/bmichel/.agents/skills/author-langfuse-demo-kit/dependencies/langfuse/SKILL.md`; no changes to native surfaces, evaluators or instrumentation were made.
