"""The experiment runner the presenter runs in step 5 (spec §7).

Loads the hosted ``ev-grant-disputed-rejections`` dataset and runs **prompt v2** as the
task via the v4 ``run_experiment`` API. The task is the SAME agent function used at seed
time — only the prompt label is flipped to ``v2`` — so the experiment is the real
production path with the fixed prompt. This makes REAL model calls (temperature 0).

The managed UI judge (scoped to this dataset's new runs) scores the resulting Dataset
Run -> green. We leave ``evaluators`` empty so the managed judge is what scores it; an
optional local PASS-rate aggregate is available as a CI/CD regression-gate fallback.
"""
from __future__ import annotations

from typing import Callable

from ..agent import GrantRule, decide
from ..config import Config
from ..models import Application
from ..state import RunState


def _make_task(lf, anth, cfg: Config) -> Callable:
    prompt_name = cfg.golden_path.prompt_name
    model = cfg.golden_path.task_model

    def task(*args, **kwargs):
        item = kwargs.get("item") if "item" in kwargs else (args[0] if args else None)
        # SAME agent fn as seeding; the only lever is the prompt label -> "v2".
        decision = decide(item.input, "v2", live=True, lf=lf, anth=anth,
                          prompt_name=prompt_name, model=model)
        return decision.model_dump()

    return task


def run_experiment(cfg: Config, *, run_name: str = "ev-grant-fix",
                   baseline: bool = False, log: Callable[[str], None] = print):
    """Run v2 (the fix) against the hosted dataset. Optionally also run a v1 baseline
    for a side-by-side red/green comparison view (spec §7, §14)."""
    from ..lfclient import get_anthropic, get_langfuse

    lf = get_langfuse(cfg)
    anth = get_anthropic()
    dataset = lf.get_dataset(cfg.golden_path.dataset.name)

    results = {}
    if baseline:
        log("· running v1 baseline (for side-by-side comparison) …")
        v1_task = _v1_task(lf, anth, cfg)
        res_v1 = dataset.run_experiment(name=f"{run_name}-v1-baseline",
                                        description="Stale prompt (v1): no grant applied.",
                                        task=v1_task)
        log(res_v1.format())
        results["v1"] = res_v1

    log(f"· running v2 fix against hosted dataset {cfg.golden_path.dataset.name!r} …")
    task = _make_task(lf, anth, cfg)
    res_v2 = dataset.run_experiment(
        name=run_name,
        description="Fixed prompt (v2): EV purchase grant applied before affordability.",
        task=task,
        # evaluators left empty: the managed UI judge (scoped to dataset runs) scores it.
    )
    log(res_v2.format())
    results["v2"] = res_v2

    lf.flush()
    return results


def _v1_task(lf, anth, cfg: Config) -> Callable:
    prompt_name = cfg.golden_path.prompt_name
    model = cfg.golden_path.task_model

    def task(*args, **kwargs):
        item = kwargs.get("item") if "item" in kwargs else (args[0] if args else None)
        return decide(item.input, "v1", live=True, lf=lf, anth=anth,
                      prompt_name=prompt_name, model=model).model_dump()

    return task


# -- CI/CD regression-gate fallback (optional, offline arithmetic) ----------
def pass_rate_offline(cfg: Config, state: RunState) -> float:
    """Deterministic PASS-rate over the hosted dataset using v2 arithmetic + the judge rule.
    A code-only gate that needs no model — for a pipeline `synth experiment --gate`."""
    from ..lfclient import get_langfuse

    lf = get_langfuse(cfg)
    dataset = lf.get_dataset(cfg.golden_path.dataset.name)
    rule = GrantRule(amount_eur=cfg.golden_path.grant_amount_eur,
                     price_cap_eur=cfg.golden_path.price_cap_eur,
                     effective_date=state.grant_effective_date)
    passed = 0
    total = 0
    for item in dataset.items:
        app = Application.from_input(item.input)
        got = decide(app, "v2", rule=rule)
        expected = item.expected_output or {}
        total += 1
        if got.decision == expected.get("decision"):
            passed += 1
    return passed / total if total else 0.0
