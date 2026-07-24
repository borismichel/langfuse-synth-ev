"""The flagship narrative — the EV-subsidy regression (spec §7).

Fabricates the "before" state: a recent drift window where, among eligible borderline
applicants, the agent rejects on gross price (v1, stale prompt) — semantically real,
well-reasoned rejections that never mention the grant. Plus correct-rejection controls.

Produces:
- ``disputed_specs``  — backdated traces (eligible false-negatives + controls), all
  in the drift window, all with the decision generation linked to prompt v1.
- ``dataset_plan``    — the ``ev-grant-disputed-rejections`` items: ~70% eligible
  false-negatives + correct-rejection controls, each with ``expectedOutput`` = the
  *correct* (v2) decision and a ``sourceTraceId``.
- ``reserved_trace_ids`` — eligible false-negatives deliberately LEFT OUT of the
  dataset, so the presenter can add a fresh current case live (spec §7, step 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..agent import GrantRule, decide
from ..config import Config
from ..content import (
    control_overcap_application,
    control_phev_application,
    eligible_borderline_application,
)
from ..models import Application, Decision
from langfuse_synth_core.rng import Rng
from langfuse_synth_core.timegen import day_anchor, iso_date, sample_in_range
from .traces import TraceSpec


@dataclass
class DatasetItemPlan:
    item_id: str
    source_trace_id: str
    application: Application
    expected: Decision  # the correct (v2) decision
    eligible: bool
    borderline: bool
    scenario: str  # false_negative | control_overcap | control_phev


@dataclass
class GoldenPath:
    effective_date: datetime
    drift_start: datetime
    drift_end: datetime
    rule: GrantRule
    disputed_specs: list[TraceSpec] = field(default_factory=list)
    dataset_plan: list[DatasetItemPlan] = field(default_factory=list)
    reserved_trace_ids: list[str] = field(default_factory=list)
    disputed_trace_ids: list[str] = field(default_factory=list)  # eligible FNs (all)
    next_id: int = 0  # first free applicant index after the golden-path block


def _grant_rule(cfg: Config, effective_date: datetime) -> GrantRule:
    gp = cfg.golden_path
    return GrantRule(amount_eur=gp.grant_amount_eur, price_cap_eur=gp.price_cap_eur,
                     effective_date=iso_date(effective_date))


def build(cfg: Config, run_date: datetime, rng: Rng, users: list[dict],
          id_start: int) -> GoldenPath:
    gp = cfg.golden_path
    effective_date = day_anchor(run_date, gp.grant_effective_day_offset)
    drift_start = max(
        day_anchor(run_date, -gp.drift_window_days),
        effective_date,
    )
    drift_end = run_date
    rule = _grant_rule(cfg, effective_date)
    out = GoldenPath(effective_date=effective_date, drift_start=drift_start,
                     drift_end=drift_end, rule=rule)

    r = rng.sub("golden")

    # Size the disputed pool generously so the dataset + reserved set draw from it.
    ds = gp.dataset
    n_eligible_needed = int(round(ds.n_items * ds.eligible_share)) + ds.n_reserved_for_live_add
    n_control_needed = ds.n_items - int(round(ds.n_items * ds.eligible_share))
    n_eligible = max(n_eligible_needed + 12, 30)   # extra eligible FNs as ambient drift volume
    n_overcap = max(n_control_needed, 4) + 3
    n_phev = max(n_control_needed, 4) + 3

    # The eligible false-negatives are the *only* drift signal (each forces a user
    # appeal), so ramp their timestamps UP toward run_date — the dashboard then reads
    # as "appeals climbing to today" rather than a burst that ended days ago. Controls
    # raise no appeals, so they spread evenly across the window.
    elig_times = sample_in_range(r, drift_start, drift_end, n_eligible,
                                 label="disputed_elig", ramp=0.12)
    ctrl_times = sample_in_range(r, drift_start, drift_end, n_overcap + n_phev,
                                 label="disputed_ctrl")

    # power users (loan officers) dominate the disputed volume
    officers = [u for u in users if u["is_power"]] or users
    n = id_start
    cidx = 0

    def next_officer(key) -> str:
        return r.sub("offsel", key).choice(officers)["userId"]

    # -- eligible false-negatives ----------------------------------------
    eligible_specs: list[TraceSpec] = []
    for i in range(n_eligible):
        ts = elig_times[i]
        app = eligible_borderline_application(r, n, iso_date(ts), rule)
        dec_v1 = decide(app, "v1", rule=rule)   # the wrong rejection (gross price)
        tid = r.trace_id("golden", n)
        spec = TraceSpec(
            trace_id=tid, timestamp=ts, application=app, decision=dec_v1,
            user_id=next_officer(n), session_id=r.trace_id("gsession", n),
            environment="production", kind="golden_eligible", stale_grant_window=True,
            plan_step=r.chance(0.5), tags=["ev-grant"])  # `disputed` added by the judge verdict
        eligible_specs.append(spec)
        out.disputed_specs.append(spec)
        out.disputed_trace_ids.append(tid)
        n += 1

    # -- controls: over-cap BEV + PHEV (correctly rejected under both) ----
    overcap_specs: list[TraceSpec] = []
    for _ in range(n_overcap):
        ts = ctrl_times[cidx]; cidx += 1
        app = control_overcap_application(r, n, iso_date(ts), rule)
        dec_v1 = decide(app, "v1", rule=rule)
        spec = TraceSpec(trace_id=r.trace_id("golden", n), timestamp=ts, application=app,
                         decision=dec_v1, user_id=next_officer(n),
                         session_id=r.trace_id("gsession", n), environment="production",
                         kind="control_overcap", stale_grant_window=True,
                         tags=["ev-grant", "control"])
        overcap_specs.append(spec); out.disputed_specs.append(spec); n += 1

    phev_specs: list[TraceSpec] = []
    for _ in range(n_phev):
        ts = ctrl_times[cidx]; cidx += 1
        app = control_phev_application(r, n, iso_date(ts), rule)
        dec_v1 = decide(app, "v1", rule=rule)
        spec = TraceSpec(trace_id=r.trace_id("golden", n), timestamp=ts, application=app,
                         decision=dec_v1, user_id=next_officer(n),
                         session_id=r.trace_id("gsession", n), environment="production",
                         kind="control_phev", stale_grant_window=True,
                         tags=["ev-grant", "control"])
        phev_specs.append(spec); out.disputed_specs.append(spec); n += 1

    # -- assemble the dataset + reserved pool -----------------------------
    _select_dataset(out, cfg, r, eligible_specs, overcap_specs, phev_specs)
    out.next_id = n
    return out


def _select_dataset(out: GoldenPath, cfg: Config, rng: Rng,
                    eligible: list[TraceSpec], overcap: list[TraceSpec],
                    phev: list[TraceSpec]) -> None:
    ds = cfg.golden_path.dataset
    n_eligible_items = int(round(ds.n_items * ds.eligible_share))
    n_controls = ds.n_items - n_eligible_items
    n_overcap = n_controls // 2 + (n_controls % 2)
    n_phev = n_controls // 2

    elig_sorted = sorted(eligible, key=lambda s: s.timestamp)
    # reserve the most recent eligible false-negatives for the live add (fresh cases)
    reserved = elig_sorted[-ds.n_reserved_for_live_add:] if ds.n_reserved_for_live_add else []
    out.reserved_trace_ids = [s.trace_id for s in reserved]
    reserved_ids = set(out.reserved_trace_ids)
    pool = [s for s in elig_sorted if s.trace_id not in reserved_ids]

    chosen_eligible = pool[:n_eligible_items]
    chosen_overcap = overcap[:n_overcap]
    chosen_phev = phev[:n_phev]

    def item(spec: TraceSpec, eligible_flag: bool, scenario: str) -> DatasetItemPlan:
        expected = decide(spec.application, "v2", rule=out.rule)  # the CORRECT decision
        return DatasetItemPlan(
            item_id=rng.item_id("dsitem", spec.trace_id), source_trace_id=spec.trace_id,
            application=spec.application, expected=expected, eligible=eligible_flag,
            borderline=eligible_flag, scenario=scenario)

    for s in chosen_eligible:
        out.dataset_plan.append(item(s, True, "false_negative"))
    for s in chosen_overcap:
        out.dataset_plan.append(item(s, False, "control_overcap"))
    for s in chosen_phev:
        out.dataset_plan.append(item(s, False, "control_phev"))
