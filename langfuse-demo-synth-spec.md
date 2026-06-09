# Langfuse Demo Data Synthesiser — Specification

**Status:** Draft v0.9
**Owner:** Boris
**Target:** Self-hosted Langfuse
**Purpose in one line:** Seed a fresh Langfuse project with believable, time-distributed observability data — anchored by one end-to-end "golden path" story — so a demo dashboard looks *alive* and walks an audience through the full engineering loop.

---

## 1. Purpose & non-goals

### Purpose
Generate synthetic LLM-application telemetry — traces, nested observations, sessions, users, scores, plus a pre-seeded prompt and dataset — and ingest it into a target Langfuse project so that:

- Every dashboard and chart is populated with realistic distributions (latency, cost, token usage, error rate).
- Data is spread across a configurable historical window with diurnal/weekly patterns, so time-series views look real.
- One **flagship narrative** (the EV-subsidy regression, §7) sets up a live demo of the complete loop: trace → detect a silent failure → build an evaluator → curate a dataset → fix via prompt management → prove the fix with an experiment.
- A few **ambient incidents** (cost spike, latency degradation, error burst) give secondary things to drill into.
- A run is **reproducible** (seeded) so a demo can be rehearsed and re-created identically.

### Non-goals
- Not a load/perf tester — we are not measuring Langfuse throughput.
- Not real instrumentation — **seeding makes no model calls at all.** Every trace's content (the few-thousand ambient traces *and* the golden-path v1 rejections) is deterministic and templated, so a large seed is free and byte-reproducible. The model runs only at demo time: the live experiment (v2 task) and the judge — and the judge sees only a bounded set (a recent-trace sample + the ~24 dataset items), never the thousands.
- Not for production projects — it writes fabricated data; point it only at demo/sandbox projects.

---

## 2. Core architectural decision: the ingestion layer

This is the decision everything else hangs off.

The high-level OTel-based SDK (Python v4 / JS v5) timestamps observations synchronously from the wall clock and offers **no `start_time` parameter** on `start_observation()` / `start_span()`. It is built for instrumenting live code, not backfilling history. Using it would pin every trace to "now."

**Decision:** build on the **low-level batch ingestion endpoint** (`POST /api/public/ingestion`, reachable via `langfuse.api.ingestion.batch([...])`). We construct event objects directly:

- `TraceCreate` — with explicit `timestamp`
- `ObservationCreate` / span / generation events — with explicit `startTime` and `endTime`
- `ScoreCreate` — with explicit `timestamp`

This gives full control over backdating and latency (latency is derived from `endTime − startTime`, so we set both).

**Implications to honour:**
- Send `x-langfuse-ingestion-version: 4` on requests so data is visible in real time on the v2 query/metrics endpoints rather than being delayed.
- The data model is **mostly immutable** with a 30-day upsert-merge window keyed on `id`. Our synth *creates* each object once, so this is mostly irrelevant — but it means re-running against the same project **adds** data. Teardown = fresh project (§12).
- Self-hosted has no per-unit billing, but traces + observations + scores still drive ClickHouse storage/compute. A 30-day, multi-thousand-trace seed is cheap.
- **Datasets/prompts are a separate API surface** (`api.datasets*`, `api.prompts*`), unaffected by the ingestion-endpoint choice. Dataset items reference trace IDs, so they link to our backdated traces fine (§7).
- **Seeding is deterministic and model-free:** all backdated traces (including golden-path v1 rejections) are templated `Decision`s, ingested via the batch API with explicit timestamps. We never let the high-level SDK own ingestion, and we never call the model in the seed path — that keeps a few-thousand-trace seed both free and reproducible (§7, §9, §16).

---

## 3. Domain model we emit

| Langfuse object | We generate | Notes |
|---|---|---|
| **Trace** | One per request/turn | Carries `userId`, `sessionId`, `tags`, `metadata`, `environment`, input/output |
| **Observation: span** | Orchestration / retrieval / tool steps | Nested under trace; can nest further |
| **Observation: generation** | LLM calls | `model`, `input`, `output`, `usageDetails` (tokens), cost |
| **Observation: event** | Discrete markers (cache hit, guardrail trip) | Zero-duration |
| **Session** | Groups multi-turn traces | Same `sessionId` across N traces |
| **User** | Synthetic population | Via `userId` propagation |
| **Score** | Quality / feedback / pass-fail | `NUMERIC` / `CATEGORICAL` / `BOOLEAN`; on traces, observations, sessions |
| **Score config** | Standardised scoring schemas | Created first so scores are comparable |
| **Prompt** (v1) | Stale system prompt, registered | Historical `decision` generations link to it (§7) |
| **Dataset** | One golden-path dataset | e.g. `ev-grant-disputed-rejections`, hosted on Langfuse |
| **DatasetItem** | Pre-seeded items | `input` (application), `expectedOutput` (correct decision), `metadata` (eligibility), `sourceTraceId` → its trace |

IDs use W3C Trace Context format via `create_trace_id()`; seeded deterministically (§9).

---

## 4. Application archetype (scenario model)

**Default archetype: agentic credit-approval assistant** — an agent that assesses EV loan applications. A true agentic workflow (retrieval + tool calls + a decision generation), mirroring a real production agent, and the substrate for §7.

An archetype defines:
- **Trace template(s):** observation-tree shape and which steps are optional/probabilistic.
- **Tool inventory:** named tools, each with a latency profile and failure rate.
- **Model mix:** which models appear, with pricing and token profiles.
- **Content pool:** templated application inputs/decision outputs. For most traces this is set dressing; for the golden-path window it must be *semantically real* and judge-evaluable (§7).

Other archetypes are pluggable (support copilot, batch summarisation). Ship one well; design the interface so more drop in.

---

## 5. Data generation model

### Volume & window
- `total_traces` over `window_days` (default: ~3–5k over 30 days).
- Distributed with a **diurnal + weekly** weighting: business-hours peaks, overnight troughs, weekend dip.

### Realistic distributions
- **Latency:** log-normal per step; trace latency = critical-path sum. Long tail of slow outliers.
- **Tokens:** sampled per generation from model-appropriate ranges.
- **Cost:** token counts × per-model pricing table (in config, auditable).
- **Errors:** baseline error rate per tool/step; errored observations carry `level=ERROR` + `statusMessage`.

### Trace template (default archetype: credit-approval agent)
```
trace: "credit_agent.assess_application"
 ├─ generation: "plan"                  (Opus  — strategy; only ~25% of traces, the ambiguous ones)
 ├─ span: "load_application"
 │    └─ generation: "extract_fields"   (Haiku — normalize the raw application)
 ├─ span: "retrieve_policy"             (vector_search — no model)
 ├─ span: "check_subsidy_eligibility"   (tool — no model)   ← load-bearing for §7
 ├─ span: "compute_affordability"       (tool — financed principal vs approved line)
 ├─ generation: "decision"              (Sonnet — the work: approve/reject; this is decide(), links to prompt v1)
 └─ generation: "explain"               (Haiku — customer-facing rationale)
```
In the stale-prompt window, the agent skips `check_subsidy_eligibility` or ignores its result, so `compute_affordability` runs on the gross price (§7). Multi-turn sessions chain 2–4 traces under one `sessionId`.

**Model mix (realistic).** Roles map to tiers: **Opus** plans (hard/ambiguous applications only — ~25% of traces), **Sonnet** does the work (the `decision` generation, exactly one per trace — this is `decide()`), **Haiku** handles the cheap high-volume steps (field extraction + the customer-facing explanation, 1–2 calls per trace). By **call count** Haiku dominates; by **spend** Sonnet and Opus lead (Opus is 5× Haiku per token), so the cost view and the volume view disagree — worth showing. Per-model token/latency profiles differ: Opus larger and slower (it reasons), Haiku small and fast. Pricing in §10 (Anthropic API, May 2026).

---

## 6. Scores & evaluation

A spread that exercises every scoring path so eval dashboards populate:

- **NUMERIC** — `answer_quality` (0–1), an LLM-as-judge on response quality. Stays **green** through the golden-path window (rejections are well-reasoned).
- **CATEGORICAL** — `tone` / `format_compliance`. Also green.
- **BOOLEAN / NUMERIC** — `user_disagreement` (appeals, loan-officer overrides). The **blunt, lagging human signal that drifts** in the golden-path window.
- **Session-level** — a `csat` rollup per session.

**Deliberate gap:** no existing score measures *decision correctness given applicable subsidies*. That gap is the whole point — it's what the new evaluator in §7 fills. Define score configs first; score only a realistic fraction (e.g. 60% auto, 10% human) — fully-scored data looks fake.

---

## 7. Flagship narrative — the EV-subsidy regression (the golden path)

This is the spine of the demo. A generic generator gives noise; this gives a presenter a complete story to walk through.

### The story
A new EV purchase grant comes into effect. It's applied **at point of sale**, lowering the principal a customer needs to finance. The credit-approval agent's system prompt predates the grant, so it assesses affordability on the **gross** price and **rejects borderline applicants who should now be approved**. Quality, tone and format evals stay green — the rejections read perfectly well; they're just *wrong*. The only smoke is a rising `user_disagreement` / appeal rate. The failure is silent because nothing was checking decision correctness under the new rule.

### Why "silent"
The answer fails on exactly one axis — correctness-under-the-new-grant — that no eval covers. User disagreement is the lagging, noisy signal; the judge built during the demo is the precise instrument installed *after* noticing the smoke. The lesson: generic quality scores lull you; you need purpose-built correctness evals.

### The fictional grant rule (self-contained, so the judge never relies on model knowledge)
> **EV Purchase Grant** — effective `[run_date − ~7 days]`. Eligible: battery-electric vehicles (BEV), manufacturer list price ≤ €50,000. Benefit: €6,000 deducted at point of sale, reducing the financed principal. Decision rule: approve if financed principal ≤ applicant's approved credit line (and DTI ≤ threshold).

Worked case: BEV at €42,000, approved line €40,000. Pre-grant → finance €42,000 > €40,000 → **reject**. With grant → finance €36,000 ≤ €40,000 → **should approve**. The stale agent rejects a good applicant — a **false rejection** (the safe failure direction: turning away good customers, not approving bad loans).

### What the synth fabricates (the "before" state)
- A baseline of healthy historical credit-approval traces across the window.
- A recent window (~last 5 days) where, **among eligible borderline applicants**, the agent rejects on gross price — semantically real inputs (application details) and outputs (a clear, well-reasoned rejection that never mentions the grant).
- A rising `user_disagreement` score on those recent traces, while `answer_quality` / `tone` stay green.
- Prompt **v1 (stale, no grant section)** registered in prompt management, with historical `decision` generations linked to it — so "every bad decision used v1" is visibly true.
- A pre-seeded **dataset** (`ev-grant-disputed-rejections`) built from the disputed traces: mostly **eligible false-negatives** (wrongly rejected, should-approve) plus a few **ineligible controls** (correctly rejected — over the €50k cap, or a PHEV). Each item carries the application as `input`, the correct decision as `expectedOutput`, eligibility flags in `metadata`, and a `sourceTraceId` linking it to its trace. *("there are already some in the set.")*
- A **reserved pool** of recent eligible false-negative traces deliberately left **out** of the dataset, so the presenter has fresh, current cases to add live.

### What the presenter does live (the loop)
1. Notice the `user_disagreement` drift; open recent rejections — they read fine.
2. Build the **decision-correctness LLM-as-judge**; run it over recent production traces → they go **red**.
3. Open the pre-seeded dataset (already has disputed cases) and **add one current false-negative from a reserved trace** — demonstrating trace-to-dataset curation without depending on it for the whole set. *(Map the trace input; do **not** copy the v1 rejection in as expected output.)*
4. **Author prompt v2** in prompt management (adds the grant rule + apply instruction).
5. **Run the experiment** (v4 Experiment Runner SDK, hosted dataset) with v2 as the task and the same judge as the evaluator → every item, including the just-added one, comes back **green**.

**Red→green:** red is established on production traces in step 2; green is the v2 experiment in step 5. *Optional punchier visual:* also run a v1 baseline experiment so the UI shows a side-by-side red-column / green-column comparison on the same dataset.

### The evaluator (reference-grounded decision judge)
- **Input:** application details + the agent's decision + rationale.
- **Reference:** the grant rule above, embedded in the judge prompt (not the judge's own knowledge — unreliable and self-defeating given the story is *about* stale knowledge). The literal judge template + variable mappings are in §16.
- **Output:** `PASS`/`FAIL` + a one-line reason ("eligible BEV under cap, post-effective-date, grant not applied → wrong rejection").
- **Mechanism — use a *managed* LLM-as-judge (configured in the Langfuse UI), not an SDK evaluator function.** Only the managed kind can run on *both* surfaces: configure it once with the reference rule, scope it to the recent production traces (backfill) for the **red**, and scope a copy to the `ev-grant-disputed-rejections` dataset's new runs for the **green**. That's how it's literally the *same judge*. (An SDK `evaluators=[fn]` function runs in your own process and cannot reuse a UI evaluator, so it would mean duplicating the judge logic — fine as a CI/code-only fallback, but not the demo path.)
- **Models:** the v2 task run uses **Sonnet** — the same model as the production `decision` step (§5), so the experiment has production fidelity. The judge uses **Sonnet** too (or **Opus** for a stronger-than-agent judge; it runs on a bounded set, so cost is negligible). **Temperature 0** on both so the flip is identical every rehearsal.
- **Self-hosted setup:** the managed judge needs an LLM connection (Anthropic key, or Bedrock) configured in project settings. The task run and any code evaluator call the model directly and don't need it.

### Dataset & experiment — build notes
- The synth creates the dataset and items via the datasets API (`api.datasets*` / dataset-items), each with `sourceTraceId`. The dataset is **hosted on Langfuse**, not local, so experiment runs render as dataset runs with comparison views. (Local datasets only create traces/scores — no run rows, no comparison.)
- The live experiment uses the **v4 Experiment Runner SDK** (`run_experiment`), which auto-creates the dataset run and links run items. This sidesteps the gotcha that experiment attributes alone don't insert dataset-run-item rows.
- **Independence from §2:** the synth's backdated traces use the legacy batch endpoint; dataset items just reference trace IDs, so linkage is unaffected. The synth never runs experiments itself.
- The live experiment **makes real model calls** (running v2). Pick a task model strong enough that v2 reliably applies the grant arithmetic and flips borderline cases to approve — and rehearse it. The arithmetic is simple (subtract grant, compare to line), so a mid model with an explicit prompt should hold.

### One agent function — the only lever is the prompt
There is a single agent implementation, `decide(application, prompt_label) -> Decision`: it fetches the system prompt from prompt management by label, calls the model (temperature 0), and returns a structured `Decision` (schema in §16). Everything red→green is driven by **one argument**: `prompt_label="v1"` vs `"v2"`. Same code, same model, same dataset, same judge — only the prompt differs. That is the point the demo makes visible.

The model runs in **only one place at demo time** — the experiment:
- **The experiment runner** calls `decide(item.input, "v2")` as the `run_experiment` task, live, and the managed judge scores the run. This is the real production agent path, exercised with the fixed prompt.
- **Seeding never calls the model.** The few-thousand traces *and* the golden-path v1 rejections are deterministic, templated `Decision`s, ingested backdated via the batch API. This satisfies the cost/determinism requirement: a large seed is free and byte-reproducible.

The v1-rejection templates are written to mirror exactly what `decide(app, "v1")` produces — a rejection computed on the gross price with no grant applied — so they are authentic *and* judge-failable. Optional: generate them **once** with `decide(app, "v1")` and commit as **fixtures**, for literal same-function provenance with no per-seed (and no per-thousand) cost.

### The experiment runner script (shipped with the demo kit)
A small, version-controlled script the presenter runs in step 5. It loads the hosted dataset, runs **prompt v2** as the task, and lets the managed judge score the resulting dataset run. Pseudocode (verify exact params against the v4 Python reference):

```python
from langfuse import get_client
# from anthropic import Anthropic   # or a Bedrock client

langfuse = get_client()                 # picks up LANGFUSE_BASE_URL → your self-hosted instance
dataset  = langfuse.get_dataset("ev-grant-disputed-rejections")

def run_v2(item):                       # task: one dataset item -> decision output
    application = item.input
    prompt = langfuse.get_prompt("credit_decision", label="v2")   # prompt management
    messages = prompt.compile(application=application)
    resp = client.messages.create(model="claude-haiku", temperature=0,
                                   max_tokens=512, messages=messages)
    return parse_decision(resp)         # {"decision": "...", "financed_principal": ..., ...}

result = langfuse.run_experiment(
    name="ev-grant-fix",
    data=dataset.items,                 # hosted dataset → renders as a Dataset Run with comparison view
    task=lambda item: decide(item.input, prompt_label="v2"),   # SAME agent fn as seeding, label flipped
    # evaluators=[...]                   # leave empty: the managed UI judge scores the run instead
    # run_evaluators=[...]               # optional aggregate (e.g. % PASS) for a CI gate
)
print(result.format())
langfuse.flush()
```

- Because the dataset is **hosted**, `run_experiment` auto-creates the Dataset Run and links each execution trace to its item; the managed judge (scoped to this dataset's new runs) then scores them → green.
- Optional SA flex: wrap a `run_evaluators` aggregate + a threshold to turn this into a **CI/CD regression gate** (raise on % PASS below target) — same script, run in a pipeline.

### Talk track (one line)
"Quality scores were green the whole time — but appeals were climbing. We built a correctness judge, pulled the disputed cases into a dataset, fixed the system prompt to apply the new grant, and the same judge that was failing every case now passes them. That's the full loop, in Langfuse."

### 7.x Ambient incidents (secondary, toggleable)
Date-anchored relative to "now": **cost spike** (the Opus planner over-triggers, or a subset switches to a pricier model / inflated tokens), **latency degradation** (one tool's latency triples), **error burst** (short window of elevated tool failures), **quiet baseline** (healthy contrast).

---

## 8. Sessions, users, environments

- **Users:** fixed synthetic population (e.g. 50–200), a few power users (loan officers) generating disproportionate volume (Zipf-ish).
- **Sessions:** propagate `sessionId` early; mix single-turn and multi-turn (application → clarification → re-assessment).
- **Environments:** tag the bulk `production`, sprinkle `staging`.

---

## 9. Determinism & reproducibility

- Single top-level `seed` drives all RNG and deterministic trace/observation/dataset-item IDs.
- Same seed + same config ⇒ identical project state. Rehearse and regenerate byte-for-byte if a project is wiped.
- "Relative to now" date anchors snap to the run date, so the grant effective date and the drift window stay recent on every run.
- The seed path makes **no model calls**, so a few-thousand-trace seed is free and reproducible across clones. The only nondeterminism (live model output) is confined to the experiment at demo time.

---

## 10. Configuration schema (sketch)

```yaml
target:
  host: http://localhost:3000           # self-hosted base URL
  # keys via env: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
  project_hint: "demo-only"             # guardrail; refuse names that don't match

generation:
  seed: 42
  archetype: credit_approval_agent
  total_traces: 4000
  window_days: 30
  population: { users: 120, multi_turn_ratio: 0.35 }

models:                                  # price per 1k tokens (Anthropic API, May 2026)
  - { name: claude-opus-4.8,   role: plan,  input_per_1k: 0.005, output_per_1k: 0.025 }
  - { name: claude-sonnet-4.6, role: work,  input_per_1k: 0.003, output_per_1k: 0.015 }
  - { name: claude-haiku-4.5,  role: light, input_per_1k: 0.001, output_per_1k: 0.005 }

model_mix:                               # realistic per-trace distribution
  plan_step_share: 0.25                  # fraction of traces that invoke the Opus planner
  light_calls_per_trace: [1, 2]          # Haiku extraction + explanation (most calls by count)
  # the Sonnet decision step is exactly one per trace

golden_path:                            # the flagship narrative (§7)
  enabled: true
  judge_model: claude-sonnet-4.6          # managed LLM-as-judge (Opus for a stronger judge)
  task_model: claude-sonnet-4.6           # v2 task = production 'work' model; temperature 0
  grant_effective_day_offset: -7
  drift_window_days: 5
  grant_amount_eur: 6000
  price_cap_eur: 50000
  prompt_v1_register: true              # register stale prompt + link generations
  borderline_clustering: true
  dataset:
    name: ev-grant-disputed-rejections
    n_items: 24
    eligible_share: 0.7                 # rest are correct-rejection controls
    n_reserved_for_live_add: 3          # eligible false-negatives kept OUT of the dataset

ambient_incidents:
  cost_spike:      { enabled: true, day_offset: -12 }
  latency_degrade: { enabled: false }
  error_burst:     { enabled: true, day_offset: -3, duration_hours: 6 }

scoring: { auto_score_ratio: 0.6, human_annotation_ratio: 0.1 }
```

---

## 11. Interface / CLI

```
synth plan        --config demo.yaml   # dry-run: volumes, golden-path dates, dataset summary
synth seed        --config demo.yaml   # generate deterministic traces + templated v1 rejections, ingest
                                        #   backdated; register prompt v1; create dataset + items;
                                        #   reserve the live-add false-negatives; emit DEMO_SCRIPT.md
synth verify      --config demo.yaml   # query back via v2 API, assert counts/shape/drift/dataset
synth experiment  --config demo.yaml   # run the hosted dataset with prompt v2 (the live fix)
synth script      --config demo.yaml   # (re)generate the demo runbook from the current run state
```

- `verify` asserts the golden path specifically: the `user_disagreement` drift, green quality scores in the same window, prompt-v1 linkage on decision generations, dataset item count + `sourceTraceId` links, and that the reserved false-negatives exist in traces but **not** in the dataset.
- Batch sends in chunks (respect ingestion payload/rate limits); retry with backoff; idempotent on re-run via deterministic IDs.

---

## 12. Constraints & gotchas (build-time checklist)

- ✅ Use the batch ingestion API, **not** the high-level tracing SDK (no backdating there).
- ✅ Set `x-langfuse-ingestion-version: 4` for real-time visibility on v2 query/metrics endpoints.
- ✅ Set both `startTime` and `endTime` on observations so latency is correct.
- ✅ Order of creation: score configs → prompt v1 → traces/scores → dataset + items (items need their source traces to exist first).
- ✅ Dataset hosted on Langfuse (not local) so the live experiment renders a dataset run with comparison views.
- ✅ Golden-path content must be *semantically real and judge-evaluable* — the one place templated filler won't do.
- ⚠️ Immutable + 30-day merge window: re-running **appends**. Teardown = fresh project. Loud guardrail so it never runs against a project whose name doesn't match `project_hint`.
- ⚠️ When adding a trace to the dataset live, map the *input* only — don't let the v1 wrong rejection become the item's expected output.
- ⚠️ Self-hosted Python SDK v4 / JS v5 needs a platform version supporting ingestion-version-4 behaviour — confirm against your deployment.

---

## 13. Build phases

1. **Spike** — ingest one fully-formed backdated trace (trace + spans + generation + score) via the batch API; confirm correct latency and timestamp. *De-risks §2.*
2. **Generator core** — distributions, time model, the credit-approval archetype, sessions/users.
3. **Scores + configs** — including `user_disagreement` and the deliberate correctness gap.
4. **Golden-path corpus** — the judge-evaluable EV-application content: eligible/ineligible mix, borderline clustering, stale rationales. *Concentrated-complexity milestone; budget for it.*
5. **Agent function + golden-path wiring** — implement `decide(application, prompt_label)`; register prompt v1; produce the real v1 rejections and ingest them backdated with linked generations; plant the drift; date-anchor the grant.
6. **Dataset assembly** — pre-seed the hosted dataset (items with `input` / `expectedOutput` / `metadata` / `sourceTraceId`); reserve out-of-dataset false-negatives for the live add.
7. **Ambient incidents** + talk-track docs.
8. **CLI** (`plan` / `seed` / `verify`) + storage estimate + guardrails.
9. **Demo kit (live-demo assets)** — the experiment runner (`synth experiment`), the v2 prompt template, the managed-evaluator config (reference rule + scopes for traces and dataset runs), and the **generated** demo runbook (`synth script`, §18) populated with this run's real dates, IDs, and links.
10. **Repo packaging** — clone-and-run layout (§15), `.env.example`, `config/demo.yaml`, committed v1 fixtures for offline re-seed, README demo script.
11. **Polish** — second archetype, optional CI/CD regression-gate variant of the runner.

---

## 14. Open questions

- **Single v2 run vs v1+v2 side-by-side:** the single v2 experiment matches the story; running a v1 baseline too gives a sharper red/green comparison view in the UI. Decide per audience.
*Resolved:* self-hosted target; EV-subsidy domain; pre-seeded dataset with live "add from trace" using reserved false-negatives; **managed** LLM-as-judge (Sonnet) on both surfaces, v2 task run on Sonnet (the production 'work' model) at temperature 0; realistic model mix across Opus (plan) / Sonnet (work) / Haiku (light); the experiment runner is a shipped script using `run_experiment` against the hosted dataset; distribution = a **cloneable git repo / demo kit** (§15); the seeded rejection and the experiment output come from one agent function whose only lever is the prompt label.

---

## 15. Repo layout & packaging

A cloneable git repo: `git clone`, set `.env`, `synth seed`, run the demo. Sketch:

```
langfuse-demo-synth/
  README.md                 # setup + the full demo script (judge, dataset add, experiment)
  pyproject.toml            # langfuse, anthropic | boto3 (Bedrock), pydantic, typer
  .env.example              # LANGFUSE_BASE_URL + keys; model-provider creds
  config/demo.yaml          # the §10 config
  prompts/
    credit_decision.v1.txt  # stale — registered as label v1 by `seed`
    credit_decision.v2.txt  # fixed — registered as v2 (or authored live in the UI)   (full text of both: §17)
  src/synth/
    agent.py                # decide(application, prompt_label) -> Decision   ← the one lever
    seed/
      ingest.py             # backdated batch-ingestion helpers
      traces.py  sessions.py  scores.py
      prompts.py            # register v1/v2 in prompt management
      datasets.py           # dataset + items (sourceTraceId) + reserved live-add set
    experiment/run.py       # run_experiment(task = lambda i: decide(i.input, "v2"))
    cli.py                  # plan | seed | verify | experiment | script
  templates/                # demo_script.md.j2 -> filled into DEMO_SCRIPT.md by `synth script`
  fixtures/                 # optional cached v1 outputs for reproducible/offline seed
  tests/
```

Self-contained demo kit: the seed functions (traces, sessions, scores, prompts, dataset) and the experiment runner all live in-repo, driven by `config/demo.yaml`. The managed judge is created in the UI per the README (it can't live in the repo), but its prompt text and scope settings are documented so the setup is reproducible. The `decide` function is the shared spine — seeding and the experiment both route through it, so they can never drift apart.

---

## 16. Data contracts & the judge prompt

Pinning these makes the judge reliable: it adjudicates **structured fields**, not free prose.

### `Decision` — the agent's structured output (what `decide` returns)
```json
{
  "decision": "reject",             // "approve" | "reject"
  "list_price_eur": 42000,
  "applied_grant_eur": 0,           // v1 -> 0; v2 -> 6000 when eligible
  "financed_principal_eur": 42000,  // list_price - applied_grant
  "approved_line_eur": 40000,
  "reason": "Financed amount exceeds the approved credit line."
}
```
Seeded v1 rejections use this exact shape with `applied_grant_eur: 0`. A v2 run on an eligible borderline case returns `applied_grant_eur: 6000`, a lower `financed_principal_eur`, and `decision: "approve"`.

### Dataset-item `input` — the application
```json
{
  "applicant_id": "anon_0421",
  "approved_line_eur": 40000,
  "vehicle": { "type": "BEV", "list_price_eur": 42000 },   // type: BEV | PHEV | ICE
  "application_date": "2026-06-04"
}
```
`expectedOutput` = the correct `Decision` (eligible borderline -> approve, grant applied). `metadata` = `{ eligible: true, borderline: true, scenario: "false_negative" }` (controls use `eligible: false`).

### The judge prompt (reference-grounded, managed evaluator)
The judge needs three inputs: the application (`{{input}}`), the decision under review (`{{output}}`), and the **reference rule embedded in its own prompt**. It does **not** receive the agent's v1/v2 system prompt — it audits the output against the rule regardless of what produced it.

```
You are auditing a vehicle-loan credit decision for correctness under current policy.

REFERENCE (authoritative, effective {{grant_date}}):
- Eligible: battery-electric vehicles (BEV) with list price <= EUR 50,000.
- Benefit: EUR 6,000 deducted at point of sale, reducing the financed principal.
- Rule: approve if financed principal <= the applicant's approved credit line.

APPLICATION:          {{input}}
DECISION UNDER REVIEW: {{output}}

Decide PASS or FAIL with a one-sentence reason. FAIL if the application was
eligible (BEV, <= EUR 50,000, on/after the effective date) but the grant was
not applied, or if the resulting approve/reject decision is wrong as a result.
Respond as JSON: {"verdict": "PASS" | "FAIL", "reason": "..."}
```

**Managed-evaluator variable mapping (UI):** `{{input}}` <- trace/observation **input** (the application); `{{output}}` <- the `decision` generation **output**; `{{grant_date}}` <- a constant in the template. Emit a **CATEGORICAL** score (`pass`/`fail`) with the reason as the score comment. Scope the same evaluator to the recent production traces (the red) and to the dataset's new runs (the green).

---

## 17. Agent system prompts — v1 → v2 (the single diff)

These are the system prompts `decide()` loads by label. **The only difference between them is how the financed amount is computed** — v2 adds the grant. Everything else is byte-identical, so the demo's "only the prompt changed" claim is literally true. Register both at seed time (or author v2 live in the UI for the reveal), and inject `{{grant_date}}` so it equals the seeded effective date (`grant_effective_day_offset`).

### `credit_decision.v1.txt` (stale)
```
You are the credit-decision agent for an auto-loan provider. For each application
you receive structured data and must return a single approve/reject decision.

INPUT (provided in the user message as JSON):
- approved_line_eur : the applicant's pre-approved credit line
- vehicle           : { type, list_price_eur }     # type is BEV | PHEV | ICE
- application_date

POLICY:
- The amount to finance (financed_principal_eur) is the vehicle's list price.
  Set applied_grant_eur to 0.
- Approve if financed_principal_eur <= approved_line_eur. Otherwise reject.
- In `reason`, state the figures that drove the decision, in one sentence.

OUTPUT - respond with ONLY this JSON object and nothing else:
{
  "decision": "approve" | "reject",
  "list_price_eur": <int>,
  "applied_grant_eur": <int>,
  "financed_principal_eur": <int>,
  "approved_line_eur": <int>,
  "reason": "<one sentence>"
}
```

### `credit_decision.v2.txt` (fixed — adds the grant clause)
```
You are the credit-decision agent for an auto-loan provider. For each application
you receive structured data and must return a single approve/reject decision.

INPUT (provided in the user message as JSON):
- approved_line_eur : the applicant's pre-approved credit line
- vehicle           : { type, list_price_eur }     # type is BEV | PHEV | ICE
- application_date

POLICY:
- Determine any point-of-sale purchase grant the vehicle qualifies for, record it
  in applied_grant_eur, and set financed_principal_eur = list price - applied grant.
    EV Purchase Grant (effective {{grant_date}}): battery-electric vehicles (BEV)
    with list_price_eur <= 50000 qualify for a EUR 6,000 grant deducted at point of
    sale. Non-BEV vehicles, or BEVs priced above EUR 50,000, qualify for no grant
    (applied_grant_eur = 0).
- Approve if financed_principal_eur <= approved_line_eur. Otherwise reject.
- In `reason`, state the figures that drove the decision, in one sentence.

OUTPUT - respond with ONLY this JSON object and nothing else:
{
  "decision": "approve" | "reject",
  "list_price_eur": <int>,
  "applied_grant_eur": <int>,
  "financed_principal_eur": <int>,
  "approved_line_eur": <int>,
  "reason": "<one sentence>"
}
```

### The diff
Only the first POLICY bullet changes:
- **v1:** `financed_principal = list price`; `applied_grant = 0`.
- **v2:** `financed_principal = list price - qualifying point-of-sale grant`; the EV Purchase Grant gives EUR 6,000 to BEVs <= EUR 50,000.

### Why these exact rules produce the demo
| Application | v1 (stale) | v2 (fixed) | Judge on v2 |
|---|---|---|---|
| BEV EUR 42k, line EUR 40k (eligible, borderline) | reject (42k > 40k) | **approve** (36k <= 40k) | PASS |
| BEV EUR 58k, line EUR 55k (over cap) | reject | reject (no grant) | PASS |
| PHEV EUR 42k, line EUR 40k (not BEV) | reject | reject (no grant) | PASS |

The eligible borderline row is the false negative the demo fixes; the other two are the controls that prove the judge reasons rather than rubber-stamps. Seed the disputed window with several borderline-eligible applications plus a couple of each control type.

---

## 18. Generated demo script (the runbook)

`synth seed` emits a `DEMO_SCRIPT.md` (regenerable with `synth script`) — a presenter's runbook **filled with this run's real anchors**, so it can never drift from the seeded data. It's generated from the same config + seed state, so re-seeding regenerates a matching script.

What it carries, resolved to concrete values:
- **Pre-flight:** target instance/project, seeded counts, the grant effective date and drift window, and a reminder that the judge is created once in the UI.
- **The beats, with live anchors:**
  1. Dashboard — deep link to the `user_disagreement` drift over the last N days; note `answer_quality` / `tone` stayed green.
  2. Open disputed trace `<real id>` (e.g. applicant `anon_0421`, BEV EUR 42k, line EUR 40k): the rejection reads fine, no grant applied, generation linked to prompt **v1**.
  3. Create the managed judge — the exact prompt to paste (§16), the variable mappings, the scope to set; run on recent traces -> **red**.
  4. Open dataset `ev-grant-disputed-rejections`; add the **reserved** false-negative (trace `<real id>`, applicant `<id>`) from traces — map input only.
  5. Author prompt **v2** (or reveal the pre-registered one); show the one-clause diff (§17).
  6. Run `synth experiment`; open the dataset run; the same judge (scoped to dataset runs) scores **green**; open the comparison view.
  7. The landing line (the talk track).
- **Break-glass fallback:** if a live step misbehaves, a pre-registered v2 + a pre-run experiment let you jump straight to the green comparison — the script names those fallback IDs.
- **Reset:** how to spin up a fresh project for the next run (teardown is project-level, §12).

Implementation: a `templates/demo_script.md.j2` the builder fills from run state (dates, IDs, deep links, figures, the judge prompt). The talk-track prose is fixed; only the anchors are injected — so the wording stays polished while the IDs stay accurate.
