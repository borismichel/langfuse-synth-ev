"""EV policy evidence through the installed SDK's public export seam.

The model response is supplied at the application boundary. No provider or Langfuse
network calls occur here; released-image ingestion and model rehearsals are separate.
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest
from langfuse import Langfuse
from langfuse.api import ChatPrompt
from langfuse.model import ChatPromptClient
from langfuse_synth_core.live.emit import LiveEmitter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from synth.agent import GrantRule, decide
from synth.config import load_config
from synth.live.trace import TRACE_NAME, emit_live_trace
from synth.models import Application


@pytest.fixture
def live_sdk():
    exported = InMemorySpanExporter()

    def unexpected_request(request):
        raise AssertionError(f"Unexpected SDK HTTP request: {request.method} {request.url.path}")

    client = Langfuse(
        base_url="http://langfuse.test", public_key=f"pk-test-{uuid.uuid4()}",
        secret_key="sk-test", span_exporter=exported,
        httpx_client=httpx.Client(transport=httpx.MockTransport(unexpected_request)),
    )
    yield LiveEmitter("http://langfuse.test", client=client), exported
    client.shutdown()


@pytest.mark.parametrize("label,price,line,verdict,grant,principal,ignored", [
    ("v1", 42000, 40000, "reject", 0, 42000, True),
    ("v2", 42000, 40000, "approve", 6000, 36000, False),
    ("v2", 48000, 40000, "reject", 6000, 42000, False),
])
def test_exported_decision_preserves_policy_evidence_and_prompt(
    live_sdk, label, price, line, verdict, grant, principal, ignored,
):
    emitter, exported = live_sdk
    cfg = load_config("config/demo.yaml")
    application = Application.model_validate({
        "applicant_id": "anon-sdk-test", "approved_line_eur": line,
        "vehicle": {"type": "BEV", "list_price_eur": price},
        "application_date": "2026-06-05",
    })
    rule = GrantRule(amount_eur=6000, price_cap_eur=50000, effective_date="2026-06-02")
    decision = decide(application, label, rule=rule)
    assert (decision.decision, decision.applied_grant_eur, decision.financed_principal_eur) == (
        verdict, grant, principal)
    prompt = ChatPromptClient(ChatPrompt(
        name="credit_decision", version=1 if label == "v1" else 2,
        prompt=[{"role": "user", "content": "{{application}}"}], config={}, labels=[], tags=[],
    ))
    from types import SimpleNamespace
    from synth.seed.prompts import chat_prompt
    from synth.policy import policy_variables
    prompt = ChatPromptClient(ChatPrompt(name="credit_decision", version=1 if label == "v1" else 2,
        prompt=chat_prompt(label), config={}, labels=[], tags=[]))
    messages = prompt.compile(**policy_variables(application, rule))
    llm = SimpleNamespace(model="claude-sonnet-4-6", provider="anthropic",
        complete=lambda **kwargs: SimpleNamespace(text=decision.model_dump_json(), input_tokens=1200, output_tokens=180))
    actual, trace_id = emit_live_trace(
        emitter, cfg, application=application, rule=rule, llm=llm, prompt=prompt,
        tags=["ev-grant", "playground"], user_id="presenter", environment="production")
    assert actual == decision
    spans = {span.name: span for span in exported.get_finished_spans()}
    assert len(spans) == 4
    root = spans[TRACE_NAME]
    assert root.parent is None
    assert trace_id == format(root.context.trace_id, "032x")
    assert json.loads(root.attributes["langfuse.observation.input"]) == application.model_dump()
    assert json.loads(root.attributes["langfuse.observation.output"]) == decision.model_dump()
    for span in spans.values():
        assert span.context.trace_id == root.context.trace_id
        assert span.attributes["user.id"] == "presenter"
        assert span.attributes["langfuse.environment"] == "production"
        assert list(span.attributes["langfuse.trace.tags"]) == ["ev-grant", "playground"]
        assert json.loads(span.attributes["langfuse.trace.metadata.kind"]) == "live"
    parents = {"credit_agent": TRACE_NAME, "retrieve_policy": "credit_agent", "decision": "credit_agent"}
    for name, parent in parents.items():
        assert spans[name].parent.span_id == spans[parent].context.span_id
    retrieval = json.loads(spans["retrieve_policy"].attributes["langfuse.observation.output"])
    assert retrieval["policy_updates"][0]["effective_date"] == "2026-06-02"
    assert "ignored_by_agent" not in str(spans)
    generation = spans["decision"].attributes
    assert generation["langfuse.observation.type"] == "generation"
    assert json.loads(generation["langfuse.observation.input"]) == messages
    assert json.loads(generation["langfuse.observation.output"]) == decision.model_dump()
    usage = json.loads(generation["langfuse.observation.usage_details"])
    assert usage["input"] == 1200 and usage["output"] == 180
    assert generation["langfuse.observation.model.name"] == cfg.model_by_role("work").name
    assert generation["langfuse.observation.prompt.name"] == "credit_decision"
    assert generation["langfuse.observation.prompt.version"] == prompt.version


def test_real_anthropic_sdk_does_not_duplicate_manually_recorded_decision(monkeypatch):
    """Real provider SDK + HTTP fixture catches auto-spans hidden by completion fakes."""
    import anthropic
    import httpx2
    from opentelemetry.sdk.trace import TracerProvider
    from langfuse_synth_core.companion.llm import LLMClient
    from synth.seed.prompts import chat_prompt

    cfg = load_config("config/demo.yaml")
    app = Application(applicant_id="sdk-tracing", approved_line_eur=40000,
        vehicle={"type":"BEV", "list_price_eur":45000}, application_date="2026-06-05")
    rule = GrantRule(effective_date="2026-06-02")
    decision = decide(app,"v1",rule=rule)
    provider = TracerProvider()
    exported = InMemorySpanExporter()
    sdk = anthropic.Anthropic(api_key="test-key", max_retries=0,
        open_telemetry={"tracer_provider":provider},
        http_client=httpx2.Client(transport=httpx2.MockTransport(lambda request: httpx2.Response(
            200, json={"id":"msg_test", "type":"message", "role":"assistant",
                "model":"claude-sonnet-4-6", "content":[{"type":"text", "text":decision.model_dump_json()}],
                "stop_reason":"end_turn", "stop_sequence":None,
                "usage":{"input_tokens":664,"output_tokens":96}}))))
    monkeypatch.setattr(anthropic,"Anthropic",lambda **kwargs:sdk)
    client = Langfuse(base_url="http://langfuse.test", public_key=f"pk-test-{uuid.uuid4()}",
        secret_key="sk-test", tracer_provider=provider, span_exporter=exported,
        httpx_client=httpx.Client(transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(AssertionError("Unexpected Langfuse HTTP")))))
    prompt = ChatPromptClient(ChatPrompt(name="credit_decision",version=1,
        prompt=chat_prompt("v1"),config={},labels=[],tags=[]))
    try:
        emitter = LiveEmitter("http://langfuse.test",client=client)
        actual, _ = emit_live_trace(emitter,cfg,application=app,rule=rule,
            llm=LLMClient("anthropic","claude-sonnet-4-6"),prompt=prompt)
        assert actual == decision
        spans = exported.get_finished_spans()
        assert sorted(span.name for span in spans) == sorted([
            TRACE_NAME,"credit_agent","retrieve_policy","decision"])
        generation = next(span for span in spans if span.name=="decision")
        assert json.loads(generation.attributes["langfuse.observation.usage_details"]) == {
            "input":664,"output":96}
        assert generation.attributes["langfuse.observation.prompt.version"] == 1
        # The SDK client remains instrumented for work outside the EV manual wrapper.
        exported.clear()
        sdk.messages.create(model="claude-sonnet-4-6",max_tokens=512,
            messages=[{"role":"user","content":"Independent call"}])
        client.flush()
        assert [span.name for span in exported.get_finished_spans()] == ["anthropic.messages.create"]
    finally:
        client.shutdown()
        sdk.close()
