"""Scores & configs (spec §6).

A spread that exercises every scoring path so eval dashboards populate. Crucially:
- ``answer_quality`` / ``tone`` / ``format_compliance`` stay **green** through the
  golden-path window — the rejections read perfectly well; they're just *wrong*.
- ``user_disagreement`` is the blunt, lagging human signal that **drifts** on the
  eligible false-negatives in the drift window.
- There is **no** score for decision-correctness-under-the-new-grant. That gap is the
  whole point — it's what the managed judge in §7 fills, live, during the demo.

Configs are created first (so scores are comparable); we score only a realistic
fraction (fully-scored data looks fake).
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
     "description": "Lagging human signal: applicant appeal / loan-officer override. Drifts in the golden path."},
    {"name": "csat", "dataType": "NUMERIC", "minValue": 1, "maxValue": 5,
     "description": "Per-session customer satisfaction rollup."},
]


def quality_scores_for_trace(rng: Rng, trace_id: str, decision_obs_id: str, ts: datetime,
                             environment: str, auto_ratio: float) -> list[dict]:
    """Auto quality/tone/format scores on a realistic fraction of traces. Always green."""
    if not rng.chance(auto_ratio):
        return []
    s = rng.sub("qscore", trace_id)
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
    # format_compliance: almost always pass
    fmt = s.choices(["pass", "fail"], [0.98, 0.02], k=1)[0]
    events.append(score_event(score_id=s.score_id("fmt", trace_id), name="format_compliance",
                              value=fmt, data_type="CATEGORICAL", timestamp=ts, trace_id=trace_id,
                              environment=environment))
    return events


def disagreement_score(rng: Rng, trace_id: str, ts: datetime, environment: str,
                       disagree_rate: float, human_ratio: float,
                       force: bool = False) -> list[dict]:
    """The lagging human signal. Emitted on a fraction of traces; elevated in the drift window.

    ``force=True`` guarantees the score exists (used so the drift is legible on the
    specific disputed traces), otherwise it appears at ``human_ratio`` coverage.
    """
    s = rng.sub("dscore", trace_id)
    if not force and not s.chance(human_ratio):
        return []
    disagree = s.chance(disagree_rate)
    return [score_event(score_id=s.score_id("disagree", trace_id), name="user_disagreement",
                        value=1 if disagree else 0, data_type="BOOLEAN", timestamp=ts,
                        trace_id=trace_id, environment=environment,
                        comment="applicant appeal" if disagree else None)]


def csat_score(rng: Rng, session_id: str, ts: datetime, environment: str) -> dict:
    s = rng.sub("csat", session_id)
    val = round(min(5.0, max(1.0, s.gauss(4.1, 0.7))), 1)
    return score_event(score_id=s.score_id("csat", session_id), name="csat", value=val,
                       data_type="NUMERIC", timestamp=ts, session_id=session_id,
                       environment=environment)
