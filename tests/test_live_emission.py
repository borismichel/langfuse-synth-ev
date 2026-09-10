"""The playground emits through the live-emission seam, and still looks like the pool.

Two things have to hold at once after the cutover (portal #211):

  * a submission is written by the **live seam** — wall clock, the Langfuse SDK, no Spool
    envelope, nothing byte-compared against a golden. The playground used to build the
    Spool's backdated event tree and push it through the `Ingestor`, which coupled a
    surface that has no timestamp to supply to machinery whose whole purpose is supplying
    one;
  * the trace still **renders as the seeded pool does** — same agent graph, same names,
    same observation types — because the demo's move is a live decision landing at the top
    of the same timeline. That is what makes the seam swap invisible to the presenter.

So the shape assertion here is written against the seeded builder's own output rather than
a hand-copied list: if the two writers ever drift, this fails.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from langfuse_synth_core.live.emit import LiveEmitter

from synth.agent import GrantRule, decide
from synth.config import load_config
from synth.content import eligible_borderline_application
from synth.live.trace import TRACE_NAME, emit_live_trace
from langfuse_synth_core.rng import Rng


class _FakeSpan:
    def __init__(self, recorder, kw, parent=None):
        self.recorder = recorder
        self.kw = dict(kw)
        self.parent = parent
        self.trace_id = "trace-live"
        self.id = f"obs-{len(recorder.spans)}"
        recorder.spans.append(self)

    def update(self, **kw):
        self.kw.update(kw)
        return self

    @contextmanager
    def start_as_current_observation(self, **kw):
        yield _FakeSpan(self.recorder, kw, parent=self)


class _FakeClient:
    def __init__(self):
        self.spans: list[_FakeSpan] = []
        self.scores: list[dict] = []
        self.flushes = 0

    @contextmanager
    def start_as_current_observation(self, **kw):
        yield _FakeSpan(self, kw, parent=None)

    def create_score(self, **kw):
        self.scores.append(kw)

    def flush(self):
        self.flushes += 1


@contextmanager
def _no_propagate(**_attrs):
    yield


@pytest.fixture
def client():
    return _FakeClient()


@pytest.fixture
def emitter(client):
    return LiveEmitter("http://localhost:3000", public_key="pk", secret_key="sk",
                       client=client, propagate=_no_propagate)


def _submission(cfg):
    rule = GrantRule(amount_eur=cfg.golden_path.grant_amount_eur,
                     price_cap_eur=cfg.golden_path.price_cap_eur,
                     effective_date="2026-06-02")
    app = eligible_borderline_application(Rng(1), 1, "2026-06-04", rule)
    return app, decide(app, "v1", rule=rule)


def _emit(emitter, cfg):
    app, decision = _submission(cfg)
    trace_id = emit_live_trace(
        emitter, cfg, application=app, decision=decision,
        rule=GrantRule(effective_date="2026-06-02"),
        decision_input=[{"role": "system", "content": "You are a credit-decision agent."}],
        decision_usage=(1200, 180), prompt=None, tags=["ev-grant", "playground"])
    return app, decision, trace_id


def _seeded_shape(cfg, app, decision):
    """The (name, observation type) pairs the seeder writes for one trace, in tree order.

    The Spool is OTLP spans since the write-path cutover (#210), so the type is read off the
    span attribute rather than an envelope field — including the minted root, which is the
    trace and is named for it on both writers.
    """
    from synth.seed.traces import TraceSpec, build_trace_events

    spec = TraceSpec(trace_id=Rng(1).trace_id("shape", "1"),
                     timestamp=datetime(2026, 6, 4, tzinfo=timezone.utc),
                     application=app, decision=decision, user_id="u", session_id=None,
                     environment="production", kind="golden_eligible", plan_step=False)
    spans = build_trace_events(Rng(cfg.generation.seed), cfg, spec, 1)

    def obs_type(span):
        for attr in span["attributes"]:
            if attr["key"] == "langfuse.observation.type":
                return attr["value"]["stringValue"].upper()
        return "SPAN"

    return [(s["name"], obs_type(s)) for s in spans
            if s["name"] not in (TRACE_NAME, "policy_cache_hit")]


def test_the_live_trace_carries_the_same_agent_graph_the_seeder_writes(emitter, client):
    cfg = load_config("config/demo.yaml")
    app, decision, _ = _emit(emitter, cfg)

    live = [(s.kw.get("name"), str(s.kw.get("as_type", "span")).upper())
            for s in client.spans if s.kw.get("name") != TRACE_NAME]
    assert live == _seeded_shape(cfg, app, decision), (
        "the live writer and the seeder drifted — a submission would no longer render like "
        "the pool it lands in front of")


def test_the_graph_nests_the_way_the_pool_does(emitter, client):
    """`extract_fields` inside `load_application` inside `credit_agent`, everything else on
    the agent. Flattening it would still list the right names and render the wrong trace."""
    _emit(emitter, load_config("config/demo.yaml"))
    by_name = {s.kw.get("name"): s for s in client.spans}

    assert by_name["credit_agent"].parent is client.spans[0]           # the root/trace
    assert by_name["load_application"].parent is by_name["credit_agent"]
    assert by_name["extract_fields"].parent is by_name["load_application"]
    for name in ("retrieve_policy", "check_subsidy_eligibility", "compute_affordability",
                 "decision", "explain"):
        assert by_name[name].parent is by_name["credit_agent"], name


def test_the_decision_generation_carries_the_real_usage_and_the_prompt_link(emitter, client):
    _, decision, _ = _emit(emitter, load_config("config/demo.yaml"))
    gen = next(s for s in client.spans if s.kw.get("name") == "decision")

    assert gen.kw["usage_details"]["input"] == 1200
    assert gen.kw["usage_details"]["output"] == 180
    assert gen.kw["cost_details"]["total"] > 0
    assert gen.kw["output"] == decision.model_dump()
    assert "prompt" not in gen.kw or gen.kw["prompt"] is None   # pruned when unlinked


def test_the_overall_io_lands_on_the_root_observation(emitter, client):
    """Under v4 there is no trace body: the trace's input and output live on its root."""
    app, decision, trace_id = _emit(emitter, load_config("config/demo.yaml"))
    root = client.spans[0]

    assert root.kw["name"] == TRACE_NAME
    assert root.kw["input"] == app.model_dump()
    assert root.kw["output"] == decision.model_dump()
    assert trace_id == "trace-live"


def test_the_submission_is_delivered_before_the_surface_answers(emitter, client):
    _emit(emitter, load_config("config/demo.yaml"))
    assert client.flushes == 1


def test_the_playground_never_reaches_for_the_spool():
    """The determinism line, kit-side: a live surface that imported the Spool's builders or
    its ingestor would be back on the backdating path the seam exists to leave."""
    import pathlib

    for module in ("live/trace.py", "live/submit.py"):
        source = pathlib.Path("src/synth") .joinpath(module).read_text()
        body = source.split('"""', 2)[-1]          # the docstrings discuss the line
        for forbidden in ("Ingestor", "build_trace_events", "seed.events", "score_event"):
            assert forbidden not in body, f"{module} reaches for the Spool: {forbidden}"


@pytest.mark.parametrize("vehicle,price,line,application_date,label,grant,principal,verdict,ignored,available", [
    ("BEV", 38000, 34000, "2026-06-02", "v1", 0, 38000, "reject", True, 4000),
    ("BEV", 38000, 34000, "2026-06-02", "v2", 4000, 34000, "approve", False, 4000),
    ("BEV", 46000, 44000, "2026-06-04", "v2", 0, 46000, "reject", False, 0),
    ("PHEV", 38000, 34000, "2026-06-04", "v2", 0, 38000, "reject", False, 0),
    ("ICE", 38000, 34000, "2026-06-04", "v2", 0, 38000, "reject", False, 0),
    ("BEV", 38000, 34000, "2026-06-01", "v2", 0, 38000, "reject", False, 0),
    ("BEV", 45000, 41000, "2026-06-02", "v2", 4000, 41000, "approve", False, 4000),
])
def test_historical_and_live_evidence_share_the_policy(
    emitter, client, vehicle, price, line, application_date, label, grant, principal, verdict, ignored, available,
):
    import json
    from langfuse_synth_core.seed import otlp
    from synth.models import Application, Vehicle
    from synth.seed.traces import TraceSpec, build_trace_events

    cfg = load_config("config/demo.yaml")
    rule = GrantRule(amount_eur=4000, price_cap_eur=45000, effective_date="2026-06-02")
    app = Application(applicant_id="policy-case", approved_line_eur=line,
                      vehicle=Vehicle(type=vehicle, list_price_eur=price), application_date=application_date)
    decision = decide(app, label, rule=rule)
    assert (decision.applied_grant_eur, decision.financed_principal_eur, decision.decision) == (grant, principal, verdict)
    emit_live_trace(emitter, cfg, application=app, decision=decision, rule=rule,
                    decision_input=[], decision_usage=(100, 50))
    live = {s.kw["name"]: s.kw for s in client.spans}
    # Seeded history always represents v1; fixed-output coverage is the live confirmation.
    historical = decide(app, "v1", rule=rule)
    spec = TraceSpec(trace_id=Rng(1).trace_id("policy-case"),
                     timestamp=datetime(2026, 6, 4, tzinfo=timezone.utc), application=app,
                     decision=historical, user_id="u", session_id=None,
                     environment="production", kind="control", grant_rule=rule)
    spans = build_trace_events(Rng(1), cfg, spec, 1)
    elig = next(s for s in spans if s["name"] == "check_subsidy_eligibility")
    attrs = {a["key"]: next(iter(a["value"].values())) for a in elig["attributes"]}
    evidence = live["check_subsidy_eligibility"]["output"]
    assert json.loads(attrs[otlp.OBS_OUTPUT]) == evidence
    assert evidence["applicable_subsidies"] == ([{"name": "EV Purchase Grant", "amount_eur": 4000}] if available else [])
    assert evidence["policy"] == {"amount_eur": 4000, "price_cap_eur": 45000, "effective_date": "2026-06-02"}
    assert live["check_subsidy_eligibility"]["metadata"]["ignored_by_agent"] is ignored
    assert live["compute_affordability"]["input"]["financed_principal_eur"] == principal
    assert live["compute_affordability"]["output"] == {"within_line": verdict == "approve"}


@pytest.mark.parametrize("as_of,expected_grant,expected_verdict", [
    ("2026-06-09", 4000, "approve"), ("2099-06-09", 0, "reject"),
])
def test_submission_keeps_the_seeded_policy_anchor(
    monkeypatch, tmp_path, emitter, client, as_of, expected_grant, expected_verdict,
):
    import json
    import requests
    from types import SimpleNamespace
    from synth.live.submit import submit
    from synth.models import Application, Vehicle
    from synth.seed.run import run_seed

    cfg = load_config("config/demo.yaml", overrides=[
        "generation.target_traces=120", f"generation.as_of_date={as_of}",
        "golden_path.grant_amount_eur=4000", "golden_path.price_cap_eur=45000"])
    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path / "state"))
    state = run_seed(cfg, dry_run=True, persist=False, do_import=False,
                     spool_path=tmp_path / "events.ndjson", log=lambda _: None)
    state.save()
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"data":[{"id":"demo-project","name":"demo-ev"}]}'
    monkeypatch.setattr(requests, "request", lambda *a, **kw: response)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    prompt_reads, model_calls = [], []

    def get_prompt(*args, **kwargs):
        prompt_reads.append(kwargs)
        return SimpleNamespace(version=1, compile=lambda **variables: [
            {"role": "system", "content": "Finance gross price. Apply no grant."},
            {"role": "user", "content": variables["application"]}])

    def complete(**kwargs):
        model_calls.append(kwargs)
        return SimpleNamespace(text=json.dumps({"decision": "reject", "list_price_eur": 38000,
            "applied_grant_eur": 0, "financed_principal_eur": 38000, "approved_line_eur": 34000,
            "reason": "Gross price exceeds the approved line."}), input_tokens=123, output_tokens=45)

    adapter = SimpleNamespace(langfuse=lambda: SimpleNamespace(get_prompt=get_prompt),
                              llm=lambda _: SimpleNamespace(complete=complete),
                              emitter=lambda **_: emitter)
    app = Application(applicant_id="live", approved_line_eur=34000,
                      vehicle=Vehicle(type="BEV", list_price_eur=38000), application_date="2000-01-01")
    # A new process with default config still uses the seed's amount, cap and fixed date.
    result = submit(load_config("config/demo.yaml"), app, adapter=adapter, log=lambda _: None)
    assert (result["expected"].applied_grant_eur, result["expected"].decision) == (expected_grant, expected_verdict)
    evidence = next(s.kw["output"] for s in client.spans if s.kw["name"] == "check_subsidy_eligibility")
    assert evidence["policy"] == {"amount_eur": 4000, "price_cap_eur": 45000,
                                  "effective_date": as_of[:4] + "-06-02"}
    assert len(model_calls) == 1
    submitted = json.loads(model_calls[0]["messages"][0]["content"])
    assert submitted["application_date"] == datetime.now(timezone.utc).date().isoformat()
    assert prompt_reads[0]["label"] == "production" and prompt_reads[0]["cache_ttl_seconds"] == 0
    gen = next(s.kw for s in client.spans if s.kw["name"] == "decision")
    assert gen["usage_details"]["input"] == 123 and gen["output"]["applied_grant_eur"] == 0
