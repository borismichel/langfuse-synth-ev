"""Langfuse Bank — internal lending-analytics dashboard (``/analytics`` in the playground).

The report that starts the investigation: the mock BI view Lending Analytics sends to
AI Engineering. Business metrics scream — appeals climbing, decision CSAT breaking
down, approval rate for eligible BEVs collapsing, financing volume walking away —
while the AI quality monitors stay green. That contradiction is the demo's opening
hook: nothing the AI team watches is red, yet the business is bleeding.

Every number is **derived from the same deterministic plan the seed ingested**: the
specs come from ``build_plan(config, run_date)`` and the score verdicts replay the
exact rng substreams the seeder drew (they're keyed by trace/session id, not draw
order). So the dashboard and the data in Langfuse always agree — drill into any
figure and the traces back it up.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ..config import Config
from ..content import customer_appeal
from ..seed.generator import Plan, build_plan
from ..seed.scores import csat_events, disagreement_score, format_compliance_score, quality_judge_scores
from ..state import RunState
from .paths import local
from .theme import page

DAYS_SHOWN = 14
TITLE = "Langfuse Bank — Lending Analytics"


# ---------------------------------------------------------------------------
# Series: replay the seed's score draws and aggregate per day
# ---------------------------------------------------------------------------
@dataclass
class Daily:
    day: date
    decisions: int = 0
    appeals: int = 0          # user_disagreement verdict true
    appeal_sampled: int = 0   # judge ran on this trace
    bev_elig: int = 0         # production decisions on BEVs at/under the price cap
    bev_elig_approved: int = 0
    csat: list[float] = field(default_factory=list)
    quality: list[float] = field(default_factory=list)
    fmt_pass: int = 0
    fmt_n: int = 0


@dataclass
class Series:
    days: list[Daily]
    drift_start: date
    lost_volume_eur: int          # financed principal of wrongly rejected eligible BEVs
    n_disputed: int
    appeal_quote: str
    # baseline vs drift-window aggregates
    appeal_rate: tuple[float, float]
    csat_avg: tuple[float, float]
    bev_approval: tuple[float, float]
    quality_avg: tuple[float, float]
    fmt_rate: tuple[float, float]


_SERIES_CACHE: dict[tuple, "Series"] = {}


def cached_series(cfg: Config, run_date: datetime) -> "Series":
    """Replaying 4k traces' draws takes a moment — derive once per (run, config)."""
    key = (run_date.isoformat(), cfg.generation.seed, cfg.generation.total_traces)
    if key not in _SERIES_CACHE:
        _SERIES_CACHE[key] = build_series(cfg, run_date)
    return _SERIES_CACHE[key]


def _rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def _avg(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def build_series(cfg: Config, run_date: datetime) -> Series:
    plan: Plan = build_plan(cfg, run_date)
    gp, sc = cfg.golden_path, cfg.scoring
    rng = plan.rng

    days = [run_date.date() - timedelta(days=i) for i in range(DAYS_SHOWN - 1, -1, -1)]
    by_day = {d: Daily(d) for d in days}

    lost = 0
    quote = ""
    for s in plan.specs:
        d = by_day.get(s.timestamp.date())
        if s.kind == "golden_eligible":
            lost += s.decision.financed_principal_eur
            if not quote:
                quote = customer_appeal(rng, s.trace_id, s.application, gp.grant_amount_eur)
        if d is None:
            continue
        d.decisions += 1
        app = s.application
        if (s.environment == "production" and app.vehicle.type == "BEV"
                and app.vehicle.list_price_eur <= gp.price_cap_eur):
            d.bev_elig += 1
            d.bev_elig_approved += s.decision.decision == "approve"
        # replay the seeder's judge draws (substreams are id-keyed, so verdicts match)
        if s.kind == "golden_eligible":
            _, dis = disagreement_score(rng, s.trace_id, s.timestamp, s.environment,
                                        gp.drift_disagreement_rate, sc.disagreement_judge_ratio,
                                        force=True, force_disagree=True)
            sampled = True
        else:
            evs, dis = disagreement_score(rng, s.trace_id, s.timestamp, s.environment,
                                          gp.baseline_disagreement_rate, sc.disagreement_judge_ratio)
            sampled = bool(evs)
        d.appeal_sampled += sampled
        d.appeals += dis
        for ev in quality_judge_scores(rng, s.trace_id, "", s.timestamp, s.environment,
                                       sc.quality_judge_ratio):
            if ev["body"]["name"] == "answer_quality":
                d.quality.append(float(ev["body"]["value"]))
        fmt = format_compliance_score(rng, s.trace_id, s.timestamp, s.environment)[0]
        d.fmt_n += 1
        d.fmt_pass += fmt["body"]["value"] == "pass"

    for ev in csat_events(rng, plan.specs, plan.sessions, sc.csat_response_ratio):
        ts = datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00"))
        d = by_day.get(ts.date())
        if d is not None:
            d.csat.append(float(ev["body"]["value"]))

    drift_start = plan.golden.drift_start.date()
    base = [d for d in days if d < drift_start]
    drift = [d for d in days if d >= drift_start]

    def agg(sel, num, den) -> tuple[float, float]:
        return (_rate(sum(num(by_day[d]) for d in sel or days), sum(den(by_day[d]) for d in sel or days)),
                _rate(sum(num(by_day[d]) for d in drift), sum(den(by_day[d]) for d in drift)))

    csat_base = [v for d in base for v in by_day[d].csat]
    csat_drift = [v for d in drift for v in by_day[d].csat]
    q_base = [v for d in base for v in by_day[d].quality]
    q_drift = [v for d in drift for v in by_day[d].quality]

    return Series(
        days=[by_day[d] for d in days],
        drift_start=drift_start,
        lost_volume_eur=lost,
        n_disputed=len(plan.golden.disputed_trace_ids),
        appeal_quote=quote,
        appeal_rate=agg(base, lambda d: d.appeals, lambda d: d.appeal_sampled),
        csat_avg=(_avg(csat_base), _avg(csat_drift)),
        bev_approval=agg(base, lambda d: d.bev_elig_approved, lambda d: d.bev_elig),
        quality_avg=(_avg(q_base), _avg(q_drift)),
        fmt_rate=agg(base, lambda d: d.fmt_pass, lambda d: d.fmt_n),
    )


# ---------------------------------------------------------------------------
# Rendering: flat inline-SVG charts on the Langfuse tokens
# ---------------------------------------------------------------------------
_W, _H, _PAD = 290, 84, 4


def _scale(vals: list[float], lo: float | None = None, hi: float | None = None):
    lo = min(vals) if lo is None else lo
    hi = max(vals) if hi is None else hi
    span = (hi - lo) or 1.0
    n = max(len(vals) - 1, 1)

    def pt(i: int, v: float) -> tuple[float, float]:
        x = _PAD + i * (_W - 2 * _PAD) / n
        y = _H - _PAD - (v - lo) / span * (_H - 2 * _PAD)
        return round(x, 1), round(y, 1)

    return pt


def _svg(inner: str) -> str:
    return (f"<svg viewBox='0 0 {_W} {_H}' preserveAspectRatio='none' "
            f"xmlns='http://www.w3.org/2000/svg'>{inner}</svg>")


def _bars(vals: list[float], color: str, mark_from: int) -> str:
    """Bar sparkline; bars from index ``mark_from`` use the alert color."""
    hi = max(vals) or 1.0
    n = len(vals)
    bw = (_W - 2 * _PAD) / n * 0.62
    step = (_W - 2 * _PAD) / n
    parts = []
    for i, v in enumerate(vals):
        h = (v / hi) * (_H - 2 * _PAD)
        x = _PAD + i * step + (step - bw) / 2
        c = color if i >= mark_from else "var(--line-structure)"
        parts.append(f"<rect x='{x:.1f}' y='{_H - _PAD - h:.1f}' width='{bw:.1f}' "
                     f"height='{max(h, 1):.1f}' rx='1.5' fill='{c}'/>")
    return _svg("".join(parts))


def _line(vals: list[float], color: str, lo: float, hi: float) -> str:
    pt = _scale(vals, lo, hi)
    pts = " ".join(f"{x},{y}" for x, y in (pt(i, v) for i, v in enumerate(vals)))
    lx, ly = pt(len(vals) - 1, vals[-1])
    grid = "".join(f"<line x1='{_PAD}' x2='{_W - _PAD}' y1='{y}' y2='{y}' "
                   f"stroke='var(--line-divider-dash)' stroke-width='1' stroke-dasharray='3 4'/>"
                   for y in (_PAD + 0.0, _H / 2, _H - _PAD))
    return _svg(grid + f"<polyline points='{pts}' fill='none' stroke='{color}' "
                       f"stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>"
                       f"<circle cx='{lx}' cy='{ly}' r='3' fill='{color}'/>")


def _kpi(label: str, value: str, delta: str, tone: str) -> str:
    return (f"<div class='kpi'><div class='klabel'>{label}</div>"
            f"<div class='kvalue'>{value}</div><div class='kdelta {tone}'>{delta}</div></div>")


def render_analytics(cfg: Config) -> str:
    if not RunState.exists():
        return page("<div class='eyebrow'>Langfuse Bank · lending analytics</div>"
                    "<div class='card'><h2>No report yet</h2><p class='sub'>Run <code>synth seed"
                    "</code> first — the report is generated from the seeded book of business."
                    "</p></div>", title=TITLE, wide=True)
    state = RunState.load()
    run_date = datetime.fromisoformat(state.run_date)
    s = cached_series(cfg, run_date)

    appeals_per_day = [d.appeals for d in s.days]
    csat_per_day = [_avg(d.csat) or None for d in s.days]
    csat_filled = [v if v is not None else (s.csat_avg[0] or 4.1) for v in csat_per_day]
    bev_per_day = [_rate(d.bev_elig_approved, d.bev_elig) * 100 for d in s.days]
    mark_from = next((i for i, d in enumerate(s.days) if d.day >= s.drift_start), len(s.days))

    ab, ad = s.appeal_rate
    cb, cd = s.csat_avg
    bb, bd = s.bev_approval
    qb, qd = s.quality_avg
    fb, fd = s.fmt_rate
    drift_days = (run_date.date() - s.drift_start).days + 1
    period = f"last {drift_days}d vs prior"

    traces_link = ""
    if state.project_id:
        traces_link = (f"<a href='{state.base_url}/project/{state.project_id}/traces' "
                       f"target='_blank'>open the decision records in Langfuse →</a>")

    body = f"""
    <div class="eyebrow">Langfuse Bank · lending analytics · internal</div>
    <h1>EV financing — <span class="mark">weekly risk report</span></h1>
    <p class="sub">Prepared by Lending Analytics for <b>AI Engineering</b> · week ending {run_date.date()} ·
      distribution: head of credit, AI platform lead</p>

    <div class="memo">
      <b>Summary.</b> Decision appeals on EV loans are climbing and decision CSAT is breaking down,
      concentrated in battery-electric applications since {s.drift_start}. The credit-decision agent's
      own quality monitors show <b>no regression</b> — whatever is wrong, our current evals don't see it.
      Requesting investigation by AI Engineering.
    </div>

    <div class="grid">
      {_kpi("Decision appeals", f"{ad:.0%}", f"▲ from {ab:.0%} of reviewed decisions · {period}", "bad")}
      {_kpi("Decision CSAT", f"{cd:.1f} / 5", f"▼ from {cb:.1f} · {period}", "bad")}
      {_kpi("Approval rate · BEV ≤ €{:,}".format(cfg.golden_path.price_cap_eur), f"{bd:.0%}",
            f"▼ from {bb:.0%} · {period}", "bad")}
      {_kpi("Financing volume walked away", f"€{s.lost_volume_eur:,.0f}",
            f"{s.n_disputed} disputed rejections, all BEV", "bad")}
      {_kpi("Agent quality eval", f"{qd:.2f}", f"flat vs {qb:.2f} baseline — green", "good")}
      {_kpi("Format compliance", f"{fd:.0%}", f"flat vs {fb:.0%} baseline — green", "good")}
    </div>

    <div class="charts">
      <div class="chart"><div class="klabel">Appeals per day · 14d</div>
        {_bars(appeals_per_day, "var(--error)", mark_from)}</div>
      <div class="chart"><div class="klabel">Decision CSAT · daily avg</div>
        {_line(csat_filled, "var(--error)", 1.0, 5.0)}</div>
      <div class="chart"><div class="klabel">BEV ≤ cap approval rate · %</div>
        {_line(bev_per_day, "var(--text-primary)", 0.0, 100.0)}</div>
    </div>

    <div class="card">
      <div class="klabel" style="font-family:var(--font-mono);font-size:10.5px;text-transform:uppercase;
        letter-spacing:.1em;color:var(--text-tertiary)">What customers say in their appeals</div>
      <p class="memo quote" style="border:0;background:none;padding:10px 0 0">“{s.appeal_quote}”</p>
      <div class="kv" style="margin-top:8px"><span>AI monitors (answer quality · tone · format)</span>
        <span><span class="chip green">all green</span></span></div>
      <div class="kv"><span>Hypothesis</span><span>none — decisions read well and pass every check we run</span></div>
      <div class="kv"><span>Action requested</span><span>AI Engineering to investigate decision correctness — {traces_link or "see Langfuse"}</span></div>
    </div>

    <a class="back" href="{local('/')}">← Langfuse Bank · loan application</a>"""
    return page(body, title=TITLE, wide=True)
