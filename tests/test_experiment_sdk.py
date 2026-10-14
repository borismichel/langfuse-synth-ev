"""Native EV experiment records using the real SDK and controlled HTTP/model boundaries."""
import json
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
from langfuse import Langfuse
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from synth.config import load_config
from synth.experiment.run import run_experiment


def test_native_experiment_exports_item_identity_decisions_and_comparison_url(monkeypatch):
    import requests

    def unexpected_raw_request(*args, **kwargs):
        raise AssertionError("Unexpected fallback HTTP request")

    monkeypatch.setattr(requests, "request", unexpected_raw_request)
    cfg = load_config("config/demo.yaml")
    stamp = "2026-06-09T12:00:00Z"
    dataset_name = cfg.golden_path.dataset.name
    items = []
    for identifier, price, verdict, principal in [
        ("eligible", 42000, "approve", 36000), ("above-line", 48000, "reject", 42000),
    ]:
        application = {"applicant_id": identifier, "approved_line_eur": 40000,
                       "vehicle": {"type": "BEV", "list_price_eur": price},
                       "application_date": "2026-06-05"}
        items.append({"id": identifier, "status": "ACTIVE",
            "input": {"application": json.dumps(application)},
            "expectedOutput": {"decision": verdict, "applied_grant_eur": 6000,
                               "financed_principal_eur": principal},
            "metadata": {"scenario": identifier}, "datasetId": "dataset-test",
            "datasetName": dataset_name, "createdAt": stamp, "updatedAt": stamp,
            "version": stamp, "mediaReferences": []})

    def receive(request):
        path = request.url.path
        assert request.method == "GET", f"Unexpected SDK request: {request.method} {path}"
        if path == "/api/public/projects":
            return httpx.Response(200, json={"data": [{"id": "project-test", "name": "demo-test", "metadata": {}, "organization": {"id": "organization-test", "name": "Test"}}]})
        if path == f"/api/public/v2/datasets/{dataset_name}":
            return httpx.Response(200, json={"id": "dataset-test", "name": dataset_name,
                "projectId": "project-test", "metadata": {}, "createdAt": stamp, "updatedAt": stamp})
        if path == "/api/public/dataset-items":
            assert request.url.params["datasetName"] == dataset_name
            return httpx.Response(200, json={"data": items,
                "meta": {"page": 1, "limit": 50, "totalItems": 2, "totalPages": 1}})
        if path == f"/api/public/v2/prompts/{cfg.golden_path.prompt_name}":
            assert request.url.params["label"] == "development"
            return httpx.Response(200, json={"name": cfg.golden_path.prompt_name,
                "version": 2, "type": "chat", "config": {}, "labels": ["development"], "tags": [],
                "prompt": [{"role": "user", "content": "{{application}}"}]})
        raise AssertionError(f"Unexpected SDK request: {request.method} {path}")

    def complete(**kwargs):
        application = json.loads(kwargs["messages"][0]["content"])
        expected = next(item["expectedOutput"] for item in items
                        if item["id"] == application["applicant_id"])
        return SimpleNamespace(text=json.dumps({**expected, "reason": "Policy calculation."}),
                               input_tokens=120, output_tokens=40)

    exported = InMemorySpanExporter()
    client = Langfuse(base_url="http://langfuse.test", public_key=f"pk-test-{uuid.uuid4()}",
        secret_key="sk-test", span_exporter=exported,
        httpx_client=httpx.Client(transport=httpx.MockTransport(receive)))
    adapter = SimpleNamespace(langfuse=lambda: client,
        llm=lambda _: SimpleNamespace(provider="test", model="test-model", complete=complete))
    try:
        result = run_experiment(cfg, label="development", adapter=adapter, log=lambda _: None)
        assert result["outcome"].green and result["outcome"].total == 2
        sdk_result = result["result"]
        link = urlparse(result["run_url"])
        assert link.path == "/project/project-test/experiments/results"
        assert parse_qs(link.query) == {"baseline": [sdk_result.experiment_id]}
        assert result["run_url"] == sdk_result.experiment_url
        assert {item.item.id for item in sdk_result.item_results} == {"eligible", "above-line"}
        spans = exported.get_finished_spans()
        tasks = [span for span in spans if span.name == "experiment-item-task"]
        generations = [span for span in spans if span.name == "decision"]
        assert len(tasks) == len(generations) == 2
        for task in tasks:
            attrs = task.attributes
            assert attrs["langfuse.experiment.id"] == sdk_result.experiment_id
            assert attrs["langfuse.experiment.dataset.id"] == "dataset-test"
            original = next(item for item in items if item["id"] == attrs["langfuse.experiment.item.id"])
            assert json.loads(attrs["langfuse.observation.input"]) == original["input"]
            assert json.loads(attrs["langfuse.experiment.item.expected_output"]) == original["expectedOutput"]
            assert attrs["langfuse.experiment.item.root_observation_id"] == format(task.context.span_id, "016x")
            output = json.loads(attrs["langfuse.observation.output"])
            assert {key: output[key] for key in original["expectedOutput"]} == original["expectedOutput"]
            generation = next(span for span in generations if span.parent.span_id == task.context.span_id)
            assert generation.context.trace_id == task.context.trace_id
            assert generation.attributes["langfuse.observation.prompt.version"] == 2
            assert generation.attributes["langfuse.observation.prompt.name"] == cfg.golden_path.prompt_name
            assert json.loads(generation.attributes["langfuse.observation.usage_details"]) == {
                "input": 120, "output": 40}
    finally:
        client.shutdown()
