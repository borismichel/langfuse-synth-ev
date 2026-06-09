"""`synth script` — render DEMO_SCRIPT.md from run state (spec §18).

The talk-track prose is fixed (in the template); only the anchors — dates, trace ids,
figures, deep links, the judge prompt with the real grant date — are injected, so the
wording stays polished while the IDs stay accurate.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from .config import Config
from .state import REPO_ROOT, RunState

TEMPLATE_PATH = REPO_ROOT / "templates" / "demo_script.md.j2"
OUTPUT_PATH = REPO_ROOT / "DEMO_SCRIPT.md"

# The reference-grounded judge prompt (spec §16), with {{grant_date}} baked to the run.
_JUDGE_PROMPT = """You are auditing a vehicle-loan credit decision for correctness under current policy.

REFERENCE (authoritative, effective {grant_date}):
- Eligible: battery-electric vehicles (BEV) with list price <= EUR {price_cap}.
- Benefit: EUR {grant_amount} deducted at point of sale, reducing the financed principal.
- Rule: approve if financed principal <= the applicant's approved credit line.

APPLICATION:          {{{{input}}}}
DECISION UNDER REVIEW: {{{{output}}}}

Decide PASS or FAIL with a one-sentence reason. FAIL if the application was
eligible (BEV, <= EUR {price_cap}, on/after the effective date) but the grant was
not applied, or if the resulting approve/reject decision is wrong as a result.
Respond as JSON: {{{{"verdict": "PASS" | "FAIL", "reason": "..."}}}}"""


def _deep_link(state: RunState, suffix: str, label: str) -> str:
    if not state.project_id:
        return ""
    return f" — [{label}]({state.base_url}/project/{state.project_id}/{suffix})"


def build_context(cfg: Config, state: RunState) -> dict:
    judge_prompt = _JUDGE_PROMPT.format(
        grant_date=state.grant_effective_date,
        price_cap=f"{state.price_cap_eur:,}",
        grant_amount=f"{state.grant_amount_eur:,}",
    )
    disputed_tid = state.disputed_example.get("trace_id", "")
    reserved_tid = state.reserved_example.get("trace_id", "")
    return {
        **state.__dict__,
        "judge_prompt": judge_prompt,
        "reserved_count": len(state.reserved_trace_ids),
        "drift_window_days_window": cfg.generation.window_days,
        "dashboard_link": _deep_link(state, "dashboards", "open"),
        "dataset_link": _deep_link(state, "datasets", "open"),
        "disputed_trace_link": _deep_link(state, f"traces/{disputed_tid}", "open") if disputed_tid else "",
        "reserved_trace_link": _deep_link(state, f"traces/{reserved_tid}", "open") if reserved_tid else "",
    }


def render_script(cfg: Config, state: RunState, *, out_path: Path = OUTPUT_PATH) -> Path:
    template = Template(TEMPLATE_PATH.read_text())
    ctx = build_context(cfg, state)
    out_path.write_text(template.render(**ctx))
    return out_path
