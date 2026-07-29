# EV Subsidy Silent Regression

A **Demo Depot cartridge**: this repo is a complete Demo Package that the depot
deploys **as-is** from its catalog, landing the Run-Triad — the Spool, the
Presenter Runbook, and a live Companion. An operator picks it in the portal, points it at a demo Langfuse project
(Cloud or self-hosted), and gets a fully seeded, presentable environment. Nothing
on this page needs installing to *run* the demo; everything developer-facing lives
at the bottom, under
[Development and running outside the depot](#development-and-running-outside-the-depot).

**The story in one line:**

> trace → detect a silent failure → build an evaluator → curate a dataset → fix via prompt management → prove the fix with an experiment.

## The business case & story arc
 
**The business.** A consumer lender approves auto-loan applications with an AI credit-approval agent: it retrieves policy, checks subsidy eligibility, computes affordability against the customer's credit line, and returns an approve/reject decision with a customer-facing rationale. Thousands of decisions a day ride on it, so its outputs are monitored for the things that usually go wrong with an LLM: quality, tone and format.
 
**The tension.** A new EV purchase grant takes effect (€6,000 off BEVs ≤ €50,000, applied at the point of sale), but the agent's system prompt predates it. It keeps assessing affordability on the gross price and wrongly rejects borderline applicants who are now affordable. Every quality, tone and format eval stays green: the rejections read perfectly; they're just *wrong*. The only smoke is a rising appeal / `user_disagreement` rate. The failure is silent because nothing was scoring decision *correctness* under the new rule.
 
**The arc** (the demo walks the full engineering loop, trace → fix → proof):
 
1. **Production reality.** ~4,000 backdated traces show the agent working at scale: a planner → `retrieve_policy` → `check_subsidy_eligibility` + `compute_affordability` tools → the Sonnet `decision` → a Haiku `explain`, with realistic latency, token usage and cost. Quality/tone/format monitors are all green.
2. **The smoke.** The in-scene Lending Analytics report (`/analytics`) that opens the demo: appeals climbing, decision CSAT breaking down, eligible-BEV approval rate collapsing, financing volume walking away, while the agent's own quality monitors stay green. Something is wrong that nobody is measuring.
3. **The missing instrument.** Install the one eval that was absent: a decision-correctness managed LLM-as-judge. Backfilled over recent production, it turns red on the disputed rejections. The gap was the whole point.
4. **Curate & fix.** Curate the eligible false-negatives into a hosted dataset, then fix the prompt through prompt management (v1 stale → v2 grant-aware), labelled `production` / `development`.
5. **Prove it.** An experiment runs the labelled prompt over the dataset: the *same judge* that failed every case now passes them. Promote v2 to `production` and the live playground flips subsequent decisions reject → approve, no code change.

**This kit tells the prompt-loop story:** catching a silent regression in production and closing the loop on it, end to end.
 
The arithmetic that produces the regression (spec §17):
 
| Application | v1 (stale) | v2 (fixed) | Judge on v2 |
|---|---|---|---|
| BEV €42k, line €40k (eligible, borderline) | reject (42k > 40k) | **approve** (36k ≤ 40k) | PASS |
| BEV €58k, line €55k (over cap) | reject | reject (no grant) | PASS |
| PHEV €42k, line €40k (not BEV) | reject | reject (no grant) | PASS |

The full spec lives in this repo as `langfuse-demo-synth-spec.md` — the
**"Full spec"** doc in the portal's docs reader.

## What's in the package (the Run-Triad)

Deploying this kit lands everything it takes to present the demo:

- **The Spool** — ~4,000 backdated traces plus scores, sessions, a user
  population, prompts v1/v2, and the hosted `ev-grant-disputed-rejections`
  dataset, batch-ingested into your Langfuse project. Byte-deterministic and
  model-free; the full inventory is under
  [What the seeded data contains](#what-the-seeded-data-contains).
- **The Presenter Runbook** — `DEMO_SCRIPT.md`, generated at seed time and
  filled with *this run's real* dates, trace IDs, figures and deep links. The
  portal renders it on the deployment page; it is the talk track.
- **The Companion** — the live decision playground, plus the staff-facing
  `/analytics` lending report that opens the demo. Started on demand from the
  portal; see [The Companion, played live](#the-companion-played-live).

## Deploying it from the depot

1. Pick **EV Subsidy Silent Regression** in the portal catalog and click
   **Deploy this demo**. Connect a Langfuse demo project — the kit refuses any
   project whose name doesn't contain `demo`, and the check runs before any job
   starts, so a customer's production project is never at risk.
2. The pipeline pauses with the exact billable-units estimate for your OK
   before anything is written, then runs this kit's own Recipe — materializing
   the deterministic Spool and replaying it into your project — and finishes
   with the kit's own `verify`, proving the golden path landed.
3. Present from the **Presenter Runbook** on the deployment page and the seeded
   Langfuse project.
4. The Companion is the encore: it is never running by default — start it from
   the deployment page when you want to hand the room the wheel. It needs an
   LLM key (provider chosen at deploy time) for its one real model call per
   submission.
5. Teardown is project-level: to run the demo fresh, point a new deployment at
   a fresh Langfuse project and re-seed.

One manual step remains in the Langfuse UI — the managed judge below.

## The managed judge (created once in the UI)

The decision-correctness judge is a **managed LLM-as-judge** configured in the Langfuse UI —
it cannot live in the repo, but the Presenter Runbook's step 3 contains the exact prompt to
paste, the variable mappings, and the scopes. It is *the same judge* on both surfaces: scoped
to the recent production traces (backfill → **red**) and to the dataset's new runs (the
experiment → **green**). Either target needs an LLM connection (Anthropic key, or Bedrock)
configured in project settings for the managed judge and the experiment task.

## The Companion, played live

The live decision playground is a small configurator so the audience can emit *their own*
trace: pick one of five prefabs or enter a custom application against an **editable credit
line**, submit, and get the **real production decision** back — rendered as a native
agent-graph trace at the top of the timeline. A **Dispute** button logs a `user_disagreement`
appeal (with a free-text comment) on that trace, nudging the dashboard's appeal rate live. The
prompt is pulled by the `production` label *per request*, so promoting v2 to production flips
subsequent submissions from reject → approve — no code change.

The playground also carries the demo's **central red/green beat**. At the very bottom of the
page, behind a deliberately quiet `presenter tools` disclosure, sit two buttons — **Run eval ·
production** and **Run eval · development** — that run the hosted dataset through the labelled
prompt server-side and render the verdict, the matched-item counts and a dataset-runs deep
link in scene. They are presenter controls, not part of the fiction: collapsed and muted so a
prospect reading the loan application never registers them. The Presenter Runbook's step 6
walks it. No shell is involved, and the model calls ride the deployment's own LLM key through
the Companion Adapter.

The same beat, end to end — **submit → decision + feedback → the recorded trace in Langfuse:**

| 1 · Submission form | 2 · Decision + feedback | 3 · Recorded trace |
|---|---|---|
| ![Playground submission form](https://raw.githubusercontent.com/borismichel/langfuse-synth-ev/main/docs/img/playground-form.png) | ![Lending decision with review request](https://raw.githubusercontent.com/borismichel/langfuse-synth-ev/main/docs/img/playground-decision.png) | ![The decision's trace in Langfuse](https://raw.githubusercontent.com/borismichel/langfuse-synth-ev/main/docs/img/playground-trace.png) |
| A BEV at €38,000 against a €32,000 line — borderline-eligible under the new grant. | The stale `production` prompt **declines** it (grant €0, ignoring the €6k it qualifies for); the customer requests a review. | The native agent-graph trace lands in the deployment's project, carrying the real `decision` call (tokens + cost) and the `user_disagreement` score from the review. |

Only the `decision` is a real model call (real tokens + latency); the surrounding agent graph
is templated/computed exactly like the seed, so the live trace is shape-identical to the
seeded data. Prefabs: `eligible` (the bug), `overcap`, `phev`, `approvable`, `rejected`.

A second, staff-facing route — **`/analytics`** — is the in-scene **lending-analytics report**
that opens the demo: the weekly risk dashboard Lending Analytics sends AI Engineering. Appeals
climbing, decision CSAT breaking down, eligible-BEV approval rate collapsing, financing volume
walking away — while the agent's own quality monitors stay green. Every figure is **derived from
the same deterministic plan the seed ingested** (the score draws are replayed from the same
id-keyed rng substreams), so the report and the data in Langfuse always agree.

## What the seeded data contains

- **~4,000 traces** over 30 days with diurnal/weekly shape; realistic latency (log-normal)
  with a **time-to-first-token** on every generation; **production-scale token usage**
  anchored to the visible chat messages (input = messages + per-role overhead; Opus thinking
  billed as `reasoning` tokens) with **prompt caching** (cache-read / cache-creation split),
  multi-turn context growth, and Opus reasoning that feeds the decision step's input; cost
  (token × per-model price, incl. cache rates), and a baseline error rate.
- Each trace is an **agent graph**: a `credit_agent` orchestrator over a planner (Opus, ~25%),
  a `retrieve_policy` retriever, two tool calls (`check_subsidy_eligibility`,
  `compute_affordability`), the Sonnet `decision` (carrying `tool_calls`), and a Haiku `explain`.
  (Tool/retriever carry their type in metadata; native agent-graph observation types are
  OTel-only, so they're rendered as spans to spare a small self-hosted ClickHouse.)
- A realistic **model mix** — so the **cost view and volume view disagree** (Haiku dominates by
  call count; Sonnet/Opus dominate spend).
- **Scores by instrument kind** (best-practice coverage): deterministic `format_compliance` on
  **100%** of traces; an LLM-judge pass (`answer_quality` + `tone`) on a thin **~15%** sample;
  `user_disagreement` (BOOLEAN) — an **LLM-judge over the interaction** that flags customer
  pushback, sampled ~15% and **forced true on the disputed false-negatives** (it drifts, and its
  verdict *drives the `disputed` tag*); and per-session `csat` at a ~30% response rate. **No**
  decision-correctness score — that gap is the point.
- **Sessions** (single- and multi-turn), a **user population** with Zipf-ish power users
  (loan officers), and `production`/`staging` environments.
- The **golden path**: a drift window of eligible false-negatives (wrongly rejected, ramping to
  demo day) plus correct-rejection controls; prompt **v1** labelled **`production`** (stale) and
  **v2** labelled **`development`** (the fix), with every `decision` generation linked to **v1**;
  the hosted **`ev-grant-disputed-rejections`** dataset (eligible false-negatives + controls,
  each with `sourceTraceId`); and a **reserved pool** of fresh false-negatives kept *out* of the
  dataset for the live "add from trace" beat.
- **Ambient incidents** (toggleable): a cost spike, an error burst, optional latency degradation.

Everything is **deterministic** (single `seed`) and **model-free at seed time** — a large seed
is free and byte-reproducible. The model runs in exactly one place: the live experiment.

## Delivery model: a cartridge, not a standalone app

Per the delivery-model decision (2026-07-29): **a kit is a cartridge that goes
into the depot** — the primary delivery method is as-is through the portal,
which owns deployment, seeding, artifacts, and the Companion's lifecycle. A
standalone-run story exists (everything below runs from a clone), but the
decision on how kits run individually *outside* the depot is explicitly
deferred — this repo references that open question without answering it.

---

## Development and running outside the depot

Everything from here down is for **kit development** — the `synth` CLI, local
seeding, tests, and release plumbing. None of it is needed to deploy or present
the demo through the depot. (Running a kit standalone this way works today, but
it is the kit-dev loop, not a supported delivery method — see the
[delivery model](#delivery-model-a-cartridge-not-a-standalone-app) note above.)

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
synth seed     --config config/demo.yaml     # spool backdated data to disk → batch-import, register prompts, build dataset, emit DEMO_SCRIPT.md
synth verify   --config config/demo.yaml     # query back via the v2 API and assert the golden path

# 4. follow DEMO_SCRIPT.md for the live presentation; the experiment runs the *labelled* prompt:
synth experiment --config config/demo.yaml                     # production (v1, stale) → RED
synth experiment --config config/demo.yaml --label development  # development (v2, the fix) → GREEN
# then promote v2 to `production` in the UI and re-run the production command → green
```

`synth seed` writes **`DEMO_SCRIPT.md`** — the Presenter Runbook filled with *this run's real*
dates, trace IDs, figures and deep links. Re-seeding regenerates a matching script
(`synth script` regenerates it from existing run state). After seeding, confirm the data
matches the narrative with **[`VERIFICATION.md`](VERIFICATION.md)** (`synth verify` + live
coverage / drift / tag checks). If a large import stalls, the generated data is safe on disk
— resume with `synth import-spool`.

### Running the playground locally

```bash
pip install -e '.[playground]'
synth playground --config config/demo.yaml          # → http://127.0.0.1:8000
synth submit --config config/demo.yaml --prefab eligible --line 32000   # one-shot, from the terminal
```

`synth playground` serves the same configurator (FastAPI) the depot starts as the
Companion, including the `/analytics` report route.

### Architecture (why the batch ingestion endpoint)

The high-level OTel SDK timestamps observations from the wall clock and offers no
`start_time` — it can't backfill history. So the seed path builds event objects directly and
posts them to **`POST /api/public/ingestion`** with explicit `timestamp` / `startTime` /
`endTime` and the `x-langfuse-ingestion-version: 4` header (real-time visibility on the v2
endpoints). Datasets, prompts and the experiment use the v4 SDK (separate API surfaces).

Ingestion is **two-phase and recoverable**: generation streams every event to an NDJSON
**spool on disk** first, then a separate pass **batch-imports** it in chunks. A wedged or slow
upload can't lose the (deterministic, expensive) generated data — resume with
`synth import-spool`. The spool lives under `.synth_spool/` (gitignored).

**Cloud vs self-hosted** is a single URL-derived fact in [`target.py`](src/synth/target.py)
(`TargetProfile.detect`), kept out of every call site. The batch ingestion endpoint already
retries, but the hand-rolled REST helpers (the project guardrail, prompt-label PATCH,
score-config creation, and `synth verify`'s paginated query-backs) did single shots that
Langfuse Cloud rate-limits with 429s. The shared core's `langfuse_synth_core.http.request_retry`
is the one **Retry-After-aware** backoff they all share (moved to the lib in Ring 2, #33 — it
speaks the Langfuse REST machine, not the scenario), and on Cloud the one-at-a-time reads/writes
get a small `post_throttle_s` spacing so they don't trip the limiter to begin with
(self-hosted: zero overhead). `seed`, `experiment` and `verify` each log which target they hit.

```
config/demo.yaml ──▶ generator (deterministic plan)
                          │
        score configs ─▶ prompts (v1→production, v2→development) ─▶ spool→batch-import traces+scores ─▶ dataset+items
                          │                                                │
                          └────────────── .synth_state.json ──────────────┘
                                                  │
                              DEMO_SCRIPT.md  ◀────┘   (synth script)

demo time:  synth experiment [--label production|development] ──▶ run_experiment(task = decide(item.input, label))  + managed judge
```

`decide(application, prompt_label) -> Decision` is the **single agent function** — seeding and
the experiment both route through it. At seed time the label selects the arithmetic (`"v1"`
stale vs `"v2"` fixed); at demo time the experiment passes a **Langfuse label**
(`production` / `development`) that's resolved to the live prompt at runtime — so promoting v2
to `production` in the UI changes what the eval runs, no code change. See
[`src/synth/`](src/synth/) and the layout in spec §15.

### Repo layout

```
config/demo.yaml          # the run config (auditable; seed + this file determine everything)
prompts/credit_decision.v{1,2}.txt
src/synth/
  agent.py                # decide(application, prompt_label) -> Decision  ← the one lever
  config.py rng.py models.py pricing.py timegen.py distributions.py content.py
  target.py http.py       # Cloud-vs-self-hosted facts + Retry-After-aware REST helper
  seed/                   # ingest (spool+batch), events, traces, sessions, scores, golden_path, prompts, datasets, run
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
- Data is append-only within Langfuse's 30-day merge window, and seed IDs are deterministic, so
  re-running **upserts** rather than duplicates. Prompt registration is **idempotent on content**
  (no version churn — v1 stays version 1), and the `production`→v1 / `development`→v2 labels are
  **re-asserted on every seed**, so the red→green flip always resets.
- **Teardown is project-level**: spin up a fresh project and re-seed. A fresh project is also
  required to *change coverage* (which scores get emitted) — append-only ingestion never deletes,
  so dropped scores would otherwise linger as orphans.

### CI/CD regression gate (optional)

`synth experiment --gate 0.95` computes an offline PASS-rate of v2 over the hosted dataset (no
model call) and exits non-zero below the threshold — drop it in a pipeline as a regression gate.

### Tests

```bash
pip install pytest && pytest -q     # determinism, the §17 arithmetic table, golden-path invariants
```

### Image releases

Pushing a `vX.Y.Z` tag triggers `.github/workflows/publish.yml`, which builds this
kit's image, pushes it to `ghcr.io/borismichel/langfuse-synth-ev`, and cosign-signs it
keylessly (Spec E · E7, #102). See
[`langfuse-synth-core`'s `docs/CI_SIGNING.md`](https://github.com/borismichel/langfuse-synth-core/blob/main/docs/CI_SIGNING.md)
for the full contract — image naming, cadence, runner, and the signing-identity policy
the portal's verification gate checks against.
