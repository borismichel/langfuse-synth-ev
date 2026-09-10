"""`synth script` — render DEMO_SCRIPT.md from run state (spec §18).

The talk-track prose is fixed (in the template); only the anchors — dates, trace ids,
figures, deep links, the judge prompt with the real grant date — are injected, so the
wording stays polished while the IDs stay accurate.
"""
from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Template

from .config import Config
from .state import REPO_ROOT, RunState

TEMPLATE_PATH = REPO_ROOT / "templates" / "demo_script.md.j2"


def output_dir() -> Path:
    """Where run artifacts (DEMO_SCRIPT.md) land.

    The portal collects artifacts from ``SYNTH_OUT_DIR`` (PLAN.md §5.1, set to
    ``/app/out`` in the kit image); local dev leaves it unset and falls back to the
    repo root. Resolved at call time so a container `ENV` or a shell export both work.
    """
    env = os.environ.get("SYNTH_OUT_DIR")
    return Path(env) if env else REPO_ROOT



def _deep_link(state: RunState, suffix: str, label: str) -> str:
    if not state.project_id:
        return ""
    return f" — [{label}]({state.base_url}/project/{state.project_id}/{suffix})"


def build_context(cfg: Config, state: RunState) -> dict:
    from .agent import GrantRule
    from .evaluation.package import judge_prompt
    prompt = judge_prompt(GrantRule(state.grant_amount_eur, state.price_cap_eur,
                                   state.grant_effective_date))
    disputed_tid = state.disputed_example.get("trace_id", "")
    reserved_tid = state.reserved_example.get("trace_id", "")
    return {
        **state.__dict__,
        "judge_prompt": prompt,
        "reserved_count": len(state.reserved_trace_ids),
        "drift_window_days_window": cfg.generation.window_days,
        "dashboard_link": _deep_link(state, "dashboards", "open"),
        "dataset_link": _deep_link(state, "datasets", "open"),
        "disputed_trace_link": _deep_link(state, f"traces/{disputed_tid}", "open") if disputed_tid else "",
        "reserved_trace_link": _deep_link(state, f"traces/{reserved_tid}", "open") if reserved_tid else "",
    }


def render_script(cfg: Config, state: RunState, *, out_path: Path | None = None) -> Path:
    if out_path is None:
        out_path = output_dir() / "DEMO_SCRIPT.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    template = Template(TEMPLATE_PATH.read_text())
    ctx = build_context(cfg, state)
    out_path.write_text(template.render(**ctx))
    return out_path
