"""Public exported evaluator: deployment policy, native inputs and complete amounts."""
import json
import runpy
from types import SimpleNamespace

import pytest

from synth.agent import GrantRule
from synth.evaluation.package import evaluator_source
from synth.models import Application
from synth.policy import policy_variables
from synth.seed.prompts import chat_prompt

RULE = GrantRule(amount_eur=6000, price_cap_eur=50000, effective_date="2026-06-02")
APPLICATION = {"applicant_id": "reviewed-flagship", "approved_line_eur": 40000,
    "vehicle": {"type": "BEV", "list_price_eur": 45000}, "application_date": "2026-06-02"}
CORRECT = {"list_price_eur": 45000, "applied_grant_eur": 6000,
    "financed_principal_eur": 39000, "approved_line_eur": 40000,
    "decision": "approve", "reason": "45000 - 6000 = 39000 <= 40000"}


@pytest.fixture
def evaluate(tmp_path):
    path = tmp_path / "POLICY_EVALUATOR.py"
    path.write_text(evaluator_source(RULE))
    return runpy.run_path(str(path))["evaluate"]


def score(evaluate, input, output):
    return evaluate(SimpleNamespace(observation=SimpleNamespace(input=input, output=output))).scores[0]


@pytest.mark.parametrize("field,wrong", [("list_price_eur", 44999), ("approved_line_eur", 40001),
    ("applied_grant_eur", 0), ("financed_principal_eur", 45000), ("decision", "reject")])
def test_correct_label_does_not_hide_any_incorrect_financing_field(evaluate, field, wrong):
    assert score(evaluate, APPLICATION, CORRECT).value is True
    result = score(evaluate, APPLICATION, {**CORRECT, field: wrong})
    assert result.value is False
    assert field in result.comment
    assert result.metadata["status"] == "policy_error"


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.parametrize("encoded", [False, True])
def test_native_compiled_prompt_uses_complete_policy_truth(evaluate, version, encoded):
    from langfuse.api import ChatPrompt
    from langfuse.model import ChatPromptClient
    variables = policy_variables(Application.model_validate(APPLICATION), RULE)
    client = ChatPromptClient(ChatPrompt(name="credit_decision", version=1,
        prompt=chat_prompt(version), labels=[], tags=[], config={}))
    observed = client.compile(**variables)
    observed = json.dumps(observed) if encoded else observed
    # Baseline input omits the bulletin. The evaluator still knows the full policy.
    stale = {**CORRECT, "applied_grant_eur": 0, "financed_principal_eur": 45000, "decision": "reject"}
    assert score(evaluate, observed, stale).value is False
    assert score(evaluate, observed, [{"role": "assistant", "content": json.dumps(CORRECT)}]).value is True


@pytest.mark.parametrize("output", [None, {"error": "provider unavailable"}, "not JSON",
    {k: v for k, v in CORRECT.items() if k != "reason"},
    {**CORRECT, "approved_line_eur": "40000"}, {**CORRECT, "reason": None},
    {**CORRECT, "alternative_decision": "reject"},
    json.dumps(CORRECT) + "\n" + json.dumps({**CORRECT, "decision": "reject"})])
def test_missing_malformed_or_conflicting_output_is_never_a_pass(evaluate, output):
    result = score(evaluate, APPLICATION, output)
    assert result.value is False
    assert result.metadata["status"] == "malformed_output"


def test_exported_package_calibrates_native_inputs_and_wrong_amounts(tmp_path):
    from datetime import datetime, timezone
    from synth.config import load_config
    from synth.evaluation.package import write_package
    from synth.seed.generator import build_plan

    cfg = load_config("config/demo.yaml", overrides=["generation.target_traces=100"])
    write_package(build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc)), tmp_path)
    manifest = json.loads((tmp_path / "POLICY_EVALUATION.json").read_text())
    evaluate = runpy.run_path(str(tmp_path / "POLICY_EVALUATOR.py"))["evaluate"]
    names = {row["name"] for row in manifest["editor_examples"]}
    assert {"correct_reject_wrong_list_price", "correct_reject_wrong_line",
            "baseline_compiled_input", "candidate_compiled_input"} <= names
    for row in manifest["editor_examples"]:
        actual = score(evaluate, row["observation"]["input"], row["observation"]["output"])
        assert actual.value is row["expected_score"], row["name"]
    assert manifest["experiment"]["expected_count_before_curation"] == 8
