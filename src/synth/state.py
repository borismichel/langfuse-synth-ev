"""Run-state persistence.

``synth seed`` writes ``.synth_state.json`` capturing the concrete anchors of a run
(dates, prompt versions, dataset name, example trace ids + figures, project name).
``synth verify`` and ``synth script`` read it back so the demo runbook can never drift
from the seeded data (spec §18). The file is git-ignored — it is per-run output.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = str(REPO_ROOT / ".synth_state.json")


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

    def save(self, path: str = STATE_PATH) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: str = STATE_PATH) -> "RunState":
        data = json.loads(Path(path).read_text())
        return cls(**data)

    @staticmethod
    def exists(path: str = STATE_PATH) -> bool:
        return Path(path).exists()
