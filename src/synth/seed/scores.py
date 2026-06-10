"""Scores & configs (spec §6).

Coverage follows the *kind* of instrument, not one blanket ratio:
- ``format_compliance`` is a **deterministic** schema check — cheap, so it runs on
  **every** trace (sampling a rule check is the giveaway it's fake).
- ``answer_quality`` / ``tone`` are an **LLM-judge** pass — graded on a thin sample,
  and they stay **green** through the golden-path window (the rejections read fine;
  they're just *wrong*).
- ``user_disagreement`` is an **LLM-judge** over the interaction that flags customer
  pushback — sampled, and **forced true on the disputed false-negatives** so the
  appeal rate **drifts** in the window. Its verdict drives the ``disputed`` tag.
- ``csat`` is a per-session **customer survey** — present at a response rate, not a grade.
  Disputed false-negatives answer at double the rate and angrily (~2.0 vs ~4.1), so CSAT
  visibly breaks down in the drift window — the business-side smoke the analytics
  dashboard (``/analytics`` in the playground) reports to AI Engineering.
- There is **no** score for decision-correctness-under-the-new-grant. That gap is the
  whole point — it's what the managed judge in §7 fills, live, during the demo.

Configs are created first (so scores are comparable).
"""
from __future__ import annotations

from datetime import datetime

from ..rng import Rng
from .events import score_event

# Score configs to create up front (POST /api/public/score-configs). The decision-
# correctness judge is deliberately ABSENT here — it is created live in the UI (§7).
SCORE_CONFIGS: list[dict] = [
    {"name": "answer_quality", "dataType": "NUMERIC", "minValue": 0, "maxValue": 1,
     "description": "LLM-as-judge response quality (well-reasoned, on-task). Stays green in the golden path."},
    {"name": "tone", "dataType": "CATEGORICAL",
     "categories": [{"label": "positive", "value": 2}, {"label": "neutral", "value": 1},
                    {"label": "negative", "value": 0}],
     "description": "Customer-facing tone of the rationale."},
    {"name": "format_compliance", "dataType": "CATEGORICAL",
     "categories": [{"label": "pass", "value": 1}, {"label": "fail", "value": 0}],
     "description": "Decision output conforms to the required JSON schema."},
    {"name": "user_disagreement", "dataType": "BOOLEAN",
     "description": "LLM-judge over the interaction: did the customer push back on the decision? Drives the 'disputed' tag; drifts in the golden path."},
    {"name": "csat", "dataType": "NUMERIC", "minValue": 1, "maxValue": 5,
     "description": "Per-session customer satisfaction rollup."},
]


def format_compliance_score(rng: Rng, trace_id: str, ts: datetime, environment: str) -> list[dict]:
    """Deterministic schema check — runs on EVERY trace. Almost always pass."""
    s = rng.sub("fmtscore", trace_id)
    fmt = s.choices(["pass", "fail"], [0.98, 0.02], k=1)[0]
    return [score_event(score_id=s.score_id("fmt", trace_id), name="format_compliance",
                        value=fmt, data_type="CATEGORICAL", timestamp=ts, trace_id=trace_id,
                        environment=environment)]


def quality_judge_scores(rng: Rng, trace_id: str, decision_obs_id: str, ts: datetime,
                         environment: str, sample_ratio: float) -> list[dict]:
    """LLM-judge pass (answer_quality + tone), bundled, on a thin sample. Always green."""
    s = rng.sub("qscore", trace_id)
    if not s.chance(sample_ratio):
        return []
    events = []
    # answer_quality: green, gently varying
    aq = round(min(0.99, max(0.55, s.gauss(0.86, 0.06))), 3)
    events.append(score_event(score_id=s.score_id("aq", trace_id), name="answer_quality",
                              value=aq, data_type="NUMERIC", timestamp=ts, trace_id=trace_id,
                              observation_id=decision_obs_id, environment=environment))
    # tone: mostly positive/neutral
    tone = s.choices(["positive", "neutral", "negative"], [0.6, 0.37, 0.03], k=1)[0]
    events.append(score_event(score_id=s.score_id("tone", trace_id), name="tone",
                              value=tone, data_type="CATEGORICAL", timestamp=ts, trace_id=trace_id,
                              environment=environment))
    return events


def disagreement_score(rng: Rng, trace_id: str, ts: datetime, environment: str,
                       disagree_rate: float, sample_ratio: float,
                       force: bool = False, force_disagree: bool = False,
                       comment: str | None = None) -> tuple[list[dict], bool]:
    """LLM-judge that flags customer pushback. Returns ``(events, disagree)`` so the caller
    can apply the ``disputed`` tag when the verdict is true.

    ``force`` guarantees the judge ran (used on the disputed cases); ``force_disagree``
    pins the verdict to true (the false-negatives are the cases customers contest); ``comment``
    is the customer's actual pushback (the judge quotes it) — defaults to a generic note."""
    s = rng.sub("dscore", trace_id)
    if not force and not s.chance(sample_ratio):
        return [], False
    disagree = True if force_disagree else s.chance(disagree_rate)
    note = (comment or "customer pushed back in chat") if disagree else None
    ev = score_event(score_id=s.score_id("disagree", trace_id), name="user_disagreement",
                     value=1 if disagree else 0, data_type="BOOLEAN", timestamp=ts,
                     trace_id=trace_id, environment=environment, comment=note)
    return [ev], disagree


def csat_score(rng: Rng, session_id: str, ts: datetime, environment: str,
               dissatisfied: bool = False) -> dict:
    s = rng.sub("csat", session_id)
    mu, sigma = (2.0, 0.6) if dissatisfied else (4.1, 0.7)
    val = round(min(5.0, max(1.0, s.gauss(mu, sigma))), 1)
    return score_event(score_id=s.score_id("csat", session_id), name="csat", value=val,
                       data_type="NUMERIC", timestamp=ts, session_id=session_id,
                       environment=environment)


def csat_events(rng: Rng, specs, sessions: dict[str, list[str]],
                response_ratio: float):
    """Every per-session csat survey for a plan, in one place (seed AND the analytics
    dashboard derive from this, so they can never disagree).

    Multi-turn sessions respond at ``response_ratio`` with the healthy ~4.1 mean. The
    disputed false-negatives' sessions are surveyed too — wrongly rejected customers
    answer at double the rate (angry customers always take the survey) and angrily
    (~2.0) — which is what makes CSAT visibly break down in the drift window."""
    spec_by_id = {s.trace_id: s for s in specs}
    for sid, trace_ids in sessions.items():
        members = [spec_by_id[t] for t in trace_ids if t in spec_by_id]
        if not members:
            continue
        if not rng.sub("csatsample", sid).chance(response_ratio):
            continue
        last = max(members, key=lambda s: s.timestamp)
        yield csat_score(rng, sid, last.timestamp, last.environment)
    for s in specs:
        if s.kind != "golden_eligible" or not s.session_id:
            continue
        if not rng.sub("csatsample", s.session_id).chance(min(1.0, response_ratio * 2)):
            continue
        yield csat_score(rng, s.session_id, s.timestamp, s.environment, dissatisfied=True)
