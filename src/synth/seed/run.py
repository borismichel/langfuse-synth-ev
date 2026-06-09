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
    format_compliance_score,
    quality_judge_scores,
)
from ..content import customer_appeal
from .traces import build_trace_events

FIXTURES_DIR = REPO_ROOT / "fixtures"
DEFAULT_SPOOL = REPO_ROOT / ".synth_spool" / "events.ndjson"


def run_seed(cfg: Config, *, dry_run: bool = False, persist: bool = True,
             run_date: datetime | None = None, spool_path: str | Path | None = None,
             do_import: bool = True, log: Callable[[str], None] = print) -> RunState:
    run_date = run_date or now_utc()
    base_url = cfg.target.base_url
    spool_path = Path(spool_path) if spool_path else DEFAULT_SPOOL

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
        from .prompts import register_prompts, set_version_labels

        lf = get_langfuse(cfg)
        versions = register_prompts(lf, cfg, plan.golden.effective_date,
                                    register_v1=cfg.golden_path.prompt_v1_register,
                                    register_v2=cfg.golden_path.prompt_v2_register)
        log(f"✓ prompts registered: {versions}")
        # Environment labels: production -> v1 (stale incumbent), development -> v2 (the fix).
        # The experiment runs `production` red, then `development` validates v2 before promotion.
        pname = cfg.golden_path.prompt_name
        for key, labels in (("v1", ["v1", "production"]), ("v2", ["v2", "development"])):
            if versions.get(key):
                try:
                    set_version_labels(base_url, pname, versions[key], labels)
                    log(f"✓ labels {labels} -> {pname} v{versions[key]}")
                except Exception as exc:  # noqa: BLE001 — non-fatal; set it in the UI
                    log(f"⚠ could not set labels {labels} (set in the UI): {exc}")
    else:
        lf = None
    v1_version = versions.get("v1") if cfg.golden_path.prompt_v1_register else None

    # -- 3. backdated traces + scores -------------------------------------
    # Phase 3a: generate every event straight to an NDJSON spool on disk.
    # Phase 3b: batch-import that file in chunks. Decoupling the two means a
    # wedged/slow upload never loses the generated data — re-import to resume.
    ing = Ingestor.from_env(base_url, dry_run=dry_run, spool_path=spool_path)
    n_events = _spool_traces_and_scores(cfg, plan, v1_version, ing, log)
    log(f"✓ generated {ing.spooled} events across {len(plan.specs)} traces "
        f"→ spooled to {spool_path}")
    if dry_run:
        log("  dry-run: spool written, nothing imported")
    elif not do_import:
        log("  --no-import: spool written, skipping batch import (resume with `synth import-spool`)")
    else:
        log(f"· batch-importing {ing.spooled} events from disk (chunks of {ing.chunk_size}) …")
        ing.import_spool(log=log)
        log(f"✓ batch-imported {ing.sent} events")

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


def _spool_traces_and_scores(cfg: Config, plan: Plan, v1_version, ing: Ingestor,
                             log: Callable[[str], None]) -> int:
    """Phase 3a — write every trace/score event to the NDJSON spool on disk.

    No network here: generation is CPU-bound and deterministic, so we stream it to
    disk and let :meth:`Ingestor.import_spool` do the uploading in a separate pass."""
    gp = cfg.golden_path
    sc = cfg.scoring
    rng = plan.rng
    total = 0

    ing.open_spool()
    try:
        for i, spec in enumerate(plan.specs):
            # 1. disagreement judge first — its verdict drives the `disputed` tag, which has
            #    to be set on the trace *before* we build it. The eligible false-negatives are
            #    the cases customers contest, so the judge is forced true on them.
            if spec.kind == "golden_eligible":
                appeal = customer_appeal(rng, spec.trace_id, spec.application, gp.grant_amount_eur)
                dis_events, disagree = disagreement_score(
                    rng, spec.trace_id, spec.timestamp, spec.environment,
                    gp.drift_disagreement_rate, sc.disagreement_judge_ratio,
                    force=True, force_disagree=True, comment=appeal)
            else:
                dis_events, disagree = disagreement_score(
                    rng, spec.trace_id, spec.timestamp, spec.environment,
                    gp.baseline_disagreement_rate, sc.disagreement_judge_ratio)
            if disagree and "disputed" not in spec.tags:
                spec.tags = [*spec.tags, "disputed"]

            # 2. build the trace (now carries `disputed` iff the judge fired true)
            events = build_trace_events(rng, cfg, spec, v1_version)
            ing.extend(events)
            total += len(events)

            # 3. deterministic format check on every trace; quality judge on a thin sample
            ing.extend(format_compliance_score(rng, spec.trace_id, spec.timestamp, spec.environment))
            ing.extend(quality_judge_scores(rng, spec.trace_id, spec.decision_obs_id,
                                            spec.timestamp, spec.environment, sc.quality_judge_ratio))
            ing.extend(dis_events)

        # per-session csat survey at a response rate
        spec_by_id = {s.trace_id: s for s in plan.specs}
        for sid, trace_ids in plan.sessions.items():
            members = [spec_by_id[t] for t in trace_ids if t in spec_by_id]
            if not members:
                continue
            if not rng.sub("csatsample", sid).chance(sc.csat_response_ratio):
                continue
            last = max(members, key=lambda s: s.timestamp)
            ing.add(csat_score(rng, sid, last.timestamp, last.environment))
    finally:
        ing.close_spool()
    return total


def import_spool_file(cfg: Config, spool_path: str | Path | None = None,
                      log: Callable[[str], None] = print) -> int:
    """Recovery / resume entry point: batch-import an existing spool without regenerating.

    Use after an interrupted upload — idempotent ids make the re-import upsert."""
    base_url = cfg.target.base_url
    path = Path(spool_path) if spool_path else DEFAULT_SPOOL
    _project_id, project_name = assert_demo_project(base_url, cfg.target.project_hint)
    log(f"✓ guardrail passed: project {project_name!r} matches hint {cfg.target.project_hint!r}")
    ing = Ingestor.from_env(base_url, spool_path=path)
    log(f"· batch-importing from {path} (chunks of {ing.chunk_size}) …")
    ing.import_spool(log=log)
    log(f"✓ batch-imported {ing.sent} events")
    return ing.sent


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
