"""Build one trace's full event tree (spec §5 template), backdated.

    trace: credit_agent.assess_application
     └─ AGENT: credit_agent              (orchestrator — parents everything below)
         ├─ generation: plan             (Opus  — ~25% of traces, the ambiguous ones)
         ├─ span: load_application
         │    └─ generation: extract_fields  (Haiku)
         ├─ RETRIEVER: retrieve_policy   (vector_search — no model)
         ├─ TOOL: check_subsidy_eligibility  (load-bearing for §7)
         ├─ TOOL: compute_affordability
         ├─ generation: decision         (Sonnet — decide(), links to prompt v1; tool_calls)
         └─ generation: explain          (Haiku)

Timestamps walk a cursor forward from the trace timestamp; trace latency is the
critical-path sum (latency = endTime - startTime). In the stale-grant window the
agent skips/ignores ``check_subsidy_eligibility`` so ``compute_affordability`` runs on
the gross price — the mechanism of the silent regression (§7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..config import Config
from ..content import decision_messages, explain_io, extract_io, model_label, plan_io, retrieve_io
from ..distributions import cache_split, sample_latency_ms, sample_tokens, text_tokens, tool_latency_ms
from ..models import Application, Decision
from ..pricing import cost_details, usage_details
from ..rng import Rng
from .events import event_event, generation_event, observation_event, span_event, trace_event
from .prompts import prompt_text

TRACE_NAME = "credit_agent.assess_application"
HISTORY_TOKENS_PER_TURN = 750  # accumulated Q+A added to input per prior turn (multi-turn)


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
    turn_index: int = 0  # position within a multi-turn session (0 = first/only turn)
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


def _first_token_at(r: Rng, s: datetime, e: datetime) -> datetime:
    """When streaming starts: 30–65% into the call (request + prefill before token one)."""
    return s + (e - s) * r.uniform(0.3, 0.65)


def _subsidy_eligibility(cfg: Config, spec: TraceSpec) -> tuple[dict, bool]:
    """What ``check_subsidy_eligibility`` reports, and whether the agent ignored it.

    For a *live* submission the policy is active today, so an eligible BEV sees the **real
    grant** — and a v1 decision that didn't apply it is flagged ``ignored_by_agent`` (the bug
    made visible). Seed traces keep the stale-window / no-subsidy text that the §7 regression
    relies on."""
    if spec.kind == "live":
        app = spec.application
        if app.vehicle.type == "BEV" and app.vehicle.list_price_eur <= cfg.golden_path.price_cap_eur:
            g = cfg.golden_path.grant_amount_eur
            out = {"applicable_subsidies": [{"name": "EV Purchase Grant", "amount_eur": g}],
                   "note": f"BEV ≤ €{cfg.golden_path.price_cap_eur:,} qualifies for the €{g:,} EV purchase grant"}
            return out, spec.decision.applied_grant_eur == 0   # grant offered but not applied
        return {"applicable_subsidies": [], "note": "no subsidy applies to this vehicle"}, False
    if spec.stale_grant_window:
        return {"applicable_subsidies": [], "note": "no subsidy programs configured for this policy version"}, True
    return {"applicable_subsidies": [], "note": "no active subsidy at application date"}, False


def build_trace_events(rng: Rng, cfg: Config, spec: TraceSpec, prompt_v1_version: int | None,
                       decision_usage: tuple[int, int] | None = None,
                       decision_latency_ms: int | None = None,
                       decision_input: list[dict] | None = None) -> list[dict]:
    """Build the agent-graph event tree. Seed path leaves the overrides None (tokens + latency
    are sampled; the decision input is the v1 chat turn compiled from the prompt file); the
    live playground passes the *real* model ``(input, output)`` token counts, the measured
    call latency, and the actually-compiled chat messages."""
    r = rng.sub("trace", spec.trace_id)
    app = spec.application
    env = spec.environment
    tid = spec.trace_id
    cur = _Cursor(spec.timestamp)
    events: list[dict] = []

    opus = cfg.model_by_role("plan")
    sonnet = cfg.model_by_role("work")
    haiku = cfg.model_by_role("light")

    # multi-turn context growth: each prior turn's Q+A accrues into the prompt, so the
    # reasoning steps (plan, decision) on later turns carry a larger input (spec §8).
    history_tokens = 0
    if spec.turn_index:
        hr = r.sub("history", spec.turn_index)
        history_tokens = int(spec.turn_index * hr.lognormal(HISTORY_TOKENS_PER_TURN, 0.25))

    # -- trace shell ------------------------------------------------------
    tags = list(spec.tags)
    if spec.environment == "staging":
        tags.append("staging")

    # Everything hangs off a root AGENT observation (the orchestrator), so the trace
    # renders as an agent graph: agent → {plan, tools, retriever, decision}. The two
    # load-bearing tools are surfaced as explicit tool_calls on the decision step.
    agent_id = r.obs_id("agent", tid)
    elig_call_id = r.obs_id("toolcall_elig", tid)
    afford_call_id = r.obs_id("toolcall_afford", tid)
    tool_calls = [
        {"id": elig_call_id, "name": "check_subsidy_eligibility"},
        {"id": afford_call_id, "name": "compute_affordability"},
    ]

    # -- optional plan generation (Opus) ----------------------------------
    # When the planner runs, its reasoning output is carried into the decision step's
    # input — so Opus reasoning has a downstream cost impact on the Sonnet call.
    plan_reasoning_tokens = 0
    if spec.plan_step:
        s, e = cur.advance(sample_latency_ms(r, "plan", spec.slow_factor))
        inp, outp = plan_io(app)
        it, ot, rt = sample_tokens(r, "plan", visible_input=text_tokens(inp),
                                   visible_output=text_tokens(outp), context_tokens=history_tokens)
        plan_reasoning_tokens = ot + rt
        ti, cr, cc = cache_split(r, "plan", it)
        events.append(generation_event(
            obs_id=r.obs_id("plan", tid), trace_id=tid, name="plan", start=s, end=e,
            completion_start=_first_token_at(r, s, e),
            parent_id=agent_id, model=opus.name, usage_details=usage_details(ti, ot, cr, cc, reasoning=rt),
            cost_details=cost_details(opus, ti, ot, cr, cc, reasoning=rt), environment=env,
            input=inp, output=outp, model_parameters={"temperature": 0.3}))

    # -- load_application span + extract_fields generation ----------------
    s_load, _ = cur.advance(0)  # span wraps the extract gen
    s, e = cur.advance(sample_latency_ms(r, "light", spec.slow_factor))
    raw, ein, eout = extract_io(app)
    it, ot, _ = sample_tokens(r, "light", visible_input=text_tokens(ein),
                              visible_output=text_tokens(eout))
    ti, cr, cc = cache_split(r, "light", it)
    load_id = r.obs_id("load", tid)
    events.append(span_event(obs_id=load_id, trace_id=tid, name="load_application",
                             start=s_load, end=e, parent_id=agent_id, environment=env,
                             input={"raw": raw}, output=eout))
    events.append(generation_event(
        obs_id=r.obs_id("extract", tid), trace_id=tid, name="extract_fields", start=s, end=e,
        completion_start=_first_token_at(r, s, e),
        parent_id=load_id, model=haiku.name, usage_details=usage_details(ti, ot, cr, cc),
        cost_details=cost_details(haiku, ti, ot, cr, cc), environment=env, input=ein, output=eout,
        metadata={"vehicle_model": model_label(r, app.vehicle.type)}))

    # -- retrieve_policy (RETRIEVER — vector search, no model) ------------
    s, e = cur.advance(tool_latency_ms(r, 180, 0.5, spec.slow_factor))
    rq, rdocs = retrieve_io()
    events.append(observation_event(
        obs_id=r.obs_id("retrieve", tid), trace_id=tid, name="retrieve_policy",
        obs_type="RETRIEVER", start=s, end=e, parent_id=agent_id, environment=env,
        input=rq, output={"documents": rdocs}, metadata={"retriever": "vector_search"}))

    # -- check_subsidy_eligibility (TOOL, load-bearing) ------------------
    fail_here = spec.error_step == "check_subsidy_eligibility"
    s, e = cur.advance(tool_latency_ms(r, 90, 0.4, spec.slow_factor))
    elig_out, ignored_by_agent = _subsidy_eligibility(cfg, spec)
    events.append(observation_event(
        obs_id=r.obs_id("eligib", tid), trace_id=tid, name="check_subsidy_eligibility",
        obs_type="TOOL", start=s, end=e, parent_id=agent_id, environment=env,
        input={"vehicle": app.vehicle.model_dump()},
        output=elig_out, level="ERROR" if fail_here else None,
        status_message="subsidy service timeout" if fail_here else None,
        metadata={"tool": "subsidy_lookup", "toolCallId": elig_call_id,
                  "ignored_by_agent": ignored_by_agent}))

    # -- compute_affordability (TOOL) ------------------------------------
    fail_aff = spec.error_step == "compute_affordability"
    s, e = cur.advance(tool_latency_ms(r, 70, 0.4, spec.slow_factor))
    events.append(observation_event(
        obs_id=r.obs_id("afford", tid), trace_id=tid, name="compute_affordability",
        obs_type="TOOL", start=s, end=e, parent_id=agent_id, environment=env,
        input={"financed_principal_eur": spec.decision.financed_principal_eur,
               "approved_line_eur": app.approved_line_eur},
        output={"within_line": spec.decision.financed_principal_eur <= app.approved_line_eur},
        level="ERROR" if fail_aff else None,
        status_message="affordability engine error" if fail_aff else None,
        metadata={"tool": "affordability_engine", "toolCallId": afford_call_id}))

    # -- decision generation (Sonnet) — decide(), links to prompt v1 ------
    # Input is the actual LLM turn: the managed system prompt + the application JSON
    # as the user message (multi-turn history / planner reasoning only grow the tokens).
    s, e = cur.advance(decision_latency_ms if decision_latency_ms is not None
                       else sample_latency_ms(r, "work", spec.slow_factor))
    if decision_input is None:                   # seed: every backdated decision ran v1
        decision_input = decision_messages(prompt_text("v1"), app)
    if decision_usage is not None:               # live: real token counts, no cache split
        ti, ot, cr, cc = decision_usage[0], decision_usage[1], 0, 0
    else:                                        # seed: sampled tokens + prompt-cache split
        it, ot, _ = sample_tokens(r, "work", visible_input=text_tokens(decision_input),
                                  visible_output=text_tokens(spec.decision.model_dump()),
                                  context_tokens=history_tokens + plan_reasoning_tokens)
        ti, cr, cc = cache_split(r, "work", it)
    dec_id = r.obs_id("decision", tid)
    spec.decision_obs_id = dec_id
    events.append(generation_event(
        obs_id=dec_id, trace_id=tid, name="decision", start=s, end=e, parent_id=agent_id,
        completion_start=_first_token_at(r, s, e),
        model=sonnet.name,
        usage_details=usage_details(ti, ot, cr, cc), cost_details=cost_details(sonnet, ti, ot, cr, cc),
        environment=env, input=decision_input, output=spec.decision.model_dump(),
        model_parameters={"temperature": 0}, metadata={"tool_calls": tool_calls},
        prompt_name=cfg.golden_path.prompt_name if prompt_v1_version else None,
        prompt_version=prompt_v1_version))

    # discrete marker: cache hit on policy retrieval, sometimes
    if r.chance(0.3):
        events.append(event_event(obs_id=r.obs_id("cache", tid), trace_id=tid,
                                  name="policy_cache_hit", start=s, parent_id=agent_id,
                                  environment=env, metadata={"layer": "policy"}))

    # -- explain generation (Haiku) ---------------------------------------
    s, e = cur.advance(sample_latency_ms(r, "light", spec.slow_factor))
    ein2, eout2 = explain_io(r, spec.decision)
    it, ot, _ = sample_tokens(r, "light", visible_input=text_tokens(ein2),
                              visible_output=text_tokens(eout2))
    ti, cr, cc = cache_split(r, "light", it)
    events.append(generation_event(
        obs_id=r.obs_id("explain", tid), trace_id=tid, name="explain", start=s, end=e,
        completion_start=_first_token_at(r, s, e),
        parent_id=agent_id, model=haiku.name, usage_details=usage_details(ti, ot, cr, cc),
        cost_details=cost_details(haiku, ti, ot, cr, cc), environment=env, input=ein2, output=eout2))

    # (The customer's pushback for disputed false-negatives is surfaced as the comment on
    # the `user_disagreement` score — see run.py / scores.py — not as a trace observation.)

    # -- root AGENT observation (spans the whole orchestration) -----------
    events.insert(0, observation_event(
        obs_id=agent_id, trace_id=tid, name="credit_agent", obs_type="AGENT",
        start=spec.timestamp, end=cur.t, environment=env,
        input=app.model_dump(), output=spec.decision.model_dump(),
        metadata={"tool_calls": tool_calls, "stale_grant_window": spec.stale_grant_window}))

    # -- trace shell (timestamp at start; carries final IO) ---------------
    events.insert(0, trace_event(
        trace_id=tid, timestamp=spec.timestamp, name=TRACE_NAME, user_id=spec.user_id,
        session_id=spec.session_id, tags=tags or None, environment=env,
        input=app.model_dump(), output=spec.decision.model_dump(),
        metadata={"kind": spec.kind, "vehicle_type": app.vehicle.type,
                  "stale_grant_window": spec.stale_grant_window}))
    return events
