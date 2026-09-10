"""Pre-seed the hosted golden-path dataset (spec §7, §16).

Creates ``ev-grant-disputed-rejections`` and its items via the datasets API. Each item:
- ``input``           = {"application": serialised application JSON} (native prompt variables)
- ``expected_output`` = the *correct* (v2) Decision — NOT the v1 wrong rejection
- ``metadata``        = eligibility flags ({eligible, borderline, scenario})
- ``source_trace_id`` = the disputed trace it was built from

The dataset is **hosted on Langfuse** so the live experiment renders as a Dataset Run
with comparison views (local datasets don't produce run rows). The reserved
false-negatives are deliberately NOT added here — they exist as traces for the live add.
"""
from __future__ import annotations

import pydantic

from ..models import Decision
from .golden_path import GoldenPath
from .demo_cohort import demonstration_items


# Native input is a JSON *string*, so JSON Schema's object properties cannot
# inspect it. Validate the canonical field order emitted by model_dump_json()
# with an ECMA-compatible JSON grammar; do not rely on contentSchema annotations
# (not enforced by every hosted validator). Whitespace is allowed for UI pasting.
_JSON_STRING = r'"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"'
_JSON_INTEGER = r'-?(?:0|[1-9][0-9]*)'
_WS = r'[ \t\r\n]*'
_APPLICATION_PATTERN = (
    r'^\{' + _WS + r'"applicant_id"' + _WS + ':' + _WS + _JSON_STRING + _WS + ',' + _WS
    + r'"approved_line_eur"' + _WS + ':' + _WS + _JSON_INTEGER + _WS + ',' + _WS
    + r'"vehicle"' + _WS + ':' + _WS + r'\{' + _WS
    + r'"type"' + _WS + ':' + _WS + r'"(?:BEV|PHEV|ICE)"' + _WS + ',' + _WS
    + r'"list_price_eur"' + _WS + ':' + _WS + _JSON_INTEGER + _WS + r'\}' + _WS + ',' + _WS
    + r'"application_date"' + _WS + ':' + _WS + r'"[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"'
    + _WS + r'\}$'
)

INPUT_SCHEMA = {
    "type": "object",
    "properties": {"application": {"type": "string", "pattern": _APPLICATION_PATTERN,
        "description": "Canonical Application JSON: applicant_id, approved_line_eur, vehicle (type, list_price_eur), application_date, in that order"}},
    "required": ["application"],
    "additionalProperties": False,
}


def _tolerate_v2_response(call, what: str):
    """Run an SDK write, tolerating a v2 self-hosted target's response shape.

    The langfuse 4.x SDK validates server responses against v3-era models; a
    Langfuse v2 server (self_hosted targets, e.g. 2.95.x) persists the write
    but its response predates fields the model requires (e.g.
    ``DatasetItem.media_references``) — the SDK then raises ValidationError
    AFTER the row exists. The write is what we need; parse failures on the
    echo are ignored so v2 targets keep working.
    """
    try:
        return call()
    except pydantic.ValidationError:
        return None


def create_dataset(lf, cfg, golden: GoldenPath) -> dict:
    ds = cfg.golden_path.dataset
    demo_name = f"{ds.name}-demo"
    demo_items = demonstration_items(golden.rule, demo_name)
    dataset = _tolerate_v2_response(lambda: lf.create_dataset(
        name=ds.name, input_schema=INPUT_SCHEMA,
        expected_output_schema=Decision.model_json_schema(),
        description=("Disputed EV-grant credit rejections: eligible false-negatives (should-approve) "
                     "plus correct-rejection controls. Built from backdated production traces."),
        metadata={"scenario": "ev-subsidy-regression", "grant_effective_date":
                  golden.effective_date.date().isoformat(), "seeded": True},
    ), "create_dataset")

    created = 0
    for it in golden.dataset_plan:
        _tolerate_v2_response(lambda it=it: lf.create_dataset_item(
            dataset_name=ds.name,
            id=it.item_id,
            input={"application": it.application.model_dump_json()},
            expected_output=it.expected.model_dump(),
            metadata={"eligible": it.eligible, "borderline": it.borderline,
                      "scenario": it.scenario},
            source_trace_id=it.source_trace_id,
        ), f"create_dataset_item {it.item_id}")
        created += 1

    demo_dataset = _tolerate_v2_response(lambda: lf.create_dataset(
        name=demo_name, input_schema=INPUT_SCHEMA,
        expected_output_schema=Decision.model_json_schema(),
        description="Small native prompt experiment cohort: fictional policy boundaries and controls.",
        metadata={"scenario": "ev-subsidy-regression", "seeded": True,
                  "grant_effective_date": golden.rule.effective_date},
    ), "create_demo_dataset")
    for row in demo_items:
        _tolerate_v2_response(lambda row=row: lf.create_dataset_item(
            dataset_name=demo_name, **row), f"create_demo_item {row['id']}")

    return {
        "name": ds.name,
        "id": getattr(dataset, "id", "") or "",
        "demo_name": demo_name,
        "demo_id": getattr(demo_dataset, "id", "") or "",
        "demo_items_created": len(demo_items),
        "items_created": created,
        "eligible_items": sum(1 for it in golden.dataset_plan if it.eligible),
        "control_items": sum(1 for it in golden.dataset_plan if not it.eligible),
        "reserved_trace_ids": golden.reserved_trace_ids,
    }


def reserved_items(golden: GoldenPath) -> list[dict]:
    """Reviewable UI curation payloads; never upload the reserved set during seed.

    Source observations establish provenance. Their stale v1 outputs are evidence,
    never expected outputs. These cases must qualify and approve under the grant rule.
    """
    rows = []
    reserved = set(golden.reserved_trace_ids)
    for spec in golden.disputed_specs:
        if spec.trace_id not in reserved:
            continue
        app = spec.application
        rule = golden.rule
        principal = app.vehicle.list_price_eur - rule.amount_eur
        if not rule.qualifies(app) or principal > app.approved_line_eur:
            raise ValueError(f"Reserved trace {spec.trace_id} is not an eligible false negative")
        basis = (f"BEV at EUR {app.vehicle.list_price_eur} <= cap EUR {rule.price_cap_eur}, "
                 f"dated {app.application_date} >= {rule.effective_date}; subtract EUR "
                 f"{rule.amount_eur} to finance EUR {principal} <= line EUR {app.approved_line_eur}.")
        expected = Decision(decision="approve", list_price_eur=app.vehicle.list_price_eur,
            applied_grant_eur=rule.amount_eur, financed_principal_eur=principal,
            approved_line_eur=app.approved_line_eur, reason=basis)
        row = {
            "input": {"application": app.model_dump_json()}, "expected_output": expected.model_dump(),
            "source_trace_id": spec.trace_id,
            "metadata": {"scenario": "false_negative", "eligible": True, "borderline": True,
                         "source": "reserved seeded observation", "expectation_basis": basis},
        }
        if spec.decision_obs_id:
            row["source_observation_id"] = spec.decision_obs_id
        rows.append(row)
    return rows
