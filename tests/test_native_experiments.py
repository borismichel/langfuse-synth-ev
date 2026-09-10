"""Hosted payload and live-call contracts for portal #234 (no network/model calls)."""
from contextlib import nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from jsonschema import validate, ValidationError

from langfuse.api import ChatPrompt
from langfuse.model import ChatPromptClient

from synth.agent import decide
from synth.config import load_config
from synth.models import Application
from synth.seed.datasets import create_dataset
from synth.seed.generator import build_plan
from synth.seed.prompts import register_prompts


class HostedDatasets:
    def __init__(self):
        self.datasets = {}
        self.schemas = {}
        self.prompts = {}

    def get_prompt(self, name, *, label, **kwargs):
        return self.prompts[label]

    def create_prompt(self, *, name, prompt, labels, **kwargs):
        client = ChatPromptClient(ChatPrompt.model_validate({"name": name,
            "version": len(self.prompts) + 1, "prompt": prompt,
            "config": {}, "labels": labels, "tags": []}))
        for label in labels:
            self.prompts[label] = client
        return client

    def create_dataset(self, *, name, **kwargs):
        self.datasets[name] = []
        self.schemas[name] = kwargs

    def create_dataset_item(self, *, dataset_name, **kwargs):
        schema = self.schemas[dataset_name]
        validate(kwargs["input"], schema.get("input_schema", {}))
        validate(kwargs["expected_output"], schema.get("expected_output_schema", {}))
        self.datasets[dataset_name].append(kwargs)


def test_hosted_inputs_compile_both_prompts_as_the_live_caller():
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 100
    plan = build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc))
    hosted = HostedDatasets()
    create_dataset(hosted, cfg, plan.golden)
    register_prompts(hosted, cfg, plan.golden.effective_date)
    rows = hosted.datasets[cfg.golden_path.dataset.name]
    assert len(rows) == 24
    for row, source in zip(rows, plan.golden.dataset_plan):
        assert row["input"] == {"application": source.application.model_dump_json()}
        assert row["expected_output"] == source.expected.model_dump()
        assert row["source_trace_id"] == source.source_trace_id
        assert row["metadata"]["scenario"] == source.scenario
        for version in (1, 2):
            prompt = hosted.get_prompt(cfg.golden_path.prompt_name, label=f"v{version}")
            assert prompt.variables == ["application"]
            compiled = prompt.compile(**row["input"])
            assert compiled[-1] == {"role": "user", "content": source.application.model_dump_json()}
            assert "{{" not in compiled[0]["content"]


def test_wrapped_dataset_input_reaches_live_model_unchanged():
    app = Application.model_validate({"applicant_id": "anon_demo", "approved_line_eur": 40000,
        "vehicle": {"type": "BEV", "list_price_eur": 42000}, "application_date": "2026-06-05"})
    prompt = ChatPromptClient(ChatPrompt.model_validate({"name": "credit_decision", "version": 2,
        "prompt": [{"role": "user", "content": "{{application}}"}],
        "config": {}, "labels": [], "tags": []}))
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='{"decision":"approve","applied_grant_eur":6000,"reason":"36000 <= 40000"}',
                               input_tokens=10, output_tokens=10)

    lf = SimpleNamespace(get_prompt=lambda *a, **k: prompt,
        start_as_current_observation=lambda **k: nullcontext(SimpleNamespace(update=lambda **k: None)))
    llm = SimpleNamespace(model="test", complete=complete)
    for payload in (app.model_dump(), {"application": app.model_dump_json()}):
        result = decide(payload, "development", live=True, lf=lf, llm=llm)
        assert result.decision == "approve"
        assert result.financed_principal_eur == 36000
    assert calls[0] == calls[1]
    assert calls[1]["messages"] == [{"role": "user", "content": app.model_dump_json()}]


def test_demo_cohort_has_independently_worked_policy_expectations():
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 100
    plan = build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc))
    hosted = HostedDatasets()
    info = create_dataset(hosted, cfg, plan.golden)
    rows = hosted.datasets[info["demo_name"]]
    # Worked against the fictional EUR 6,000 grant / EUR 50,000 cap policy,
    # never obtained by calling decide(v2). Tuple: decision, grant, principal.
    expected = {
        "false_negative": ("approve", 6000, 36000),
        "grant_still_above_line": ("reject", 6000, 42000),
        "cap_equal": ("approve", 6000, 44000),
        "cap_above": ("reject", 0, 50001),
        "control_phev": ("reject", 0, 42000),
        "control_ice": ("approve", 0, 42000),
        "date_before": ("reject", 0, 42000),
        "date_on_line_equal": ("approve", 6000, 36000),
        "date_after_line_below": ("reject", 6000, 36000),
        "cap_below": ("approve", 6000, 43999),
        "line_above": ("approve", 6000, 36000),
    }
    assert len(rows) == len(expected)
    for row in rows:
        scenario = row["metadata"]["scenario"]
        want = expected[scenario]
        app = Application.from_input(row["input"])
        output = row["expected_output"]
        assert (output["decision"], output["applied_grant_eur"], output["financed_principal_eur"]) == want
        assert output["list_price_eur"] == app.vehicle.list_price_eur
        assert output["approved_line_eur"] == app.approved_line_eur
        assert row["metadata"]["source"] == "hand-worked fictional policy cases"
        assert row["metadata"]["expectation_basis"]
        assert "source_trace_id" not in row  # authored fixtures must not invent trace provenance
        actual = decide(app, "v2", rule=plan.golden.rule)
        assert (actual.decision, actual.applied_grant_eur, actual.financed_principal_eur) == want
    assert len(hosted.datasets[cfg.golden_path.dataset.name]) == 24


def test_hosted_schema_rejects_missing_prompt_variable():
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 100
    plan = build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc))
    hosted = HostedDatasets()
    create_dataset(hosted, cfg, plan.golden)
    for name in hosted.datasets:
        with pytest.raises(ValidationError, match="application"):
            hosted.create_dataset_item(dataset_name=name, input={},
                                       expected_output=plan.golden.dataset_plan[0].expected.model_dump())


@pytest.mark.parametrize("payload, message", [
    ({"application": None}, "input.application"),
    ({"application": {}}, "input.application"),
    ({"application": "not JSON"}, "input.application"),
    ({"application": "{}"}, "applicant_id"),
    ({"application": "[]"}, "input.application"),
    ({}, "applicant_id"),
])
def test_malformed_inputs_have_actionable_errors(payload, message):
    with pytest.raises(ValueError, match=message):
        Application.from_input(payload)


def _experiment_adapter(items):
    prompt = ChatPromptClient(ChatPrompt.model_validate({"name": "credit_decision", "version": 2,
        "prompt": [{"role": "user", "content": "{{application}}"}],
        "config": {}, "labels": [], "tags": []}))
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='{"decision":"approve","applied_grant_eur":6000,"reason":"36000 <= 40000"}',
                               input_tokens=10, output_tokens=10)

    def run(**kwargs):
        results = [SimpleNamespace(item=item, output=kwargs["task"](item=item)) for item in items]
        return SimpleNamespace(item_results=results, format=lambda: "complete",
                               dataset_run_url="https://example.test/experiment")

    dataset = SimpleNamespace(items=items, run_experiment=run)
    lf = SimpleNamespace(get_prompt=lambda *a, **k: prompt, get_dataset=lambda *a: dataset,
        flush=lambda: None,
        start_as_current_observation=lambda **k: nullcontext(SimpleNamespace(update=lambda **k: None)))
    llm = SimpleNamespace(provider="test", model="test", complete=complete)
    return SimpleNamespace(langfuse=lambda: lf, llm=lambda model: llm), calls


def test_companion_experiment_uses_wrapped_input_and_structured_expectations():
    from synth.experiment.run import run_experiment
    app = Application.model_validate({"applicant_id": "anon_demo", "approved_line_eur": 40000,
        "vehicle": {"type": "BEV", "list_price_eur": 42000}, "application_date": "2026-06-05"})
    item = SimpleNamespace(id="curated", input={"application": app.model_dump_json()},
                           expected_output={"decision": "approve", "financed_principal_eur": 36000})
    adapter, calls = _experiment_adapter([item])
    outcome = run_experiment(load_config("config/demo.yaml"), label="development", adapter=adapter,
                             log=lambda message: None)["outcome"]
    assert outcome.green and outcome.passed == 1
    assert calls[0]["messages"] == [{"role": "user", "content": app.model_dump_json()}]


def test_experiment_rejects_invalid_item_before_any_model_call():
    from synth.experiment.run import run_experiment
    bad = SimpleNamespace(id="broken-curated-item", input={"application": "{}"}, expected_output={})
    adapter, calls = _experiment_adapter([bad])
    with pytest.raises(ValueError, match="broken-curated-item.*input.application"):
        run_experiment(load_config("config/demo.yaml"), adapter=adapter, log=lambda message: None)
    assert calls == []


def test_reserved_curation_keeps_source_but_corrects_stale_rejection():
    from synth.seed.datasets import reserved_items
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 100
    plan = build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc))
    rows = reserved_items(plan.golden)
    assert len(rows) == 3
    assert {row["source_trace_id"] for row in rows} == set(plan.golden.reserved_trace_ids)
    for row in rows:
        app = Application.from_input(row["input"])
        expected = row["expected_output"]
        # Independent policy review, rather than copying the generated rejection.
        assert app.vehicle.type == "BEV" and app.vehicle.list_price_eur <= 50000
        assert app.application_date >= "2026-06-02"
        assert app.vehicle.list_price_eur - 6000 <= app.approved_line_eur < app.vehicle.list_price_eur
        assert expected["decision"] == "approve" and expected["applied_grant_eur"] == 6000
        assert expected["financed_principal_eur"] == app.vehicle.list_price_eur - 6000
        assert row["metadata"]["scenario"] == "false_negative"
        assert row["metadata"]["source"] == "reserved seeded observation"
        assert row["metadata"]["expectation_basis"]


def test_small_grant_and_cap_can_still_produce_a_demo_cohort():
    from synth.agent import GrantRule
    from synth.seed.demo_cohort import demonstration_items
    rows = demonstration_items(GrantRule(amount_eur=2000, price_cap_eur=35000,
                                        effective_date="2026-06-02"), "small-policy-demo")
    fn = next(row for row in rows if row["metadata"]["scenario"] == "false_negative")
    assert fn["expected_output"]["decision"] == "approve"
    assert fn["expected_output"]["applied_grant_eur"] == 2000
    assert fn["expected_output"]["financed_principal_eur"] == 27400


@pytest.mark.parametrize("application", ["not JSON", "{}", "[]",
    '{"applicant_id":"x","approved_line_eur":null,"vehicle":{"type":"BEV","list_price_eur":42000},"application_date":"2026-06-02"}',
    '{"applicant_id":"x","approved_line_eur":40000,"vehicle":{"type":"OTHER","list_price_eur":42000},"application_date":"2026-06-02"}',
])
def test_hosted_schema_rejects_malformed_serialised_application(application):
    cfg = load_config("config/demo.yaml")
    cfg.generation.total_traces = 100
    plan = build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc))
    hosted = HostedDatasets()
    create_dataset(hosted, cfg, plan.golden)
    for name in hosted.datasets:
        with pytest.raises(ValidationError):
            hosted.create_dataset_item(dataset_name=name, input={"application": application},
                                       expected_output=plan.golden.dataset_plan[0].expected.model_dump())
