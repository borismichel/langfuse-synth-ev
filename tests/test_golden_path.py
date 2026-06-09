"""Golden-path invariants: the spine of the demo must hold structurally (spec §7)."""
from datetime import datetime, timezone

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


def test_trace_events_well_formed():
    cfg, plan = _plan()
    spec = next(s for s in plan.golden.disputed_specs if s.kind == "golden_eligible")
    events = build_trace_events(plan.rng, cfg, spec, prompt_v1_version=1)
    types = [e["type"] for e in events]
    assert types[0] == "trace-create"
    assert "generation-create" in types and "span-create" in types
    # decision generation links to prompt v1
    decision = next(e for e in events if e["body"].get("name") == "decision")
    assert decision["body"]["promptName"] == cfg.golden_path.prompt_name
    assert decision["body"]["promptVersion"] == 1
    # every observation has start <= end
    for e in events:
        b = e["body"]
        if "startTime" in b and "endTime" in b:
            assert b["startTime"] <= b["endTime"]


def test_grant_effective_date_is_recent_relative_to_run():
    cfg, plan = _plan()
    # effective date = run_date + offset (negative) -> in the past, within the window
    assert plan.golden.effective_date < RUN_DATE
