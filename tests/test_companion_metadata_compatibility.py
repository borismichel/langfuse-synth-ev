"""Seed and SDK exports carry the same historical JSON metadata leaves."""
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from langfuse import Langfuse
from langfuse.api import ChatPrompt
from langfuse.model import ChatPromptClient
from langfuse_synth_core.live.emit import LiveEmitter
from langfuse_synth_core.rng import Rng
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from synth.agent import GrantRule, decide
from synth.config import load_config
from synth.live.trace import emit_live_trace
from synth.models import Application
from synth.policy import policy_variables
from synth.seed.prompts import chat_prompt
from synth.seed.traces import TraceSpec, build_trace_events


@pytest.mark.parametrize("source", ["companion", "experiment"])
@pytest.mark.parametrize("date", ["2026-05-25", "2026-06-05"])
@pytest.mark.parametrize("version", [1, 2])
def test_decision_metadata_matches_history_at_the_real_sdk_export(source, date, version):
    cfg = load_config("config/demo.yaml")
    application = Application(
        applicant_id="metadata-compatibility", approved_line_eur=32000,
        vehicle={"type": "BEV", "list_price_eur": 38000}, application_date=date,
    )
    rule = GrantRule(effective_date="2026-06-02")
    decision = decide(application, f"v{version}", rule=rule)
    prompt = ChatPromptClient(ChatPrompt(
        name="credit_decision", version=version, prompt=chat_prompt(f"v{version}"),
        config={}, labels=[], tags=[],
    ))
    variables = policy_variables(application, rule)
    llm = SimpleNamespace(
        model="claude-sonnet-4-6", provider="anthropic",
        complete=lambda **kwargs: SimpleNamespace(
            text=decision.model_dump_json(), input_tokens=100, output_tokens=40,
        ),
    )

    def receive(request):
        assert request.method == "GET"
        assert request.url.path == "/api/public/v2/prompts/credit_decision"
        assert dict(request.url.params) == {"label": "production"}
        return httpx.Response(200, json={
            "name": "credit_decision", "version": version, "type": "chat",
            "prompt": chat_prompt(f"v{version}"), "config": {}, "labels": ["production"], "tags": [],
        })

    exporter = InMemorySpanExporter()
    client = Langfuse(
        base_url="http://langfuse.test", public_key=f"pk-test-{uuid.uuid4()}", secret_key="sk-test",
        span_exporter=exporter, httpx_client=httpx.Client(transport=httpx.MockTransport(receive)),
    )
    try:
        if source == "companion":
            emit_live_trace(
                LiveEmitter("http://langfuse.test", client=client), cfg,
                application=application, rule=rule, llm=llm, prompt=prompt,
            )
        else:
            decide(variables, "production", rule=rule, live=True, lf=client, llm=llm)
            client.flush()
        generation = next(span for span in exporter.get_finished_spans() if span.name == "decision")
        rng = Rng(42)
        spec = TraceSpec(
            trace_id=rng.trace_id("compatibility"), timestamp=datetime.fromisoformat(date).replace(tzinfo=timezone.utc),
            application=application, decision=decision, user_id="metadata-compatibility", session_id=None,
            environment="production", kind="golden_eligible", grant_rule=rule,
        )
        historical = next(span for span in build_trace_events(rng, cfg, spec, 1) if span["name"] == "decision")
        historical_attributes = {a["key"]: a["value"]["stringValue"] for a in historical["attributes"]
                                 if "stringValue" in a["value"]}
        for name in ("prompt_variables", "response_schema"):
            key = f"langfuse.observation.metadata.{name}"
            # v5 ingestion decodes once; the result must remain a JSON string leaf.
            # A dict here would be flattened to dotted keys by the server.
            sdk_leaf = json.loads(generation.attributes[key])
            assert isinstance(sdk_leaf, str), f"{name} would be flattened by SDK-v5 ingestion"
            assert sdk_leaf == historical_attributes[key]
        evidence = json.loads(json.loads(generation.attributes["langfuse.observation.metadata.prompt_variables"]))
        assert set(evidence) == {"application", "handbook", "policy_updates"}
        assert all(isinstance(value, str) for value in evidence.values())
        assert json.loads(evidence["application"]) == application.model_dump()
        updates = json.loads(evidence["policy_updates"])
        if date == "2026-05-25":
            assert updates == []  # Explicitly no published update, never missing evidence.
        else:
            assert updates[0]["document_id"] == "BULLETIN-EV-1"
            assert updates[0]["effective_date"] == "2026-06-02"
            assert "6,000" in updates[0]["content"]
        messages = generation.attributes["langfuse.observation.input"]
        assert ("BULLETIN-EV-1" in messages) == (version == 2 and bool(updates))
        assert generation.attributes["langfuse.observation.prompt.version"] == version
    finally:
        client.shutdown()
