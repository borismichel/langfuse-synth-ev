"""Released presets retain the presenter story through generation and verify."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from langfuse_synth_core import read
from synth import verify
from synth.config import load_config
from synth.seed.generator import build_plan
from synth.seed.run import run_seed
from synth.script import render_script


@pytest.mark.parametrize(
    "host,mode,count",
    [
        ("cloud_eu", "presentation", 800),
        ("self_hosted", "presentation", 800),
        ("cloud_eu", "quick_rehearsal", 300),
    ],
)
@pytest.mark.parametrize("days", [14, 30])
def test_preset_generation_passes_actual_verify_from_its_emitted_evidence(
    tmp_path, monkeypatch, host, mode, count, days
):
    doc = yaml.safe_load(Path("usecase.yaml").read_text())
    values = {
        key: schema["default"]
        for key, schema in doc["config_schema"]["properties"].items()
        if "default" in schema
    }
    values.update(doc["setup"]["host_defaults"][host])
    if mode == "quick_rehearsal":
        values.update(doc["setup"]["presets"][mode]["values"])
    values["generation.window_days"] = days
    cfg = load_config(
        "config/demo.yaml",
        overrides=[f"{key}={json.dumps(value)}" for key, value in values.items()],
    )
    anchor = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
    plan = build_plan(cfg, anchor)
    import synth.seed.run as seed

    monkeypatch.setenv("SYNTH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(seed, "FIXTURES_DIR", tmp_path / "fixtures")
    spool = tmp_path / "events.ndjson"
    state = run_seed(
        cfg,
        dry_run=True,
        persist=True,
        run_date=anchor,
        spool_path=spool,
        do_import=False,
        log=lambda _: None,
    )
    assert plan.summary["total_traces"] == count
    assert state.dataset_items == 24
    assert len(state.reserved_trace_ids) == 3
    events = [json.loads(line) for line in spool.read_text().splitlines()]
    observations = []
    scores = []
    for event in events:
        if event.get("type") == "score-create":
            body = event["body"]
            scores.append(
                {
                    **body,
                    "timestamp": body.get("timestamp", event.get("timestamp")),
                    "subject": {"kind": "trace", "id": body.get("traceId")},
                }
            )
        elif "spanId" in event:
            attrs = {
                a["key"]: a["value"]["stringValue"]
                if "stringValue" in a["value"]
                else int(a["value"]["intValue"])
                if "intValue" in a["value"]
                else None
                for a in event["attributes"]
            }
            observations.append(
                {
                    "id": event["spanId"],
                    "traceId": event["traceId"],
                    "name": event["name"],
                    "type": str(attrs.get("langfuse.observation.type", "span")).upper(),
                    "startTime": datetime.fromtimestamp(
                        int(event["startTimeUnixNano"]) / 1e9, timezone.utc
                    ).isoformat(),
                    "input": attrs.get("langfuse.observation.input"),
                    "promptName": attrs.get("langfuse.observation.prompt.name"),
                    "promptVersion": attrs.get("langfuse.observation.prompt.version"),
                }
            )

    class Response:
        status_code = 200

        def __init__(self, data):
            self.data = data

        def json(self):
            return {"data": self.data, "meta": {}}

        def raise_for_status(self):
            pass

    def transport(method, url, *, params=None, **kwargs):
        params = params or {}
        if url.endswith("/api/public/v2/observations"):
            return Response(
                [
                    row
                    for row in observations
                    if not params.get("traceId") or row["traceId"] == params["traceId"]
                ]
            )
        if url.endswith("/api/public/v3/scores"):
            return Response(
                [row for row in scores if row["name"] == params.get("name")]
            )
        raise AssertionError(url)

    monkeypatch.setattr(read, "request_retry", transport)
    monkeypatch.setattr(
        verify,
        "get_json",
        lambda *a, **kw: {
            "data": [
                {"sourceTraceId": row.source_trace_id}
                for row in plan.golden.dataset_plan
            ]
        },
    )
    report = verify.run_verify(cfg, state, log=lambda _: None)
    assert report.ok, [
        (check.name, check.detail) for check in report.checks if not check.ok
    ]
    monkeypatch.setenv("SYNTH_OUT_DIR", str(tmp_path / "out"))
    runbook = render_script(cfg, state)
    for artifact in doc["artifacts"]:
        assert (runbook.parent / artifact["path"]).is_file()
    text = runbook.read_text()
    items = (runbook.parent / "NATIVE_EXPERIMENT_ITEMS.json").read_text()
    assert state.reserved_trace_ids[0] in items
    assert "24" in text and "production" in text
