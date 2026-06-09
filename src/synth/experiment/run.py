"""The experiment runner the presenter runs in step 6 (spec §7).

Loads the hosted ``ev-grant-disputed-rejections`` dataset and runs **whatever prompt
carries the requested label** (default ``production``) as the task via the v4
``run_experiment`` API. The task is the SAME agent function used at seed time, pulling the
live labelled prompt — so the demo is: run ``production`` (== v1) → red; run
``development`` (== v2) → green to validate the fix **without touching production**; then
promote v2 to ``production`` and re-run. REAL model calls (temperature 0).

The managed UI judge (scoped to this dataset's new runs) scores each Dataset Run. We
leave ``evaluators`` empty so the managed judge is what scores it; an optional local
PASS-rate aggregate is available as a CI/CD regression-gate fallback.
"""
from __future__ import annotations

from typing import Callable

from ..agent import GrantRule, decide
from ..config import Config
from ..models import Application
from ..state import RunState


def _make_task(lf, anth, cfg: Config, label: str) -> Callable:
    prompt_name = cfg.golden_path.prompt_name
    model = cfg.golden_path.task_model

    def task(*args, **kwargs):
        item = kwargs.get("item") if "item" in kwargs else (args[0] if args else None)
        # SAME agent fn as seeding; runs whatever carries `label` right now.
        decision = decide(item.input, label, live=True, lf=lf, anth=anth,
                          prompt_name=prompt_name, model=model)
        return decision.model_dump()

    return task


def run_experiment(cfg: Config, *, label: str = "production", run_name: str = "ev-grant",
                   log: Callable[[str], None] = print):
    """Run the prompt carrying ``label`` against the hosted dataset. The run is named by
    label + version (``…-{label}-v{n}``) so the demo runs (production v1 red, development
    v2 green) land as distinct Dataset Runs in the comparison view (spec §7, §14)."""
    from ..lfclient import get_anthropic, get_langfuse

    lf = get_langfuse(cfg)
    anth = get_anthropic()
    prompt_name = cfg.golden_path.prompt_name

    try:
        prompt = lf.get_prompt(prompt_name, label=label, type="chat", cache_ttl_seconds=0)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"No {prompt_name!r} prompt labelled {label!r}. Re-seed (v1→production, "
            f"v2→development are set automatically) or set the label in the UI first."
        ) from exc
    ver = getattr(prompt, "version", "?")
    name = f"{run_name}-{label}-v{ver}"

    dataset = lf.get_dataset(cfg.golden_path.dataset.name)
    log(f"· {label} = {prompt_name} v{ver}; running it against "
        f"{cfg.golden_path.dataset.name!r} as {name!r} …")
    res = dataset.run_experiment(
        name=name,
        description=f"{label.capitalize()} prompt ({prompt_name} v{ver}) against the disputed dataset.",
        task=_make_task(lf, anth, cfg, label),
        # evaluators left empty: the managed UI judge (scoped to dataset runs) scores it.
    )
    log(res.format())
    lf.flush()
    return {"label": label, "version": ver, "result": res}


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
