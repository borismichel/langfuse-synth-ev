"""Run-state persistence.

``synth seed`` writes ``.synth_state.json`` capturing the concrete anchors of a run
(dates, prompt versions, dataset name, example trace ids + figures, project name).
``synth verify`` and ``synth script`` read it back so the demo runbook can never drift
from the seeded data (spec §18). The file is git-ignored — it is per-run output.

The IO is the core anchors mechanism (``langfuse_synth_core.anchors``, portal #199): the
canonical filename, the location resolved from ``SYNTH_STATE_DIR`` at call time (the
spool volume — the Contract's per-run anchors rules, ``langfuse-synth-core``
``CONTRACT.md`` §"Per-run anchors (opt-in)"), and ``save``/``load``/``exists`` inherited
via :class:`AnchorsIO`. This module keeps only what is EV's: the payload fields the
kit's readers anchor on, and the dev-checkout fallback location.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from langfuse_synth_core.anchors import AnchorsIO
from langfuse_synth_core.anchors import state_dir as _state_dir
from langfuse_synth_core.anchors import state_path as _state_path

REPO_ROOT = Path(__file__).resolve().parents[2]
FALLBACK_STATE_DIR = REPO_ROOT / ".synth_spool"


def state_dir() -> Path:
    """Where ``.synth_state.json`` lives — ``SYNTH_STATE_DIR`` (the portal injects it)
    resolved at call time by core, else the dev checkout's spool dir."""
    return _state_dir(FALLBACK_STATE_DIR)


def state_path() -> str:
    return _state_path(FALLBACK_STATE_DIR)


@dataclass
class RunState(AnchorsIO):
    FALLBACK_STATE_DIR: ClassVar[Path] = FALLBACK_STATE_DIR

    base_url: str
    project_name: str
    run_date: str
    grant_effective_date: str
    drift_window: str
    drift_window_days: int
    prompt_name: str
    prompt_versions: dict
    dataset_name: str
    dataset_items: int
    judge_model: str
    task_model: str
    grant_amount_eur: int
    price_cap_eur: int
    summary: dict = field(default_factory=dict)
    disputed_example: dict = field(default_factory=dict)   # one dataset eligible FN, with figures
    reserved_example: dict = field(default_factory=dict)   # one reserved (live-add) trace, with figures
    control_example: dict = field(default_factory=dict)
    reserved_trace_ids: list = field(default_factory=list)
    project_id: str = ""
    dry_run: bool = False
