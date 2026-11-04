"""The real seed and SDK writers must expose the same evaluator evidence keys."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from langfuse.api import ChatPrompt
from langfuse.model import ChatPromptClient
from langfuse_synth_core.rng import Rng

from synth.agent import GrantRule, decide
from synth.config import load_config
from synth.live.trace import emit_live_trace
from synth.models import Application
from synth.policy import policy_variables
from synth.seed.prompts import chat_prompt
from synth.seed.traces import TraceSpec, build_trace_events
from test_live_sdk import live_sdk


def _decoded(value):
    # The API exposes JSON-valued metadata as objects, including JSON strings
    # captured as prompt variables. Decode without changing any metadata keys.
    while isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            break
    return value


@pytest.mark.parametrize("application_date", ["2026-05-25", "2026-06-05"])
def test_seed_and_live_export_the_same_decision_metadata(live_sdk, application_date):
    emitter, exporter = live_sdk
    cfg = load_config("config/demo.yaml")
    application = Application(applicant_id="metadata-parity", approved_line_eur=32000,
        vehicle={"type": "BEV", "list_price_eur": 38000}, application_date=application_date)
    rule = GrantRule(effective_date="2026-06-02")
    decision = decide(application, "v1", rule=rule)
    variables = policy_variables(application, rule)
    prompt = ChatPromptClient(ChatPrompt(name="credit_decision", version=1,
        prompt=chat_prompt("v1"), config={}, labels=[], tags=[]))
    llm = SimpleNamespace(model="claude-sonnet-4-6", provider="anthropic",
        complete=lambda **kwargs: SimpleNamespace(text=decision.model_dump_json(),
            input_tokens=100, output_tokens=40))
    emit_live_trace(emitter, cfg, application=application, rule=rule, llm=llm, prompt=prompt)
    live = next(s for s in exporter.get_finished_spans() if s.name == "decision")

    rng = Rng(42)
    spec = TraceSpec(trace_id=rng.trace_id("metadata-parity"),
        timestamp=datetime.fromisoformat(application_date).replace(tzinfo=timezone.utc),
        application=application, decision=decision, user_id="metadata-parity", session_id=None,
        environment="production", kind="golden_eligible", grant_rule=rule)
    seeded = next(s for s in build_trace_events(rng, cfg, spec, 1) if s["name"] == "decision")
    seed_attributes = {a["key"]: next(iter(a["value"].values())) for a in seeded["attributes"]}
    prefix = "langfuse.observation.metadata."
    expected = {f"prompt_variables.{key}": json.loads(value) for key, value in variables.items()}
    exported_metadata = []
    for attributes in (seed_attributes, live.attributes):
        metadata = {key.removeprefix(prefix): _decoded(value)
                    for key, value in attributes.items() if key.startswith(prefix)}
        for key, value in expected.items():
            assert key in metadata, f"Missing evaluator evidence key: {key}; got {list(metadata)}"
            assert metadata[key] == value
        assert "prompt_variables" not in metadata
        assert "response_schema" not in metadata
        assert metadata["response_schema.properties.decision.enum"] == ["approve", "reject"]
        assert metadata["response_schema.additionalProperties"] is False
        exported_metadata.append({k: v for k, v in metadata.items() if k != "execution"})
    assert exported_metadata[0] == exported_metadata[1]
    # Independent policy remains available even when the baseline prompt omits it.
    assert "BULLETIN-EV-1" not in json.loads(live.attributes["langfuse.observation.input"])[1]["content"]
