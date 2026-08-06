"""Run-state persistence.

``synth seed`` writes ``.synth_state.json`` capturing the concrete anchors of a run
(dates, prompt versions, dataset name, example trace ids + figures, project name).
``synth verify`` and ``synth script`` read it back so the demo runbook can never drift
from the seeded data (spec §18). The file is git-ignored — it is per-run output.

It lives in the spool dir, not the repo root — the per-run anchors rules of the
Contract (``langfuse-synth-core`` ``CONTRACT.md`` §"Per-run anchors (opt-in)" and
§"Filesystem conventions" · "The spool"): the spool is the only cross-container
surface, the artifact dir is container-local and would strand the file, and
``SYNTH_STATE_DIR`` names the location. This kit-local module predates the shared
core mechanism (portal #199) and is migration debt listed in that document.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILENAME = ".synth_state.json"


def state_dir() -> Path:
    """Where ``.synth_state.json`` lives — resolved at call time so a container ``ENV``
    or a shell export both work (the portal injects ``SYNTH_STATE_DIR``)."""
    env = os.environ.get("SYNTH_STATE_DIR")
    return Path(env) if env else REPO_ROOT / ".synth_spool"


def state_path() -> str:
    return str(state_dir() / STATE_FILENAME)


@dataclass
class RunState:
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

    def save(self, path: str | None = None) -> None:
        p = Path(path or state_path())
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: str | None = None) -> "RunState":
        data = json.loads(Path(path or state_path()).read_text())
        return cls(**data)

    @staticmethod
    def exists(path: str | None = None) -> bool:
        return Path(path or state_path()).exists()
