"""The prompt repair changes only the missing policy-update binding."""
import json
from datetime import datetime, timezone
from langfuse.api import ChatPrompt
from langfuse.model import ChatPromptClient
from synth.agent import GrantRule
from synth.config import load_config
from synth.models import Application
from synth.seed.prompts import register_prompts


def test_both_versions_receive_identical_complete_context_and_only_candidate_renders_updates():
    from synth.policy import policy_variables
    app = Application(applicant_id="case", approved_line_eur=40000,
        vehicle={"type": "BEV", "list_price_eur": 45000}, application_date="2026-06-05")
    variables = policy_variables(app, GrantRule(effective_date="2026-06-02"))
    assert set(variables) == {"application", "handbook", "policy_updates"}
    assert all(isinstance(value, str) for value in variables.values())
    updates = json.loads(variables["policy_updates"])
    assert updates[0]["effective_date"] == "2026-06-02"
    assert updates[0]["published_date"] < "2026-06-02"
    assert json.loads(variables["handbook"])["effective_date"] < updates[0]["effective_date"]
    class Prompts:
        def __init__(self): self.created = []
        def get_prompt(self, *args, **kwargs): raise LookupError()
        def create_prompt(self, **kwargs):
            self.created.append(kwargs)
            return ChatPromptClient(ChatPrompt(name=kwargs["name"], version=len(self.created),
                prompt=kwargs["prompt"], config=kwargs["config"], labels=[], tags=[]))
    hosted = Prompts()
    register_prompts(hosted, load_config("config/demo.yaml"), datetime(2026,6,2,tzinfo=timezone.utc))
    old, new = hosted.created
    assert old["config"] == new["config"]
    assert old["prompt"][0] == new["prompt"][0]
    assert new["prompt"][1]["content"] == old["prompt"][1]["content"] + "\n\nPolicy updates:\n{{policy_updates}}"
    compiled = [ChatPromptClient(ChatPrompt(name=p["name"], version=i+1,
        prompt=p["prompt"], config=p["config"], labels=[], tags=[])).compile(**variables)
        for i,p in enumerate(hosted.created)]
    assert updates[0]["document_id"] not in str(compiled[0])
    assert updates[0]["document_id"] in str(compiled[1])
    assert policy_variables(app, None)["policy_updates"] == "[]"


def test_structured_output_rejects_missing_contradictory_and_multiple_decisions():
    import pytest
    from synth.agent import parse_decision
    app = Application(applicant_id="case", approved_line_eur=40000,
        vehicle={"type": "BEV", "list_price_eur": 45000}, application_date="2026-06-05")
    valid = {"list_price_eur":45000, "applied_grant_eur":6000, "financed_principal_eur":39000,
             "approved_line_eur":40000, "reason":"Within line", "decision":"approve"}
    assert parse_decision(json.dumps(valid), app).financed_principal_eur == 39000
    bad = [{key:value for key,value in valid.items() if key != "list_price_eur"},
           dict(valid, decision="reject"), dict(valid, financed_principal_eur=45000),
           dict(valid, approved_line_eur=50000), dict(valid, applied_grant_eur=-1),
           dict(valid, list_price_eur="45000"), dict(valid, extra="unexpected")]
    for output in bad:
        with pytest.raises(ValueError): parse_decision(json.dumps(output), app)
    with pytest.raises(ValueError): parse_decision(json.dumps(valid)+json.dumps(valid), app)
    with pytest.raises(ValueError): parse_decision("Corrected: "+json.dumps(valid), app)


def test_live_generation_receives_context_only_when_binding_is_promoted():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from synth.live.trace import emit_live_trace
    from synth.seed.prompts import chat_prompt
    app = Application(applicant_id="case", approved_line_eur=40000,
        vehicle={"type":"BEV", "list_price_eur":45000}, application_date="2026-06-05")
    rule = GrantRule(effective_date="2026-06-02")
    records, active, calls = [], [], []
    class Observation:
        id = "trace-id"
        def __init__(self, name, **kw): self.name=name; self.kw=kw; records.append(self)
        def update(self, **kw): self.kw.update(kw)
        @contextmanager
        def observation(self,name,**kw):
            child=Observation(name,**kw); active.append(name)
            try: yield child
            finally: active.pop()
        generation = observation
    class Emitter:
        @contextmanager
        def trace(self,name,**kw): yield Observation(name,**kw)
    def complete(**kwargs):
        assert active[-1] == "decision"
        assert any(r.name == "retrieve_policy" and "output" in r.kw for r in records)
        calls.append(kwargs)
        grant = 6000 if "BULLETIN-EV-1" in kwargs["messages"][0]["content"] else 0
        return SimpleNamespace(text=json.dumps(dict(list_price_eur=45000, applied_grant_eur=grant,
            financed_principal_eur=45000-grant, approved_line_eur=40000, reason="Policy evidence",
            decision="approve" if grant else "reject")), input_tokens=100, output_tokens=40)
    llm=SimpleNamespace(model="claude-sonnet-4-6",provider="anthropic",complete=complete)
    for version,label in enumerate(("v1","v2"),1):
        prompt=ChatPromptClient(ChatPrompt(name="credit_decision", version=version,
            prompt=chat_prompt(label),config={},labels=[],tags=[]))
        decision, trace_id = emit_live_trace(Emitter(), load_config("config/demo.yaml"),
            application=app, rule=rule, llm=llm, prompt=prompt)
        assert (decision.applied_grant_eur, decision.decision) == ((0,"reject") if version==1 else (6000,"approve"))
        assert trace_id == "trace-id"
    retrieved=[r.kw["output"] for r in records if r.name=="retrieve_policy"]
    assert retrieved[0] == retrieved[1]
    assert calls[0]["response_schema"] == calls[1]["response_schema"]
    generations=[r.kw for r in records if r.name=="decision"]
    assert generations[0]["metadata"]["prompt_variables"] == generations[1]["metadata"]["prompt_variables"]
    assert generations[0]["usage_details"] == {"input":100,"output":40}
    assert not any(r.name in ("check_subsidy_eligibility","extract_fields","explain") for r in records)


def test_history_exposes_retrieved_update_and_exact_baseline_input_without_fake_diagnosis():
    from synth.seed.generator import build_plan
    from synth.seed.traces import build_trace_events
    from synth.policy import policy_variables, lookup_policy
    from synth.seed.prompts import chat_prompt
    cfg=load_config("config/demo.yaml"); cfg.generation.total_traces=120
    plan=build_plan(cfg,datetime(2026,6,9,tzinfo=timezone.utc))
    spec=next(s for s in plan.specs if s.kind=="golden_eligible")
    spans=build_trace_events(plan.rng,cfg,spec,1)
    def attrs(s): return {a['key']:next(iter(a['value'].values())) for a in s['attributes']}
    retrieval=attrs(next(s for s in spans if s['name']=='retrieve_policy'))
    generation=attrs(next(s for s in spans if s['name']=='decision'))
    assert json.loads(retrieval['langfuse.observation.output']) == lookup_policy(spec.application,spec.grant_rule)
    variables=policy_variables(spec.application,spec.grant_rule)
    prompt=ChatPromptClient(ChatPrompt(name="credit_decision",version=1,prompt=chat_prompt("v1"),config={},labels=[],tags=[]))
    assert json.loads(generation['langfuse.observation.input']) == prompt.compile(**variables)
    assert json.loads(generation['langfuse.observation.metadata.prompt_variables']) == variables
    assert 'ignored_by_agent' not in json.dumps(spans)
    assert 'vector_search' not in json.dumps(spans)


def test_lookup_only_exposes_updates_published_by_application_date():
    from synth.policy import lookup_policy
    rule = GrantRule(effective_date="2026-06-02")
    app = Application(applicant_id="case", approved_line_eur=40000,
        vehicle={"type": "BEV", "list_price_eur": 45000}, application_date="2026-05-25")
    assert lookup_policy(app, rule)["policy_updates"] == []
    # Publication and eligibility are different boundaries: a published amendment
    # can already be visible while an application remains too early to qualify.
    app.application_date = "2026-05-26"
    assert lookup_policy(app, rule)["policy_updates"][0]["effective_date"] == "2026-06-02"


def test_sdk_experiment_and_companion_record_the_same_effective_model_request():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from synth.agent import decide
    from synth.live.trace import emit_live_trace
    from synth.policy import policy_variables
    from synth.seed.prompts import chat_prompt

    app = Application(applicant_id="parity", approved_line_eur=40000,
        vehicle={"type":"BEV", "list_price_eur":45000}, application_date="2026-06-05")
    rule = GrantRule(effective_date="2026-06-02")
    variables = policy_variables(app, rule)
    for provider in ("anthropic", "openai"):
        for template in (chat_prompt("v1"), [{"role":"system", "content":"Assess the application."}]):
            recorded, calls = [], []
            class Observation:
                id = "trace"
                def update(self, **kwargs): pass
                @contextmanager
                def observation(self, name, **kwargs):
                    if name == "decision": recorded.append(kwargs)
                    yield self
                generation = observation
            observer = Observation()
            prompt = ChatPromptClient(ChatPrompt(name="credit_decision", version=1,
                prompt=template, config={}, labels=[], tags=[]))
            lf = SimpleNamespace(get_prompt=lambda *a,**k:prompt,
                start_as_current_observation=lambda **k:observer.observation(**k))
            emitter = SimpleNamespace(trace=lambda name,**k:observer.observation(name,**k))
            def complete(**kwargs):
                calls.append(kwargs)
                return SimpleNamespace(text=decide(app,"v1",rule=rule).model_dump_json(),
                    input_tokens=10,output_tokens=10)
            llm = SimpleNamespace(provider=provider, model="parity-model", complete=complete)
            decide(variables,"production",rule=rule,live=True,lf=lf,llm=llm)
            emit_live_trace(emitter,load_config("config/demo.yaml"),application=app,rule=rule,llm=llm,prompt=prompt)
            assert calls[0] == calls[1]
            assert recorded[0]["input"] == recorded[1]["input"]
            expected_parameters = {"max_tokens":512, **({"temperature":0} if provider=="openai" else {})}
            for trace, request in zip(recorded, calls):
                assert trace["model_parameters"] == expected_parameters
                assert {key:request[key] for key in expected_parameters} == expected_parameters
                assert trace["metadata"]["response_schema"] == request["response_schema"]
                assert request["provider_tracing"] is False
                assert [m for m in trace["input"] if m["role"]!="system"] == request["messages"]
                assert "\n\n".join(m["content"] for m in trace["input"] if m["role"]=="system") == request["system"]
                assert request["messages"]  # system-only prompts get an observable application fallback
