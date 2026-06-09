"""Build one trace's full event tree (spec §5 template), backdated.

    trace: credit_agent.assess_application
     ├─ generation: plan                 (Opus  — ~25% of traces, the ambiguous ones)
     ├─ span: load_application
     │    └─ generation: extract_fields  (Haiku)
     ├─ span: retrieve_policy            (vector_search — no model)
     ├─ span: check_subsidy_eligibility  (tool — load-bearing for §7)
     ├─ span: compute_affordability      (tool)
     ├─ generation: decision             (Sonnet — decide(), links to prompt v1)
     └─ generation: explain              (Haiku)

Timestamps walk a cursor forward from the trace timestamp; trace latency is the
critical-path sum (latency = endTime - startTime). In the stale-grant window the
agent skips/ignores ``check_subsidy_eligibility`` so ``compute_affordability`` runs on
the gross price — the mechanism of the silent regression (§7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..config import Config
from ..content import explain_io, extract_io, model_label, plan_io, retrieve_io
from ..distributions import sample_latency_ms, sample_tokens, tool_latency_ms
from ..models import Application, Decision
from ..pricing import cost_details, usage_details
from ..rng import Rng
from .events import event_event, generation_event, span_event, trace_event

TRACE_NAME = "credit_agent.assess_application"


@dataclass
class TraceSpec:
    trace_id: str
    timestamp: datetime
    application: Application
    decision: Decision
    user_id: str
    session_id: str | None
    environment: str
    kind: str  # ambient | golden_eligible | control_overcap | control_phev
    stale_grant_window: bool = False  # agent ignores the (now-active) subsidy
    plan_step: bool = False
    slow_factor: float = 1.0
    error_step: str | None = None  # tool name to fail (ambient error burst)
    decision_obs_id: str = ""  # filled during build, used to attach scores
    tags: list[str] = field(default_factory=list)


class _Cursor:
    def __init__(self, start: datetime):
        self.t = start

    def advance(self, ms: int) -> tuple[datetime, datetime]:
        s = self.t
        e = s + timedelta(milliseconds=ms)
        self.t = e
        return s, e


def build_trace_events(rng: Rng, cfg: Config, spec: TraceSpec, prompt_v1_version: int | None) -> list[dict]:
    r = rng.sub("trace", spec.trace_id)
    app = spec.application
    env = spec.environment
    tid = spec.trace_id
    cur = _Cursor(spec.timestamp)
    events: list[dict] = []

    opus = cfg.model_by_role("plan")
    sonnet = cfg.model_by_role("work")
    haiku = cfg.model_by_role("light")

    # -- trace shell ------------------------------------------------------
    tags = list(spec.tags)
    if spec.environment == "staging":
        tags.append("staging")

    # -- optional plan generation (Opus) ----------------------------------
    if spec.plan_step:
        s, e = cur.advance(sample_latency_ms(r, "plan", spec.slow_factor))
        inp, outp = plan_io(app)
        it, ot = sample_tokens(r, "plan")
        events.append(generation_event(
            obs_id=r.obs_id("plan", tid), trace_id=tid, name="plan", start=s, end=e,
            model=opus.name, usage_details=usage_details(it, ot),
            cost_details=cost_details(opus, it, ot), environment=env,
            input=inp, output=outp, model_parameters={"temperature": 0.3}))

    # -- load_application span + extract_fields generation ----------------
    s_load, _ = cur.advance(0)  # span wraps the extract gen
    s, e = cur.advance(sample_latency_ms(r, "light", spec.slow_factor))
    ein, eout = extract_io(app)
    it, ot = sample_tokens(r, "light")
    load_id = r.obs_id("load", tid)
    events.append(span_event(obs_id=load_id, trace_id=tid, name="load_application",
                             start=s_load, end=e, environment=env,
                             input={"raw": ein["raw_application"]}, output=eout))
    events.append(generation_event(
        obs_id=r.obs_id("extract", tid), trace_id=tid, name="extract_fields", start=s, end=e,
        parent_id=load_id, model=haiku.name, usage_details=usage_details(it, ot),
        cost_details=cost_details(haiku, it, ot), environment=env, input=ein, output=eout,
        metadata={"vehicle_model": model_label(r, app.vehicle.type)}))

    # -- retrieve_policy span (vector search, no model) -------------------
    s, e = cur.advance(tool_latency_ms(r, 180, 0.5, spec.slow_factor))
    rq, rdocs = retrieve_io()
    events.append(span_event(obs_id=r.obs_id("retrieve", tid), trace_id=tid, name="retrieve_policy",
                             start=s, end=e, environment=env, input=rq,
                             output={"documents": rdocs}, metadata={"retriever": "vector_search"}))

    # -- check_subsidy_eligibility span (tool, load-bearing) --------------
    fail_here = spec.error_step == "check_subsidy_eligibility"
    s, e = cur.advance(tool_latency_ms(r, 90, 0.4, spec.slow_factor))
    if spec.stale_grant_window:
        elig_out = {"applicable_subsidies": [], "note": "no subsidy programs configured for this policy version"}
    else:
        elig_out = {"applicable_subsidies": [], "note": "no active subsidy at application date"}
    events.append(span_event(
        obs_id=r.obs_id("eligib", tid), trace_id=tid, name="check_subsidy_eligibility",
        start=s, end=e, environment=env, input={"vehicle": app.vehicle.model_dump()},
        output=elig_out, level="ERROR" if fail_here else None,
        status_message="subsidy service timeout" if fail_here else None,
        metadata={"tool": "subsidy_lookup", "ignored_by_agent": spec.stale_grant_window}))

    # -- compute_affordability span (tool) --------------------------------
    fail_aff = spec.error_step == "compute_affordability"
    s, e = cur.advance(tool_latency_ms(r, 70, 0.4, spec.slow_factor))
    events.append(span_event(
        obs_id=r.obs_id("afford", tid), trace_id=tid, name="compute_affordability",
        start=s, end=e, environment=env,
        input={"financed_principal_eur": spec.decision.financed_principal_eur,
               "approved_line_eur": app.approved_line_eur},
        output={"within_line": spec.decision.financed_principal_eur <= app.approved_line_eur},
        level="ERROR" if fail_aff else None,
        status_message="affordability engine error" if fail_aff else None))

    # -- decision generation (Sonnet) — decide(), links to prompt v1 ------
    s, e = cur.advance(sample_latency_ms(r, "work", spec.slow_factor))
    it, ot = sample_tokens(r, "work")
    dec_id = r.obs_id("decision", tid)
    spec.decision_obs_id = dec_id
    events.append(generation_event(
        obs_id=dec_id, trace_id=tid, name="decision", start=s, end=e, model=sonnet.name,
        usage_details=usage_details(it, ot), cost_details=cost_details(sonnet, it, ot),
        environment=env, input=app.model_dump(), output=spec.decision.model_dump(),
        model_parameters={"temperature": 0},
        prompt_name=cfg.golden_path.prompt_name if prompt_v1_version else None,
        prompt_version=prompt_v1_version))

    # discrete marker: cache hit on policy retrieval, sometimes
    if r.chance(0.3):
        events.append(event_event(obs_id=r.obs_id("cache", tid), trace_id=tid,
                                  name="policy_cache_hit", start=s, environment=env,
                                  metadata={"layer": "policy"}))

    # -- explain generation (Haiku) ---------------------------------------
    s, e = cur.advance(sample_latency_ms(r, "light", spec.slow_factor))
    approved = spec.decision.decision == "approve"
    ein2, eout2 = explain_io(r, approved)
    it, ot = sample_tokens(r, "light")
    events.append(generation_event(
        obs_id=r.obs_id("explain", tid), trace_id=tid, name="explain", start=s, end=e,
        model=haiku.name, usage_details=usage_details(it, ot),
        cost_details=cost_details(haiku, it, ot), environment=env, input=ein2, output=eout2))

    # -- trace shell (timestamp at start; carries final IO) ---------------
    events.insert(0, trace_event(
        trace_id=tid, timestamp=spec.timestamp, name=TRACE_NAME, user_id=spec.user_id,
        session_id=spec.session_id, tags=tags or None, environment=env,
        input=app.model_dump(), output=spec.decision.model_dump(),
        metadata={"kind": spec.kind, "vehicle_type": app.vehicle.type,
                  "stale_grant_window": spec.stale_grant_window}))
    return events
