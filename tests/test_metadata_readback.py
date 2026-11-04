"""Release checks reject persisted dotted or incomplete metadata exports."""
import json
import subprocess
import sys

import pytest


def observation():
    return {
        "id": "0123456789abcdef", "traceId": "a" * 32,
        "name": "decision", "type": "GENERATION", "promptName": "credit_decision", "promptVersion": 1,
        "metadata": {
            "prompt_variables": {
                "application": '{"applicant_id":"readback","approved_line_eur":32000,"vehicle":{"type":"BEV","list_price_eur":38000},"application_date":"2026-11-04"}',
                "handbook": '{"document_id":"LENDING-1","content":"Compare the financed amount to the approved line."}',
                "policy_updates": '[{"document_id":"BULLETIN-EV-1","content":"Deduct the EUR 6000 grant."}]',
            },
            "response_schema": {"type": "object", "properties": {"decision": {"type": "string", "enum": ["approve", "reject"]}}},
        },
    }


def verify(tmp_path, item):
    export = tmp_path / "observation.json"
    export.write_text(json.dumps({"status": 200, "body": {"data": [item]}}))
    return subprocess.run(
        [sys.executable, "-m", "synth.verify_metadata", str(export)],
        capture_output=True, text=True,
    )


def test_readback_accepts_existing_nested_metadata(tmp_path):
    result = verify(tmp_path, observation())
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)[0]
    assert receipt["trace_id"] == "a" * 32
    assert receipt["prompt_version"] == 1
    assert receipt["policy_update_count"] == 1
    assert "LANGFUSE" not in result.stdout


@pytest.mark.parametrize("failure", ["dotted", "missing", "null", "truncated", "object", "schema"])
def test_readback_fails_on_incompatible_or_missing_evidence(tmp_path, failure):
    item = observation()
    variables = item["metadata"]["prompt_variables"]
    if failure == "dotted":
        item["metadata"] = {f"prompt_variables.{key}": value for key, value in variables.items()}
    elif failure == "missing":
        del variables["policy_updates"]
    elif failure == "null":
        variables["policy_updates"] = "null"
    elif failure == "truncated":
        variables["policy_updates"] = '[{"content": "truncated'
    elif failure == "object":
        variables["policy_updates"] = "{}"
    else:
        del item["metadata"]["response_schema"]
    result = verify(tmp_path, item)
    assert result.returncode != 0
    assert "metadata check failed" in result.stderr
    assert result.stdout == ""


def test_readback_accepts_explicit_empty_updates(tmp_path):
    item = observation()
    item["metadata"]["prompt_variables"]["policy_updates"] = "[]"
    result = verify(tmp_path, item)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0]["policy_update_count"] == 0
