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
    messages = prompt.compile(application=application.model_dump_json())
    trace_id = emit_live_trace(
        emitter, cfg, application=application, decision=decision, rule=rule,
        decision_input=messages, decision_usage=(1200, 180), prompt=prompt,
        tags=["ev-grant", "playground"], user_id="presenter", environment="production",
    )
    spans = {span.name: span for span in exported.get_finished_spans()}
    assert len(spans) == 9
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
    parents = {"credit_agent": TRACE_NAME, "load_application": "credit_agent",
               "extract_fields": "load_application", "retrieve_policy": "credit_agent",
               "check_subsidy_eligibility": "credit_agent", "compute_affordability": "credit_agent",
               "decision": "credit_agent", "explain": "credit_agent"}
    for name, parent in parents.items():
        assert spans[name].parent.span_id == spans[parent].context.span_id
    agent = spans["credit_agent"].attributes
    assert json.loads(agent["langfuse.observation.metadata.ignored_grant"]) is ignored
    eligibility = spans["check_subsidy_eligibility"].attributes
    assert json.loads(eligibility["langfuse.observation.metadata.ignored_by_agent"]) is ignored
    assert json.loads(eligibility["langfuse.observation.output"])["policy"] == {
        "amount_eur": 6000, "price_cap_eur": 50000, "effective_date": "2026-06-02"}
    affordability = spans["compute_affordability"].attributes
    assert json.loads(affordability["langfuse.observation.input"])["financed_principal_eur"] == principal
    assert json.loads(affordability["langfuse.observation.output"]) == {"within_line": verdict == "approve"}
    generation = spans["decision"].attributes
    assert generation["langfuse.observation.type"] == "generation"
    assert json.loads(generation["langfuse.observation.input"]) == messages
    assert json.loads(generation["langfuse.observation.output"]) == decision.model_dump()
    usage = json.loads(generation["langfuse.observation.usage_details"])
    assert usage["input"] == 1200 and usage["output"] == 180
    costs = json.loads(generation["langfuse.observation.cost_details"])
    assert costs["input"] > 0 and costs["output"] > 0 and costs["total"] > 0
    assert generation["langfuse.observation.model.name"] == cfg.model_by_role("work").name
    assert generation["langfuse.observation.prompt.name"] == "credit_decision"
    assert generation["langfuse.observation.prompt.version"] == prompt.version
