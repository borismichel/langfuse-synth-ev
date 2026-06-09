# Post-Seed Verification

After `synth seed` finishes, confirm the data actually matches the demo narrative
before you rely on it in a workshop. Two layers:

1. **`synth verify`** — automated golden-path assertions (run this always).
2. **Live spot-checks** — a small script that prints coverage, the `disputed`↔judge
   alignment, prompt versions, and the drift curve (run when you want the full picture).

> **Async indexing note.** Langfuse writes to ClickHouse asynchronously, so trace/score
> **counts can lag a few seconds–minutes** behind the import, and the v2 query API may
> briefly return `500` under load right after a big seed. If counts read slightly low or
> a call errors, wait and re-run — the numbers converge to the spool's exact figures.

Both layers read credentials from `.env` (`LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`). Run everything from the repo root.

---

## 1. `synth verify` (always run this)

```bash
synth verify --config config/demo.yaml
```

Expected — **all checks PASS**:

```
[PASS] dataset_items: 24 items (expected 24); 24 carry sourceTraceId
[PASS] reserved_pool: 3/3 reserved traces exist; 0 leaked into dataset
[PASS] disagreement_drift: appeal rate baseline=0.02 -> drift=0.27 (... before / ... during)
[PASS] quality_green: answer_quality mean in drift window = 0.86 over ... scores
[PASS] prompt_v1_linkage: trace ... decision generations linked to credit_decision v1: True
✓ ALL CHECKS PASSED
```

What each check guarantees:

| Check | Asserts |
|---|---|
| `dataset_items` | The hosted dataset has the expected item count and every item links back to a `sourceTraceId`. |
| `reserved_pool` | The live-add cases exist as traces but are **not** in the dataset (kept fresh for the demo). |
| `disagreement_drift` | The appeal rate is **higher in the drift window** than the baseline before it. |
| `quality_green` | `answer_quality` stays **green** in that same window — the failure is silent. |
| `prompt_v1_linkage` | The disputed `decision` generations link to `credit_decision` **v1**. |

If `verify` fails, stop and fix before the workshop — the live spot-checks below help locate why.

---

## 2. Live spot-checks (optional, fuller picture)

Save as `scripts/check_seed.py` (or run inline) and execute with the project's `.venv`:

```python
import os, time, collections, requests
from dotenv import load_dotenv

load_dotenv()  # reads .env from the repo root
BASE = os.environ["LANGFUSE_BASE_URL"].rstrip("/")
AUTH = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])

def get(path, **params):
    for attempt in range(5):                       # retry: CH can 500 right after a big import
        r = requests.get(f"{BASE}{path}", params=params, auth=AUTH, timeout=30)
        if r.status_code == 500:
            time.sleep(2 * (attempt + 1)); continue
        r.raise_for_status(); return r.json()
    r.raise_for_status()

def score_count(name):
    return get("/api/public/v2/scores", name=name, limit=1)["meta"]["totalItems"]

def all_scores(name):
    out, p = [], 1
    while True:
        d = get("/api/public/v2/scores", name=name, limit=100, page=p)
        out += d["data"]
        if p >= d["meta"]["totalPages"] or not d["data"]: break
        p += 1
    return out

traces = get("/api/public/traces", limit=1)["meta"]["totalItems"]
print(f"traces: {traces}\n")

print("score coverage (of all traces):")
for s in ["format_compliance", "answer_quality", "tone", "user_disagreement", "csat"]:
    c = score_count(s)
    print(f"  {s:<18} {c:>5}  ({c / traces * 100:4.0f}%)")

dis = all_scores("user_disagreement")
true = sum(1 for x in dis if float(x.get("value") or 0) == 1)
disputed = get("/api/public/traces", tags="disputed", limit=1)["meta"]["totalItems"]
print(f"\nuser_disagreement: {true} true / {len(dis)} judged")
print(f"disputed-tagged traces: {disputed}   (tag == judge-true? {disputed == true})")

pr = get("/api/public/v2/prompts", name="credit_decision", limit=5)["data"]
print(f"credit_decision versions: {[x.get('versions') for x in pr]}")

aq = all_scores("answer_quality")
by_d = collections.defaultdict(list); by_q = collections.defaultdict(list)
for x in dis: by_d[x["timestamp"][:10]].append(float(x.get("value") or 0))
for x in aq:  by_q[x["timestamp"][:10]].append(float(x.get("value") or 0))
print("\ndrift (appeal rate should rise to demo day; quality stays green):")
for day in sorted(set(by_d) | set(by_q))[-8:]:
    ar = sum(by_d[day]) / len(by_d[day]) if by_d.get(day) else 0
    qm = sum(by_q[day]) / len(by_q[day]) if by_q.get(day) else 0
    print(f"  {day}  appeals_n={len(by_d.get(day, [])):>3}  appeal_rate={ar:.2f}  quality={qm:.2f}")
```

```bash
.venv/bin/python scripts/check_seed.py
```

---

## What "good" looks like

Coverage follows the **kind** of instrument (see `config/demo.yaml` → `scoring`), not one
blanket ratio. With the default config:

| Score | Expected coverage | Why |
|---|---|---|
| `format_compliance` | **~100%** of traces | deterministic schema check (`format_check_coverage: 1.0`) |
| `answer_quality` + `tone` | **~15%** (`quality_judge_ratio`) | one LLM-judge pass, thin sample — counts move together |
| `user_disagreement` | **~15%** (`disagreement_judge_ratio`) | LLM-judge over the interaction; forced true on the disputed FNs |
| `csat` | **~30% of sessions** (`csat_response_ratio`) | per-session customer survey |

Key invariants:

- **`disputed` tag count == `user_disagreement` true count.** The tag is a pure *output*
  of the disagreement judge — every flagged-true trace is tagged, and nothing else is.
  (Typically ~42: the 32 golden false-negatives forced true, plus organic ambient pushback.)
- **`credit_decision versions: [1, 2]`** — pristine. If you see `[1, 2, 3, 4, …]`, the
  prompt was registered more than once (see Troubleshooting).
- **Drift:** `appeal_rate` is ~0 before the window and **rises toward demo day** (peak
  ~0.4 on the most recent full day), while `quality` holds ~0.85–0.87 throughout. That
  divergence — appeals climbing while quality stays green — *is* the demo's smoke.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Counts read slightly low (e.g. 3,989 vs 4,000) or a query `500`s | ClickHouse async-indexing lag right after import. Wait a moment and re-run. |
| `credit_decision versions: [1, 2, 3, 4]` | Prompt registered by more than one seed. Registration is idempotent on content, so it can't *reset* — seed a **fresh project** for pristine `v1=1 / v2=2`. |
| `disputed` count ≠ `user_disagreement` true count | The tag is applied at generation from the judge verdict; a mismatch means a code change broke that coupling — re-check `run.py` (`disagreement_score` → tag). |
| `disagreement_drift` fails / curve looks flat | Drift signal too thin. Raise `disagreement_judge_ratio` (or check the eligible FNs are landing in the window). |
| Re-seeding the **same** project shows stale/extra scores | Ingestion is append-only and never deletes. Changing coverage (which scores get emitted) requires a **fresh project**, or old scores linger as orphans. |

---

## Reset for a clean run

The seed is deterministic, but Langfuse data is append-only within its merge window, so the
clean-slate path is **project-level**: create a fresh project (name must contain the
`project_hint`, default `demo`), put its keys in `.env`, and run `synth seed` once.
