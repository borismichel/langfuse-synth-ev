"""The analytics dashboard must tell the golden-path story from the deterministic plan:
business metrics break in the drift window while the AI quality monitors stay green."""
from datetime import datetime, timezone

from synth.config import load_config
from synth.live.dashboard import build_series

RUN_DATE = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


def _series():
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 800
    return cfg, build_series(cfg, RUN_DATE)


def test_business_metrics_break_in_drift_window():
    _, s = _series()
    ab, ad = s.appeal_rate
    assert ad > ab and ad > 0.2          # appeals climb
    cb, cd = s.csat_avg
    assert cb - cd > 0.5                 # CSAT breaks down
    bb, bd = s.bev_approval
    assert bb - bd > 0.1                 # eligible-BEV approval rate drops
    assert s.lost_volume_eur > 0 and s.n_disputed > 0
    assert "grant" in s.appeal_quote.lower() or "€" in s.appeal_quote


def test_ai_monitors_stay_green():
    _, s = _series()
    qb, qd = s.quality_avg
    assert qd >= 0.8 and abs(qd - qb) < 0.05   # answer_quality flat and green
    fb, fd = s.fmt_rate
    assert fd >= 0.95                           # format compliance green


def test_csat_breakdown_comes_from_seeded_surveys():
    """The dashboard replays the same csat_events generator the seeder ingests —
    the dissatisfied surveys land on the disputed FNs' sessions in the drift window."""
    cfg, s = _series()
    drift_days = [d for d in s.days if d.day >= s.drift_start]
    angry = [v for d in drift_days for v in d.csat if v <= 3.0]
    assert angry, "expected dissatisfied surveys in the drift window"
