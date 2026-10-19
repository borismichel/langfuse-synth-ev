"""The public submission path uses its deployment anchor and actual provider usage."""
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
            {"role": "system", "content": "Assess the supplied policy evidence."},
            {"role": "user", "content": variables["application"]}])

    def complete(**kwargs):
        model_calls.append(kwargs)
        return SimpleNamespace(text=json.dumps({"decision": "reject", "list_price_eur": 38000,
            "applied_grant_eur": 0, "financed_principal_eur": 38000, "approved_line_eur": 34000,
            "reason": "Gross price exceeds the approved line."}), input_tokens=123, output_tokens=45)

    adapter = SimpleNamespace(langfuse=lambda: SimpleNamespace(get_prompt=get_prompt),
                              llm=lambda _: SimpleNamespace(model="claude-sonnet-4-6", provider="anthropic", complete=complete),
                              emitter=lambda **_: emitter)
    app = Application(applicant_id="live", approved_line_eur=34000,
                      vehicle=Vehicle(type="BEV", list_price_eur=38000), application_date="2000-01-01")
    # A new process with default config still uses the seed's amount, cap and fixed date.
    result = submit(load_config("config/demo.yaml"), app, adapter=adapter, log=lambda _: None)
    assert (result["expected"].applied_grant_eur, result["expected"].decision) == (expected_grant, expected_verdict)
    evidence = next(s.kw["output"] for s in client.spans if s.kw["name"] == "retrieve_policy")
    update = evidence["policy_updates"][0]
    assert update["effective_date"] == as_of[:4] + "-06-02"
    assert "4,000" in update["content"] and "45,000" in update["content"]
    assert len(model_calls) == 1
    submitted = json.loads(model_calls[0]["messages"][0]["content"])
    assert submitted["application_date"] == datetime.now(timezone.utc).date().isoformat()
    assert prompt_reads[0]["label"] == "production" and prompt_reads[0]["cache_ttl_seconds"] == 0
    gen = next(s.kw for s in client.spans if s.kw["name"] == "decision")
    assert gen["usage_details"]["input"] == 123 and gen["output"]["applied_grant_eur"] == 0


def test_fresh_submission_uses_promoted_version_and_replays_the_same_context(monkeypatch, tmp_path, emitter, client):
    import json
    import requests
    from types import SimpleNamespace
    from langfuse.api import ChatPrompt
    from langfuse.model import ChatPromptClient
    from synth.live.submit import submit
    from synth.models import Application
    from synth.seed.prompts import chat_prompt
    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    response=requests.Response(); response.status_code=200
    response._content=b'{"data":[{"id":"demo-project","name":"demo-ev"}]}'
    monkeypatch.setattr(requests,"request",lambda *a,**k:response)
    version=1
    reads=[]
    def get_prompt(*args,**kwargs):
        reads.append(kwargs)
        return ChatPromptClient(ChatPrompt(name="credit_decision",version=version,
            prompt=chat_prompt(f"v{version}"),config={},labels=[],tags=[]))
    def complete(**kwargs):
        grant=6000 if "BULLETIN-EV-1" in str(kwargs["messages"]) else 0
        return SimpleNamespace(text=json.dumps({"list_price_eur":45000,"applied_grant_eur":grant,
            "financed_principal_eur":45000-grant,"approved_line_eur":40000,"reason":"Policy calculation",
            "decision":"approve" if grant else "reject"}),input_tokens=100,output_tokens=40)
    adapter=SimpleNamespace(langfuse=lambda:SimpleNamespace(get_prompt=get_prompt),
        llm=lambda _:SimpleNamespace(model="claude-sonnet-4-6",provider="anthropic",complete=complete),
        emitter=lambda **_:emitter)
    app=Application(applicant_id="promotion",approved_line_eur=40000,
        vehicle={"type":"BEV","list_price_eur":45000},application_date="2000-01-01")
    cfg=load_config("config/demo.yaml")
    baseline=submit(cfg,app,adapter=adapter,log=lambda _:None)
    version=2
    fixed=submit(cfg,app,adapter=adapter,log=lambda _:None)
    assert (baseline["prompt_version"], baseline["decision"].decision)==(1,"reject")
    assert (fixed["prompt_version"], fixed["decision"].financed_principal_eur)==(2,39000)
    assert all(r["label"]=="production" and r["cache_ttl_seconds"]==0 for r in reads)
    generations=[s.kw for s in client.spans if s.kw["name"]=="decision"]
    assert generations[0]["metadata"]["prompt_variables"]==generations[1]["metadata"]["prompt_variables"]
    assert [g["prompt"].version for g in generations]==[1,2]
    assert client.flushes==2
