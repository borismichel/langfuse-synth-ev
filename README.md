# EV Subsidy Silent Regression

A Demo Depot package with deterministic historical traces, a generated Presenter Runbook and a live loan-application Companion. Deploy it from the catalog into a fresh demo Langfuse project; the Presenter Runbook contains the complete UI journey and setup inputs.

## Business case

A lender retrieves its vehicle handbook and a purchase-grant amendment. The baseline prompt template binds the application and handbook but omits the retrieved `policy_updates`. The model therefore assesses the gross purchase price. Eligible customers can be rejected even though the answers are well formatted. The candidate adds the missing binding; the system prompt, retrieved input, model and response schema stay the same.

For the default fictional policy, a BEV costing €45,000 qualifies for a €6,000 grant on or after the deployment's effective date. Its €39,000 principal fits a €40,000 credit line. The baseline rejects at €45,000; the candidate can approve at €39,000. Eligibility and arithmetic must also hold for rejection controls.

## Presenter journey

1. Inspect a disputed decision in Langfuse. Ask the integrated **Halo** assistant to investigate without supplying the diagnosis. Check its citations against the application, retrieved amendment, compiled generation input and managed prompt.
2. Create and test the native Boolean `policy_correctness` evaluator. It checks list price, grant, financed principal, credit line and decision; a correct rejection with wrong amounts fails.
3. Ask Halo to create a regression dataset and curate a reserved source case. Review the complete three-string input and policy-derived expected output before approving writes. Retain source observation and session links.
4. In **Playground**, compare fixed prompt versions with identical input, model, settings and structured output schema. The only template change adds `policy_updates`.
5. Run two native **Prompt Experiments** against the same frozen dataset version and explicitly select the evaluator. Compare monetary outputs and genuine rejection controls, not only decision labels.
6. Activate a scoped incoming-observation rule, verify a new undisputed baseline decision, promote the tested candidate once, and submit fresh eligible and rejection cases. Inspect the managed prompt version and automatic policy score in Langfuse.

The generated runbook has deployment-specific links, policy dates, reviewed inputs, evaluator source, response schema and production-rule recipe. Rehearse it before presenting; native execution, scores and assistant actions require a working target and project permissions. The direct-provider evidence below does not prove these UI beats.

## Package contents

- **Historical data:** configurable backdated traces, sessions, sampled synthetic quality/disagreement scores, baseline/candidate prompts, the regression dataset and an eight-case short cohort. Seed is deterministic and makes no model calls.
- **Presenter Runbook:** `DEMO_SCRIPT.md`, generated from saved deployment anchors. Changing local configuration later does not change its recorded policy or resource IDs.
- **Companion:** the loan form and cached `/analytics` report. Start it from the deployment page. Each successful submission performs a real bundled policy lookup and one real decision-model call.

The live trace has four observations: root `credit_agent.assess_application`, child AGENT `credit_agent`, and its `retrieve_policy` RETRIEVER and `decision` GENERATION children. The generation records exact compiled messages, all three input values in `metadata.prompt_variables`, schema and native prompt version. Historical fixtures also contain representative planner, tool and explanation operations; these are generated scenes, not live executions.

**Request a review** records `user_disagreement` against the decision-bearing agent observation. It does not start a human-review workflow. Live submissions and feedback do not rewrite the cached historical lending report. The production prompt is fetched per request with no cache; promotion affects later calls and preserves old evidence.

## Default reviewed cohort

D is this deployment's grant effective date. See the generated runbook for overridden amounts and dates.

| Case | Vehicle / price | Line | Date | Grant | Principal | Expected decision |
|---|---|---:|---|---:|---:|---|
| Flagship | BEV / €45,000 | €40,000 | D | €6,000 | €39,000 | approve |
| Before date | BEV / €45,000 | €40,000 | D−1 | €0 | €45,000 | reject |
| PHEV | PHEV / €45,000 | €40,000 | D | €0 | €45,000 | reject |
| Above cap | BEV / €50,001 | €40,000 | D | €0 | €50,001 | reject |
| Still above line | BEV / €49,000 | €40,000 | D | €6,000 | €43,000 | reject |
| Exact cap/date/line | BEV / €50,000 | €44,000 | D | €6,000 | €44,000 | approve |
| Already affordable | BEV / €39,000 | €40,000 | D | €6,000 | €33,000 | approve |
| Ineligible affordable | ICE / €35,000 | €40,000 | D | €0 | €35,000 | approve |

Each item contains `application`, `handbook` and `policy_updates` as JSON strings plus a structured expected Decision. Both prompt versions receive this same input. The candidate binds the third field; the baseline leaves it unused. Add a reserved source case only once and record the final count/version. Native experiments replay captured retrieval context; they do not execute the lookup or measure retrieval quality.

## Deploy and present

1. Select this package in Demo Depot and connect a fresh project whose name contains `demo`.
2. Review and confirm the deployment's cost estimate. The pipeline validates the target, generates/imports history, provisions assets and verifies the current run.
3. Open the generated Presenter Runbook and confirm project identity, prompt labels and policy dates. Select a working organization or project LLM connection in Langfuse. The Companion's injected key is separate.
4. Start the Companion and complete the native rehearsal. For a focused demonstration, disable the three ambient incident cohorts before the initial seed.
5. Use a fresh project for a reset. Re-seeding an occupied project appends observations and reasserts prompt labels; it does not reset existing data.

The Companion's **presenter tools** offers SDK fallback runs by `production` or `development` label. Their result is **decision agreement**, not the native five-field policy score. Labels can move; inspect the recorded version and result. A completed native comparison is the preferred rehearsal fallback.

## Verification and evidence

[Current verification status](docs/ev-context-verification.md) records the completed **v0.8.0** signed release, admission, catalog publication and ordinary Depot deployment. In one final Cloud **4.64.0** project, Halo identified the missing binding and curated the ninth case; five valid Playground pairs showed the contrast; native experiments scored **4/9 → 9/9**, with all 18 policy scores verified. Fresh live decisions showed baseline false, promoted eligible true and PHEV rejection true, each with one automatic agent score.

![Native experiment comparison from the released demo](https://raw.githubusercontent.com/borismichel/langfuse-synth-ev/caa03ff6b0432098f2e4f9036f2c93fcc14c01b2/docs/img/presenter-20261019/native-comparison.png)

[Fresh screenshots](docs/img/presenter-20261019/README.md) and the [complete delivery record](https://github.com/borismichel/langfuse-demo-depot/blob/b294cbe418eb03b5a66fbbbc6e6a8abe9d892aac/docs/release-evidence/ev-context-359/delivery/README.md) retain exact objects, settings and the two schema-setup failures. The [24-call direct-provider trial](docs/evidence/359-implemented-model/README.md) and [earlier native rehearsals](docs/evidence/359-native-ui/README.md) retain their separate scope. September evidence describes the superseded instruction-based story. The reference project is now on production v2; inspect its recorded baseline rather than moving the label back.

The [Full spec](langfuse-demo-synth-spec.md) defines the current contract. [Verification checks](VERIFICATION.md), [native experiments](docs/native-prompt-experiments.md), [policy evaluation](docs/policy-evaluation.md) and [fresh monitoring](docs/live-policy-verification.md) provide developer/reference detail; the main presenter path stays in the single runbook.

---

## Development and running outside the depot

Everything from here down is for **kit development** — the `synth` CLI, local
seeding, tests, and release plumbing. None of it is needed to deploy or present
the demo through the depot. (Running a kit standalone this way works today, but
it is the kit-dev loop, not a supported delivery method — see the
package delivery described above.)

This is the first scenario in the demo-data kit. It's a cloneable repo:
`git clone`, set `.env`, `synth seed`, run the demo. The full spec lives in
[`langfuse-demo-synth-spec.md`](langfuse-demo-synth-spec.md).

### Quick start

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. point at a DEMO/SANDBOX project (the guardrail refuses non-matching project names)
cp .env.example .env      # fill LANGFUSE_BASE_URL + keys; ANTHROPIC_API_KEY only needed for `experiment`

# 3. preview, then seed
synth plan     --config config/demo.yaml     # dry run: volumes, golden-path dates, dataset summary (no network)
synth seed     --config config/demo.yaml     # spool backdated data to disk → import, register prompts, build dataset, emit DEMO_SCRIPT.md
synth verify   --config config/demo.yaml     # query back through the read seam and assert the golden path

# 4. follow DEMO_SCRIPT.md for the live presentation; the experiment runs the *labelled* prompt:
synth experiment --config config/demo.yaml                     # current production version
synth experiment --config config/demo.yaml --label development  # current development version
# compare the recorded versions and actual results before promotion
```

`synth seed` writes **`DEMO_SCRIPT.md`** — the Presenter Runbook filled with *this run's real*
dates, trace IDs, figures and deep links. Re-seeding regenerates a matching script
(`synth script` regenerates it from existing run state). After seeding, confirm the data
matches the narrative with **[`VERIFICATION.md`](VERIFICATION.md)** (`synth verify` + live
coverage / drift / tag checks). If a large import stalls, the generated data is safe on disk
— retain it for diagnosis. Import is not resumable; use a fresh target before another import.

### Running the playground locally

```bash
pip install -e '.[playground]'
synth playground --config config/demo.yaml          # → http://127.0.0.1:8000
synth submit --config config/demo.yaml --prefab eligible --line 32000   # one-shot, from the terminal
```

`synth playground` serves the same configurator (FastAPI) the depot starts as the
Companion, including the `/analytics` report route.

### Architecture (why raw OTLP, and not the SDK)

The Langfuse SDK timestamps observations from the wall clock and offers no `start_time` — it
can't backfill history, and a Spool is by definition weeks of backdated history. So the seed
path builds wire objects directly: every observation is an **OTLP span** posted to
`POST /api/public/otel/v1/traces` with producer-supplied nanosecond timestamps and
producer-minted ids, and a trace *is* its root observation (v4 has no separate trace entity).
Scores stay `score-create` envelopes on `POST /api/public/ingestion` — the supported v4 path
for them, not a legacy call. Every write carries `x-langfuse-ingestion-version: 4`, without
which a v4 project files the data where no v4 query or dashboard can see it. Datasets,
prompts and experiments use the pinned Python SDK (separate API surfaces).

The write is **two-phase**: generation streams every wire object to an NDJSON **spool on
disk** first, then a separate pass **imports** it in chunks, so a wedged or slow upload can't
lose the (deterministic, expensive) generated data. The spool lives under `.synth_spool/`
(gitignored). That import is **not re-runnable** — see Guardrails & teardown.

**Cloud vs self-hosted** is a single URL-derived fact in [`target.py`](src/synth/target.py)
(`TargetProfile.detect`), kept out of every call site. The Spool's writer already retries,
but the hand-rolled REST helpers (the project guardrail, prompt-label PATCH,
score-config creation, and `synth verify`'s paginated query-backs) did single shots that
Langfuse Cloud rate-limits with 429s. The shared core's `langfuse_synth_core.http.request_retry`
is the one **Retry-After-aware** backoff they all share (moved to the lib in Ring 2, #33 — it
speaks the Langfuse REST machine, not the scenario), and on Cloud the one-at-a-time reads/writes
get a small `post_throttle_s` spacing so they don't trip the limiter to begin with
(self-hosted: zero overhead). `seed`, `experiment` and `verify` each log which target they hit.

```
config/demo.yaml ──▶ generator (deterministic plan)
                          │
        score configs ─▶ prompts (v1→production, v2→development) ─▶ spool→import traces+scores ─▶ dataset+items
                          │                                                │
                          └────────────── .synth_state.json ──────────────┘
                                                  │
                              DEMO_SCRIPT.md  ◀────┘   (synth script)

demo time:  synth experiment [--label production|development] ──▶ run_experiment(task = decide(item.input, label))  + explicitly configured policy evaluator
```

`decide(application, prompt_label) -> Decision` is the **single agent function** — seeding and
the experiment both route through it. At seed time the label selects the arithmetic (`"v1"`
missing update vs `"v2"` bound update); at demo time the experiment passes a **Langfuse label**
(`production` / `development`) that's resolved to the live prompt at runtime — so promoting v2
to `production` in the UI changes what the eval runs, no code change. See
[`src/synth/`](src/synth/) and the current Full spec.

### Repo layout

```
config/demo.yaml          # the run config (auditable; seed + this file determine everything)
prompts/credit_decision.v{1,2}.txt
src/synth/
  agent.py                # decide(application, prompt_label) -> Decision  ← the one lever
  config.py rng.py models.py pricing.py timegen.py distributions.py content.py
  target.py http.py       # Cloud-vs-self-hosted facts + Retry-After-aware REST helper
  seed/                   # ingest (spool+import), events, traces, sessions, scores, golden_path, prompts, datasets, run
  experiment/run.py       # run_experiment(label) → decide(i.input, label)  ← production | development
  verify.py script.py cli.py
templates/demo_script.md.j2
fixtures/golden_v1_decisions.json   # committed v1 outputs for offline provenance
tests/
```

### Configuration

All knobs are in [`config/demo.yaml`](config/demo.yaml): volume/window, population, the model
pricing table, the golden-path dates (grant effective offset, drift window), the dataset shape
(item count, eligible share, reserved count), ambient incidents, and scoring coverage. Change
the `seed` for a different-but-reproducible run.

### Guardrails & teardown

- The seeder **refuses to run** unless the target project's name contains `target.project_hint`
  (default `demo`). Point it only at demo/sandbox projects.
- **A re-seed is not a reset.** OTLP appends; it does not upsert. Re-seeding a project that
  already holds this demo tells the whole story twice, and `synth import-spool` refuses a
  second run over the same spool rather than silently doubling the volume — clear the
  project's Langfuse data and import from the top, or re-generate the spool. The old batch
  transport did upsert on a deterministic id; that property belonged to the transport, and it
  is gone (core `docs/WRITE_PATHS.md`).
- Prompt registration is still **idempotent on content** (no version churn — v1 stays version
  1), and the `production`→v1 / `development`→v2 labels are **re-asserted on every seed**, so
  the red→green flip always resets. Prompts are a separate API surface from the Spool.
- **Teardown is project-level**: spin up a fresh project and re-seed. A fresh project is also
  required to *change coverage* (which scores get emitted) — ingestion never deletes, so
  dropped scores would otherwise linger as orphans.

### CI/CD regression gate (optional)

`synth experiment --gate 0.95` computes an offline PASS-rate of v2 over the hosted dataset (no
model call) and exits non-zero below the threshold — drop it in a pipeline as a regression gate.

### Tests

```bash
pip install pytest && pytest -q     # determinism, the policy arithmetic, golden-path invariants
```

### Image releases

Pushing a `vX.Y.Z` tag triggers `.github/workflows/publish.yml`, which builds this
kit's image, pushes it to `ghcr.io/borismichel/langfuse-synth-ev`, and cosign-signs it
keylessly (Spec E · E7, #102). See
[`langfuse-synth-core`'s `docs/CI_SIGNING.md`](https://github.com/borismichel/langfuse-synth-core/blob/main/docs/CI_SIGNING.md)
for the full contract — image naming, cadence, runner, and the signing-identity policy
the portal's verification gate checks against.

### Native prompt experiments

Seeding also creates `<dataset-name>-demo`, an eight-item policy cohort, and exports
`NATIVE_EXPERIMENT_ITEMS.json` as a deployment artifact. Both hosted datasets map
`application`, `handbook` and `policy_updates` to the same string values as the live caller. Follow the
[native experiment runbook](docs/native-prompt-experiments.md) to check the project
LLM Connection, curate a reserved observation, and compare the two prompt versions
in Langfuse. The SDK and Companion experiment routes remain available.
