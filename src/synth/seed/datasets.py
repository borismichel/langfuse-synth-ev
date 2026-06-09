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

from .golden_path import GoldenPath


def create_dataset(lf, cfg, golden: GoldenPath) -> dict:
    ds = cfg.golden_path.dataset
    lf.create_dataset(
        name=ds.name,
        description=("Disputed EV-grant credit rejections: eligible false-negatives (should-approve) "
                     "plus correct-rejection controls. Built from backdated production traces."),
        metadata={"scenario": "ev-subsidy-regression", "grant_effective_date":
                  golden.effective_date.date().isoformat(), "seeded": True},
    )

    created = 0
    for it in golden.dataset_plan:
        lf.create_dataset_item(
            dataset_name=ds.name,
            id=it.item_id,
            input=it.application.model_dump(),
            expected_output=it.expected.model_dump(),
            metadata={"eligible": it.eligible, "borderline": it.borderline,
                      "scenario": it.scenario},
            source_trace_id=it.source_trace_id,
        )
        created += 1

    return {
        "name": ds.name,
        "items_created": created,
        "eligible_items": sum(1 for it in golden.dataset_plan if it.eligible),
        "control_items": sum(1 for it in golden.dataset_plan if not it.eligible),
        "reserved_trace_ids": golden.reserved_trace_ids,
    }
