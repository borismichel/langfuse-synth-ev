"""Pre-seed the hosted golden-path dataset (spec §7, §16).

Creates ``ev-grant-disputed-rejections`` and its items via the datasets API. Each item:
- ``input``           = the application (the dataset-item input contract, §16)
- ``expected_output`` = the *correct* (v2) Decision — NOT the v1 wrong rejection
- ``metadata``        = eligibility flags ({eligible, borderline, scenario})
- ``source_trace_id`` = the disputed trace it was built from

The dataset is **hosted on Langfuse** so the live experiment renders as a Dataset Run
with comparison views (local datasets don't produce run rows). The reserved
false-negatives are deliberately NOT added here — they exist as traces for the live add.
"""
from __future__ import annotations

import pydantic

from .golden_path import GoldenPath


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
    _tolerate_v2_response(lambda: lf.create_dataset(
        name=ds.name,
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
            input=it.application.model_dump(),
            expected_output=it.expected.model_dump(),
            metadata={"eligible": it.eligible, "borderline": it.borderline,
                      "scenario": it.scenario},
            source_trace_id=it.source_trace_id,
        ), f"create_dataset_item {it.item_id}")
        created += 1

    return {
        "name": ds.name,
        "items_created": created,
        "eligible_items": sum(1 for it in golden.dataset_plan if it.eligible),
        "control_items": sum(1 for it in golden.dataset_plan if not it.eligible),
        "reserved_trace_ids": golden.reserved_trace_ids,
    }
