"""SDK-v5 companion evidence preserves the existing raw-OTLP history format."""
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
from synth.seed.prompts import chat_prompt
from synth.seed.traces import TraceSpec, build_trace_events
from test_live_sdk import live_sdk


@pytest.mark.parametrize("date", ["2026-05-25", "2026-06-05"])
def test_live_metadata_serializes_as_the_existing_historical_values(live_sdk, date):
    emitter, exporter = live_sdk
    cfg = load_config("config/demo.yaml")
    app = Application(applicant_id="metadata-compatibility", approved_line_eur=32000,
        vehicle={"type":"BEV", "list_price_eur":38000}, application_date=date)
    rule = GrantRule(effective_date="2026-06-02")
    decision = decide(app,"v1",rule=rule)
    prompt = ChatPromptClient(ChatPrompt(name="credit_decision",version=1,
        prompt=chat_prompt("v1"), config={}, labels=[], tags=[]))
    llm = SimpleNamespace(model="claude-sonnet-4-6",provider="anthropic",
        complete=lambda **kw:SimpleNamespace(text=decision.model_dump_json(),input_tokens=100,output_tokens=40))
    emit_live_trace(emitter,cfg,application=app,rule=rule,llm=llm,prompt=prompt)
    live = next(s for s in exporter.get_finished_spans() if s.name=="decision")
    rng=Rng(42)
    spec=TraceSpec(trace_id=rng.trace_id("compatibility"), timestamp=datetime.fromisoformat(date).replace(tzinfo=timezone.utc),
        application=app,decision=decision,user_id="metadata-compatibility",session_id=None,
        environment="production",kind="golden_eligible",grant_rule=rule)
    seed=next(s for s in build_trace_events(rng,cfg,spec,1) if s["name"]=="decision")
    attrs={a["key"]:next(iter(a["value"].values())) for a in seed["attributes"]}
    for name in ("prompt_variables","response_schema"):
        key=f"langfuse.observation.metadata.{name}"
        # v5 ingestion decodes SDK metadata once. A JSON string remains a
        # leaf, exactly like the historical raw-OTLP value; it is not flattened.
        sdk_metadata_value=json.loads(live.attributes[key])
        assert isinstance(sdk_metadata_value,str), f"{name} would be flattened by SDK-v5 ingestion"
        assert json.loads(sdk_metadata_value)==json.loads(attrs[key])
    variables=json.loads(json.loads(live.attributes["langfuse.observation.metadata.prompt_variables"]))
    assert set(variables)=={"application","handbook","policy_updates"}
    updates=json.loads(variables["policy_updates"])
    assert bool(updates)==(date=="2026-06-05")
