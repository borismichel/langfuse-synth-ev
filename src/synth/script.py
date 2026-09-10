"""Render the Presenter Runbook from saved deployment anchors, without network calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

from jinja2 import StrictUndefined, Template

from .config import Config
from .state import REPO_ROOT, RunState

TEMPLATE_PATH = REPO_ROOT / "templates" / "demo_script.md.j2"


def output_dir() -> Path:
    """Use the portal artifact directory, or the repository for local development."""
    env = os.environ.get("SYNTH_OUT_DIR")
    return Path(env) if env else REPO_ROOT


def _deep_link(state: RunState, suffix: str, label: str) -> str:
    if not state.project_id or state.dry_run:
        return ""
    if suffix.startswith("traces/") and state.history_imported is False:
        return ""
    return f"[{label}]({state.base_url.rstrip('/')}/project/{quote(state.project_id, safe='')}/{suffix})"


def build_context(cfg: Config, state: RunState) -> dict:
    """Only saved anchors describe this run; current config may have changed since seed."""
    from .agent import GrantRule
    from .evaluation.package import judge_prompt

    prompt_path = "prompts/" + quote(state.prompt_name, safe="")
    demo_path = (f"datasets/{quote(state.demo_dataset_id, safe='')}/items"
                 if state.demo_dataset_id else "datasets")
    links = {
        "project_link": _deep_link(state, "", "Langfuse project"),
        "datasets_link": _deep_link(state, "datasets", "Open datasets"),
        "dataset_link": _deep_link(state, demo_path, "Open datasets"),
        "prompt_link": _deep_link(state, prompt_path, "Open managed prompt"),
        "disputed_trace_link": "",
        "reserved_trace_link": "",
        "control_trace_link": "",
    }
    if state.dataset_id:
        links["datasets_link"] = _deep_link(
            state, f"datasets/{quote(state.dataset_id, safe='')}/items", "Open regression dataset")
    for kind in ("disputed", "reserved", "control"):
        example = getattr(state, f"{kind}_example")
        if example.get("trace_id"):
            links[f"{kind}_trace_link"] = _deep_link(
                state, f"traces/{quote(example['trace_id'], safe='')}", f"Open {kind} example")
    return {
        **state.__dict__,
        **links,
        "judge_prompt": judge_prompt(GrantRule(state.grant_amount_eur, state.price_cap_eur,
                                               state.grant_effective_date)),
        "reserved_count": len(state.reserved_trace_ids),
        "reserved_input_json": json.dumps(state.reserved_item.get("input"), indent=2),
        "reserved_expected_json": json.dumps(state.reserved_item.get("expected_output"), indent=2),
    }


def render_script(cfg: Config, state: RunState, *, out_path: Path | None = None) -> Path:
    if out_path is None:
        out_path = output_dir() / "DEMO_SCRIPT.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    template = Template(TEMPLATE_PATH.read_text(), undefined=StrictUndefined,
                        lstrip_blocks=True)
    out_path.write_text(template.render(**build_context(cfg, state)) + "\n")
    return out_path
