"""Golden-path invariants: the spine of the demo must hold structurally (spec §7)."""
from datetime import datetime, timezone

import json

from langfuse_synth_core.seed import otlp
from synth.config import load_config
from synth.seed.generator import build_plan
from synth.seed.traces import build_trace_events

RUN_DATE = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


def _plan():
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 400
    return cfg, build_plan(cfg, RUN_DATE)


def test_dataset_counts_match_config():
    cfg, plan = _plan()
    ds = cfg.golden_path.dataset
    items = plan.golden.dataset_plan
    assert len(items) == ds.n_items
    eligible = [it for it in items if it.eligible]
    assert len(eligible) == round(ds.n_items * ds.eligible_share)


def test_eligible_items_expect_approve_controls_expect_reject():
    _, plan = _plan()
    for it in plan.golden.dataset_plan:
        if it.eligible:
            assert it.expected.decision == "approve" and it.expected.applied_grant_eur == 6000
        else:
            assert it.expected.decision == "reject" and it.expected.applied_grant_eur == 0


def test_seeded_disputed_decisions_are_v1_rejections():
    _, plan = _plan()
    fn = [s for s in plan.golden.disputed_specs if s.kind == "golden_eligible"]
    assert fn, "expected eligible false-negatives"
    for s in fn:
        assert s.decision.decision == "reject"          # the wrong rejection
        assert s.decision.applied_grant_eur == 0         # v1: no grant


def test_reserved_pool_is_not_in_dataset():
    _, plan = _plan()
    reserved = set(plan.golden.reserved_trace_ids)
    assert len(reserved) == 3
    item_sources = {it.source_trace_id for it in plan.golden.dataset_plan}
    assert reserved.isdisjoint(item_sources)


def test_disputed_traces_fall_in_drift_window():
    _, plan = _plan()
    start, end = plan.golden.drift_start, plan.golden.drift_end
    for s in plan.golden.disputed_specs:
        assert start <= s.timestamp <= end


def test_trace_events_ship_as_typed_otlp_spans():
    """The wire the kit actually ships (portal #210): the trace shell is the minted root
    span, the agent-graph steps carry their real types natively, and only scores remain
    ingestion envelopes."""
    cfg, plan = _plan()
    spec = next(s for s in plan.golden.disputed_specs if s.kind == "golden_eligible")
    events = build_trace_events(plan.rng, cfg, spec, prompt_v1_version=1)
    spans = [e for e in events if "spanId" in e]
    envelopes = [e for e in events if e.get("type")]
    assert spans and all(e["type"] == "score-create" for e in envelopes)
    assert events[0] in spans  # the root span rides where the trace envelope used to

    obs_types = set()
    for s in spans:
        for a in s["attributes"]:
            if a["key"] == "langfuse.observation.type":
                obs_types.add(a["value"]["stringValue"])
    assert {"agent", "retriever", "tool", "generation"} <= obs_types


def _attrs(span: dict) -> dict:
    """A span's attributes as a plain mapping, unwrapping the OTLP AnyValue."""
    return {a["key"]: next(iter(a["value"].values())) for a in span["attributes"]}


def test_trace_events_well_formed():
    """The deep content semantics — prompt linkage, usage-vs-text floors, TTFT ordering.

    These are claims about what the builders are *fed*, so they were asserted on the batch
    envelope's readable bodies while that wire existed. It does not (portal #213), so they
    are read off the span attributes instead. Core's suite owns the serialisation; this owns
    the substance.
    """
    from langfuse_synth_core.distributions import text_tokens

    cfg, plan = _plan()
    spec = next(s for s in plan.golden.disputed_specs if s.kind == "golden_eligible")
    events = build_trace_events(plan.rng, cfg, spec, prompt_v1_version=1)
    spans = [e for e in events if "spanId" in e]

    # decision generation links to prompt v1
    decision = next(s for s in spans if s["name"] == "decision")
    decision_attrs = _attrs(decision)
    assert decision_attrs[otlp.PROMPT_NAME] == cfg.golden_path.prompt_name
    assert int(decision_attrs[otlp.PROMPT_VERSION]) == 1
    # ... and its input is the actual LLM turn: system prompt + application user message
    dec_input = json.loads(decision_attrs[otlp.OBS_INPUT])
    assert dec_input[0]["role"] == "system"
    assert "credit-decision agent" in dec_input[0]["content"]
    assert dec_input[1]["role"] == "user"
    assert str(spec.application.vehicle.list_price_eur) in dec_input[1]["content"]

    # every generation's input is chat-shaped (the prompt is part of the input), its
    # claimed usage covers at least the visible text, and TTFT falls inside the call
    for span in spans:
        attrs = _attrs(span)
        if attrs.get(otlp.OBS_TYPE) != "generation":
            continue
        msgs = json.loads(attrs[otlp.OBS_INPUT])
        assert isinstance(msgs, list) and msgs[0]["role"] == "system", span["name"]
        usage = json.loads(attrs[otlp.USAGE_DETAILS])
        input_side = (usage["input"] + usage.get("cache_read_input_tokens", 0)
                      + usage.get("cache_creation_input_tokens", 0))
        assert input_side >= text_tokens(msgs), span["name"]
        assert usage["output"] >= text_tokens(_decoded(attrs[otlp.OBS_OUTPUT])) * 0.8, \
            span["name"]
        ttft = attrs[otlp.COMPLETION_START_TIME]
        assert _iso_ns(span["startTimeUnixNano"]) < ttft < _iso_ns(span["endTimeUnixNano"]), \
            span["name"]

    # every observation has start <= end
    for span in spans:
        assert int(span["startTimeUnixNano"]) <= int(span["endTimeUnixNano"])


def _decoded(value: str):
    """An io attribute as data. The wire carries JSON text, except where the value was a
    plain string to begin with — which core sends verbatim, and the read seam hands back
    the same way."""
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def _iso_ns(nanos: str) -> str:
    """An OTLP epoch-nanos stamp as the ISO string `completion_start_time` carries, so the
    three can be ordered against each other."""
    from datetime import datetime, timezone

    from langfuse_synth_core.timegen import iso

    return iso(datetime.fromtimestamp(int(nanos) / 1e9, tz=timezone.utc))


def test_grant_effective_date_is_recent_relative_to_run():
    cfg, plan = _plan()
    # effective date = run_date + offset (negative) -> in the past, within the window
    assert plan.golden.effective_date < RUN_DATE


def test_seeded_rejection_ignores_an_available_deployment_grant():
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 120
    cfg.golden_path.grant_amount_eur = 4000
    cfg.golden_path.price_cap_eur = 45000
    plan = build_plan(cfg, RUN_DATE)
    spec = next(s for s in plan.specs if s.kind == "golden_eligible")
    spans = {s["name"]: _attrs(s) for s in build_trace_events(plan.rng, cfg, spec, 1)}
    evidence = json.loads(spans["check_subsidy_eligibility"][otlp.OBS_OUTPUT])
    assert evidence["applicable_subsidies"] == [{"name": "EV Purchase Grant", "amount_eur": 4000}]
    assert evidence["policy"] == {"amount_eur": 4000, "price_cap_eur": 45000,
                                  "effective_date": "2026-06-02"}
    assert json.loads(spans["check_subsidy_eligibility"]["langfuse.observation.metadata.ignored_by_agent"]) is True
    affordability = json.loads(spans["compute_affordability"][otlp.OBS_INPUT])
    assert affordability["financed_principal_eur"] == spec.application.vehicle.list_price_eur
    assert json.loads(spans["compute_affordability"][otlp.OBS_OUTPUT]) == {"within_line": False}
    assert spec.decision.decision == "reject" and spec.decision.applied_grant_eur == 0
