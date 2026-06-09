"""Seed orchestrator (spec §11 `synth seed`, order-of-creation §12).

    score configs -> prompt v1/v2 -> backdated traces + scores -> hosted dataset + items

The seed path makes **no model calls**: every trace (including the golden-path v1
rejections) is a deterministic, templated Decision ingested backdated via the batch API.
Writes ``.synth_state.json`` and committed v1 fixtures on the way out.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..config import Config
from ..state import REPO_ROOT, RunState
from ..timegen import iso_date, now_utc
from .generator import Plan, build_plan
from .ingest import Ingestor, assert_demo_project, ensure_score_config
from .scores import (
    SCORE_CONFIGS,
    csat_score,
    disagreement_score,
    quality_scores_for_trace,
)
from .traces import build_trace_events

FIXTURES_DIR = REPO_ROOT / "fixtures"


def run_seed(cfg: Config, *, dry_run: bool = False, persist: bool = True,
             run_date: datetime | None = None, log: Callable[[str], None] = print) -> RunState:
    run_date = run_date or now_utc()
    base_url = cfg.target.base_url

    # -- guardrail: never touch a non-demo project (spec §12) -------------
    project_name = "(dry-run)"
    project_id = ""
    if not dry_run:
        project_id, project_name = assert_demo_project(base_url, cfg.target.project_hint)
        log(f"✓ guardrail passed: project {project_name!r} matches hint {cfg.target.project_hint!r}")

    # -- plan (deterministic) ---------------------------------------------
    log("· building deterministic plan …")
    plan = build_plan(cfg, run_date)
    log(f"  {plan.summary['total_traces']} traces "
        f"({plan.summary['golden_disputed_traces']} golden-path), "
        f"{plan.summary['dataset_items']} dataset items, "
        f"{plan.summary['multi_turn_sessions']} multi-turn sessions")

    # -- 1. score configs -------------------------------------------------
    if not dry_run:
        for sc in SCORE_CONFIGS:
            ensure_score_config(base_url, sc)
        log(f"✓ {len(SCORE_CONFIGS)} score configs ensured")

    # -- 2. prompts (v1 first so its version == 1) ------------------------
    versions = {"v1": 1, "v2": 2}
    if cfg.golden_path.enabled and not dry_run:
        from ..lfclient import get_langfuse
        from .prompts import register_prompts

        lf = get_langfuse(cfg)
        versions = register_prompts(lf, cfg, plan.golden.effective_date,
                                    register_v1=cfg.golden_path.prompt_v1_register,
                                    register_v2=cfg.golden_path.prompt_v2_register)
        log(f"✓ prompts registered: {versions}")
    else:
        lf = None
    v1_version = versions.get("v1") if cfg.golden_path.prompt_v1_register else None

    # -- 3. backdated traces + scores -------------------------------------
    ing = Ingestor.from_env(base_url, dry_run=dry_run)
    n_events = _ingest_traces_and_scores(cfg, plan, v1_version, ing, log)
    log(f"✓ ingested {n_events} events across {len(plan.specs)} traces "
        f"({'dry-run, nothing sent' if dry_run else f'{ing.sent} sent'})")

    # -- 4. hosted dataset + items ----------------------------------------
    dataset_info = {"name": cfg.golden_path.dataset.name, "items_created": len(plan.golden.dataset_plan)}
    if cfg.golden_path.enabled and not dry_run:
        from .datasets import create_dataset

        dataset_info = create_dataset(lf, cfg, plan.golden)
        lf.flush()
        log(f"✓ dataset {dataset_info['name']!r}: {dataset_info['items_created']} items "
            f"({dataset_info['eligible_items']} eligible / {dataset_info['control_items']} control), "
            f"{len(plan.golden.reserved_trace_ids)} reserved for live add")

    # -- fixtures + state -------------------------------------------------
    state = _build_state(cfg, plan, versions, project_name, dataset_info, dry_run)
    state.project_id = project_id
    if persist:
        _write_fixtures(plan)
        state.save()
        log("✓ wrote run state and v1 fixtures")
    return state


def _ingest_traces_and_scores(cfg: Config, plan: Plan, v1_version, ing: Ingestor,
                              log: Callable[[str], None]) -> int:
    gp = cfg.golden_path
    auto_ratio = cfg.scoring.auto_score_ratio
    human_ratio = cfg.scoring.human_annotation_ratio
    rng = plan.rng
    total = 0

    for i, spec in enumerate(plan.specs):
        events = build_trace_events(rng, cfg, spec, v1_version)
        ing.extend(events)
        total += len(events)

        # quality scores (always green) on a realistic fraction
        ing.extend(quality_scores_for_trace(rng, spec.trace_id, spec.decision_obs_id,
                                            spec.timestamp, spec.environment, auto_ratio))
        # lagging human signal: elevated + guaranteed on the eligible false-negatives
        if spec.kind == "golden_eligible":
            ing.extend(disagreement_score(rng, spec.trace_id, spec.timestamp, spec.environment,
                                          gp.drift_disagreement_rate, human_ratio, force=True))
        else:
            ing.extend(disagreement_score(rng, spec.trace_id, spec.timestamp, spec.environment,
                                          gp.baseline_disagreement_rate, human_ratio))

        if ing.pending >= 400:
            ing.flush()

    # session-level csat on multi-turn sessions
    spec_by_id = {s.trace_id: s for s in plan.specs}
    for sid, trace_ids in plan.sessions.items():
        members = [spec_by_id[t] for t in trace_ids if t in spec_by_id]
        if not members:
            continue
        last = max(members, key=lambda s: s.timestamp)
        ing.add(csat_score(rng, sid, last.timestamp, last.environment))

    ing.flush()
    return total


def _write_fixtures(plan: Plan) -> None:
    """Commit the golden-path v1 decisions as fixtures: literal same-function provenance,
    zero per-seed model cost (spec §7). Bounded to the disputed set."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    rows = []
    for spec in plan.golden.disputed_specs:
        item = next((it for it in plan.golden.dataset_plan
                     if it.source_trace_id == spec.trace_id), None)
        rows.append({
            "trace_id": spec.trace_id,
            "applicant_id": spec.application.applicant_id,
            "kind": spec.kind,
            "application": spec.application.model_dump(),
            "decision_v1": spec.decision.model_dump(),
            "expected_v2": item.expected.model_dump() if item else None,
        })
    (FIXTURES_DIR / "golden_v1_decisions.json").write_text(json.dumps(rows, indent=2))


def _example(application, decision) -> dict:
    return {
        "applicant_id": application.applicant_id,
        "vehicle_type": application.vehicle.type,
        "list_price_eur": application.vehicle.list_price_eur,
        "approved_line_eur": application.approved_line_eur,
        "application_date": application.application_date,
        "decision": decision.decision,
        "financed_principal_eur": decision.financed_principal_eur,
        "applied_grant_eur": decision.applied_grant_eur,
    }


def _build_state(cfg: Config, plan: Plan, versions: dict, project_name: str,
                 dataset_info: dict, dry_run: bool) -> RunState:
    g = plan.golden
    spec_by_id = {s.trace_id: s for s in plan.specs}

    disputed_example = {}
    control_example = {}
    for it in g.dataset_plan:
        s = spec_by_id.get(it.source_trace_id)
        if not s:
            continue
        ex = {**_example(s.application, s.decision), "trace_id": it.source_trace_id,
              "expected_v2_decision": it.expected.decision,
              "expected_v2_financed_eur": it.expected.financed_principal_eur}
        if it.eligible and not disputed_example:
            disputed_example = ex
        if not it.eligible and not control_example:
            control_example = ex

    reserved_example = {}
    if g.reserved_trace_ids:
        s = spec_by_id.get(g.reserved_trace_ids[0])
        if s:
            from ..agent import decide
            exp = decide(s.application, "v2", rule=g.rule)
            reserved_example = {**_example(s.application, s.decision),
                                "trace_id": s.trace_id,
                                "expected_v2_decision": exp.decision,
                                "expected_v2_financed_eur": exp.financed_principal_eur}

    return RunState(
        base_url=cfg.target.base_url,
        project_name=project_name,
        run_date=plan.run_date.isoformat(),
        grant_effective_date=iso_date(g.effective_date),
        drift_window=plan.summary["drift_window"],
        drift_window_days=cfg.golden_path.drift_window_days,
        prompt_name=cfg.golden_path.prompt_name,
        prompt_versions=versions,
        dataset_name=cfg.golden_path.dataset.name,
        dataset_items=len(g.dataset_plan),
        judge_model=cfg.golden_path.judge_model,
        task_model=cfg.golden_path.task_model,
        grant_amount_eur=cfg.golden_path.grant_amount_eur,
        price_cap_eur=cfg.golden_path.price_cap_eur,
        summary=plan.summary,
        disputed_example=disputed_example,
        reserved_example=reserved_example,
        control_example=control_example,
        reserved_trace_ids=g.reserved_trace_ids,
        dry_run=dry_run,
    )
