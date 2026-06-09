# Langfuse Demo Data Synthesiser — EV-subsidy regression

Seed a fresh self-hosted Langfuse project with believable, time-distributed observability
data — anchored by one end-to-end **golden path** (the EV-subsidy regression) — so a demo
dashboard looks *alive* and walks an audience through the full engineering loop:

> trace → detect a silent failure → build an evaluator → curate a dataset → fix via prompt
> management → prove the fix with an experiment.

This is the first scenario in the demo-data kit. It is a cloneable repo: `git clone`, set
`.env`, `synth seed`, run the demo. The full spec lives in [`langfuse-demo-synth-spec.md`](langfuse-demo-synth-spec.md).

---

## The story (60 seconds)

A new EV purchase grant (€6,000 off BEVs ≤ €50,000, applied at point of sale) takes effect.
The credit-approval agent's system prompt predates it, so it assesses affordability on the
**gross** price and **wrongly rejects** borderline applicants who should now be approved.
Quality, tone and format evals stay **green** — the rejections read perfectly well; they're
just *wrong*. The only smoke is a rising `user_disagreement` / appeal rate. The failure is
silent because nothing was checking decision correctness under the new rule. The demo
installs that missing judge, curates the disputed cases, fixes the prompt, and proves the
fix — the **same judge** that failed every case now passes them.

The arithmetic that produces it (spec §17):

| Application | v1 (stale) | v2 (fixed) | Judge on v2 |
|---|---|---|---|
| BEV €42k, line €40k (eligible, borderline) | reject (42k > 40k) | **approve** (36k ≤ 40k) | PASS |
| BEV €58k, line €55k (over cap) | reject | reject (no grant) | PASS |
| PHEV €42k, line €40k (not BEV) | reject | reject (no grant) | PASS |

---

## Quick start

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. point at a DEMO/SANDBOX project (the guardrail refuses non-matching project names)
cp .env.example .env      # fill LANGFUSE_BASE_URL + keys; ANTHROPIC_API_KEY only needed for `experiment`

# 3. preview, then seed
synth plan     --config config/demo.yaml     # dry run: volumes, golden-path dates, dataset summary (no network)
synth seed     --config config/demo.yaml     # ingest backdated data, register prompts, build dataset, emit DEMO_SCRIPT.md
synth verify   --config config/demo.yaml     # query back via the v2 API and assert the golden path

# 4. follow DEMO_SCRIPT.md for the live presentation; step 5 runs:
synth experiment --config config/demo.yaml   # run the hosted dataset with prompt v2 (the live fix) — makes real model calls
```

`synth seed` writes **`DEMO_SCRIPT.md`** — a presenter's runbook filled with *this run's real*
dates, trace IDs, figures and deep links. Re-seeding regenerates a matching script
(`synth script` regenerates it from existing run state).

---

## What gets created

- **~4,000 traces** over 30 days with diurnal/weekly shape; realistic latency (log-normal),
  tokens, cost (token × per-model price), and a baseline error rate.
- A realistic **model mix** — Opus plans (~25%), Sonnet decides (1×/trace), Haiku does the
  cheap high-volume steps — so the **cost view and volume view disagree** (Haiku dominates by
  call count; Sonnet/Opus dominate spend).
- **Scores** on a realistic fraction: `answer_quality` (NUMERIC), `tone` /
  `format_compliance` (CATEGORICAL), `user_disagreement` (BOOLEAN, the lagging signal that
  drifts), and per-session `csat`. **No** decision-correctness score — that gap is the point.
- **Sessions** (single- and multi-turn), a **user population** with Zipf-ish power users
  (loan officers), and `production`/`staging` environments.
- The **golden path**: a drift window of eligible false-negatives (wrongly rejected) plus
  correct-rejection controls; prompt **v1** (stale) and **v2** (fixed) registered, with every
  `decision` generation linked to **v1**; the hosted **`ev-grant-disputed-rejections`**
  dataset (eligible false-negatives + controls, each with `sourceTraceId`); and a **reserved
  pool** of fresh false-negatives kept *out* of the dataset for the live "add from trace" beat.
- **Ambient incidents** (toggleable): a cost spike, an error burst, optional latency degradation.

Everything is **deterministic** (single `seed`) and **model-free at seed time** — a large seed
is free and byte-reproducible. The model runs in exactly one place: the live experiment.

---

## The managed judge (created once in the UI)

The decision-correctness judge is a **managed LLM-as-judge** configured in the Langfuse UI —
it cannot live in the repo, but `DEMO_SCRIPT.md` step 3 contains the exact prompt to paste,
the variable mappings, and the scopes. It is *the same judge* on both surfaces: scoped to the
recent production traces (backfill → **red**) and to the dataset's new runs (the experiment →
**green**). Self-hosted needs an LLM connection (Anthropic key, or Bedrock) configured in
project settings for the managed judge and the experiment task.

---

## Architecture (why the batch ingestion endpoint)

The high-level OTel SDK timestamps observations from the wall clock and offers no
`start_time` — it can't backfill history. So the seed path builds event objects directly and
posts them to **`POST /api/public/ingestion`** with explicit `timestamp` / `startTime` /
`endTime` and the `x-langfuse-ingestion-version: 4` header (real-time visibility on the v2
endpoints). Datasets, prompts and the experiment use the v4 SDK (separate API surfaces).

```
config/demo.yaml ──▶ generator (deterministic plan)
                          │
        score configs ─▶ prompts v1/v2 ─▶ backdated traces+scores ─▶ hosted dataset+items
                          │                                                │
                          └────────────── .synth_state.json ──────────────┘
                                                  │
                              DEMO_SCRIPT.md  ◀────┘   (synth script)

demo time:  synth experiment ──▶ run_experiment(task = decide(item.input, "v2"))  + managed judge
```

`decide(application, prompt_label) -> Decision` is the **single agent function** — seeding and
the experiment both route through it; the **only lever** is `prompt_label` (`"v1"` vs `"v2"`).
See [`src/synth/`](src/synth/) and the layout in spec §15.

### Repo layout

```
config/demo.yaml          # the run config (auditable; seed + this file determine everything)
prompts/credit_decision.v{1,2}.txt
src/synth/
  agent.py                # decide(application, prompt_label) -> Decision  ← the one lever
  config.py rng.py models.py pricing.py timegen.py distributions.py content.py
  seed/                   # ingest, events, traces, sessions, scores, golden_path, prompts, datasets, run
  experiment/run.py       # run_experiment(task = lambda i: decide(i.input, "v2"))
  verify.py script.py cli.py
templates/demo_script.md.j2
fixtures/golden_v1_decisions.json   # committed v1 outputs for offline provenance
tests/
```

---

## Configuration

All knobs are in [`config/demo.yaml`](config/demo.yaml): volume/window, population, the model
pricing table, the golden-path dates (grant effective offset, drift window), the dataset shape
(item count, eligible share, reserved count), ambient incidents, and scoring coverage. Change
the `seed` for a different-but-reproducible run.

## Guardrails & teardown

- The seeder **refuses to run** unless the target project's name contains `target.project_hint`
  (default `demo`). Point it only at demo/sandbox projects.
- Data is append-only within Langfuse's 30-day merge window, and seed IDs are deterministic, so
  re-running **upserts** rather than duplicates. **Teardown is project-level**: spin up a fresh
  project and re-seed.

## CI/CD regression gate (optional)

`synth experiment --gate 0.95` computes an offline PASS-rate of v2 over the hosted dataset (no
model call) and exits non-zero below the threshold — drop it in a pipeline as a regression gate.

## Tests

```bash
pip install pytest && pytest -q     # determinism, the §17 arithmetic table, golden-path invariants
```
