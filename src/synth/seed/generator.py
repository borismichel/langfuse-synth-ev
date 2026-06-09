"""Assemble the full run plan: ambient traffic + sessions + users + incidents + golden path.

Deterministic from ``(config, seed, run_date)``. Produces a ``Plan`` of ``TraceSpec``s
the seeder turns into events, plus the golden-path object (dataset + reserved set) and a
summary for ``synth plan``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..agent import decide
from ..config import Config
from ..content import ambient_application, user_population
from ..rng import Rng
from ..timegen import day_anchor, iso_date, sample_timestamps, window_start
from . import golden_path as gp_mod
from .golden_path import GoldenPath
from .traces import TraceSpec


@dataclass
class Plan:
    cfg: Config
    run_date: datetime
    rng: Rng
    golden: GoldenPath
    specs: list[TraceSpec] = field(default_factory=list)        # all traces (ambient + golden)
    ambient_specs: list[TraceSpec] = field(default_factory=list)
    sessions: dict[str, list[str]] = field(default_factory=dict)  # sessionId -> trace ids (multi-turn)
    users: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def build_plan(cfg: Config, run_date: datetime) -> Plan:
    rng = Rng(cfg.generation.seed)
    users = user_population(rng, cfg.generation.population.users,
                            cfg.generation.population.power_user_share)

    if cfg.golden_path.enabled:
        golden = gp_mod.build(cfg, run_date, rng, users, id_start=0)
    else:
        golden = GoldenPath(effective_date=run_date, drift_start=run_date,
                            drift_end=run_date, rule=None)  # type: ignore[arg-type]

    n_golden = len(golden.disputed_specs)
    n_ambient = max(0, cfg.generation.total_traces - n_golden)

    ambient = _build_ambient(cfg, run_date, rng, users, golden, n_ambient)
    _assign_sessions(cfg, rng, ambient)
    _apply_incidents(cfg, run_date, rng, ambient)

    plan = Plan(cfg=cfg, run_date=run_date, rng=rng, golden=golden,
                ambient_specs=ambient, users=users)
    plan.specs = ambient + golden.disputed_specs
    plan.sessions = _collect_sessions(plan.specs)
    plan.summary = _summarise(cfg, run_date, plan)
    return plan


def _build_ambient(cfg: Config, run_date: datetime, rng: Rng, users: list[dict],
                   golden: GoldenPath, n: int) -> list[TraceSpec]:
    r = rng.sub("ambient")
    times = sample_timestamps(r, run_date, cfg.generation.window_days, n)
    weights = [u["weight"] for u in users]
    prod_share = cfg.generation.environments.production_share
    rule = golden.rule

    specs: list[TraceSpec] = []
    base_id = golden.next_id  # continue the applicant-id sequence after golden block
    for i, ts in enumerate(times):
        nid = base_id + i
        app, _ = ambient_application(r, nid, iso_date(ts))
        dec = decide(app, "v1", rule=rule) if rule else decide(app, "v1")
        user = r.choices(users, weights, k=1)[0]
        env = "production" if r.chance(prod_share) else "staging"
        specs.append(TraceSpec(
            trace_id=r.trace_id("ambient", nid), timestamp=ts, application=app, decision=dec,
            user_id=user["userId"], session_id=None, environment=env, kind="ambient",
            plan_step=r.chance(cfg.model_mix.plan_step_share)))
    return specs


def _assign_sessions(cfg: Config, rng: Rng, specs: list[TraceSpec]) -> None:
    """Mix single-turn and multi-turn (spec §8). Every trace gets a sessionId; multi-turn
    runs share one across 2-4 consecutive traces under the same (first) user."""
    r = rng.sub("sessions")
    ratio = cfg.generation.population.multi_turn_ratio
    specs_sorted = sorted(specs, key=lambda s: s.timestamp)
    i = 0
    while i < len(specs_sorted):
        s = specs_sorted[i]
        if i + 1 < len(specs_sorted) and r.chance(ratio):
            length = r.randint(2, 4)
            group = specs_sorted[i : i + length]
            sid = r.trace_id("session", s.trace_id)
            for turn, g in enumerate(group):
                g.session_id = sid
                g.user_id = group[0].user_id
                g.turn_index = turn  # later turns carry more accumulated context
            i += len(group)
        else:
            s.session_id = r.trace_id("session", s.trace_id)
            i += 1


def _apply_incidents(cfg: Config, run_date: datetime, rng: Rng, specs: list[TraceSpec]) -> None:
    """Date-anchored ambient incidents (spec §7.x)."""
    r = rng.sub("incidents")
    inc = cfg.ambient_incidents

    def window(day_offset: int, hours: int) -> tuple[datetime, datetime]:
        start = day_anchor(run_date, day_offset)
        return start, start + timedelta(hours=hours)

    for s in specs:
        # cost spike: the Opus planner over-triggers within the window
        if inc.cost_spike.enabled:
            a, b = window(inc.cost_spike.day_offset, inc.cost_spike.duration_hours)
            if a <= s.timestamp < b and r.chance(0.8):
                s.plan_step = True
                s.tags = list(s.tags) + ["incident:cost_spike"]
        # latency degradation: one tool's latency triples within the window
        if inc.latency_degrade.enabled:
            a, b = window(inc.latency_degrade.day_offset, inc.latency_degrade.duration_hours)
            if a <= s.timestamp < b:
                s.slow_factor = inc.latency_degrade.factor
                s.tags = list(s.tags) + ["incident:latency_degrade"]
        # error burst: elevated tool failures within the window
        if inc.error_burst.enabled:
            a, b = window(inc.error_burst.day_offset, inc.error_burst.duration_hours)
            if a <= s.timestamp < b and r.chance(0.35):
                s.error_step = r.choice(["check_subsidy_eligibility", "compute_affordability"])
                s.tags = list(s.tags) + ["incident:error_burst"]


def _collect_sessions(specs: list[TraceSpec]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for s in specs:
        if s.session_id:
            out.setdefault(s.session_id, []).append(s.trace_id)
    return {k: v for k, v in out.items() if len(v) > 1}  # multi-turn only


def _summarise(cfg: Config, run_date: datetime, plan: Plan) -> dict:
    g = plan.golden
    by_env: dict[str, int] = {}
    plan_steps = 0
    errored = 0
    for s in plan.specs:
        by_env[s.environment] = by_env.get(s.environment, 0) + 1
        plan_steps += 1 if s.plan_step else 0
        errored += 1 if s.error_step else 0
    return {
        "run_date": run_date.isoformat(),
        "window_start": window_start(run_date, cfg.generation.window_days).isoformat(),
        "total_traces": len(plan.specs),
        "ambient_traces": len(plan.ambient_specs),
        "golden_disputed_traces": len(g.disputed_specs),
        "golden_eligible_false_negatives": len(g.disputed_trace_ids),
        "multi_turn_sessions": len(plan.sessions),
        "by_environment": by_env,
        "traces_with_plan_step": plan_steps,
        "traces_with_error": errored,
        "grant_effective_date": iso_date(g.effective_date),
        "drift_window": f"{iso_date(g.drift_start)} .. {iso_date(g.drift_end)}",
        "dataset_name": cfg.golden_path.dataset.name,
        "dataset_items": len(g.dataset_plan),
        "dataset_eligible_items": sum(1 for it in g.dataset_plan if it.eligible),
        "dataset_control_items": sum(1 for it in g.dataset_plan if not it.eligible),
        "reserved_for_live_add": len(g.reserved_trace_ids),
    }
