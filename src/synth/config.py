"""Typed configuration loaded from ``config/demo.yaml``.

The full run is determined by ``(this config, generation.seed)``. Env vars supply
only secrets/URL (``LANGFUSE_*``, ``ANTHROPIC_API_KEY``); everything that affects
the *shape* of the generated data lives here so a run is auditable and reproducible.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Target(BaseModel):
    host: str = "http://localhost:3000"
    project_hint: str = "demo"

    @property
    def base_url(self) -> str:
        # env wins so the same config can target different instances
        return os.environ.get("LANGFUSE_BASE_URL", self.host).rstrip("/")


class Population(BaseModel):
    users: int = 120
    multi_turn_ratio: float = 0.35
    power_user_share: float = 0.06


class Environments(BaseModel):
    production_share: float = 0.92


class Generation(BaseModel):
    seed: int = 42
    archetype: str = "credit_approval_agent"
    total_traces: int = 4000
    window_days: int = 30
    population: Population = Field(default_factory=Population)
    environments: Environments = Field(default_factory=Environments)


class Model(BaseModel):
    name: str
    role: Literal["plan", "work", "light"]
    input_per_1k: float
    output_per_1k: float


class ModelMix(BaseModel):
    plan_step_share: float = 0.25
    light_calls_per_trace: tuple[int, int] = (1, 2)


class DatasetCfg(BaseModel):
    name: str = "ev-grant-disputed-rejections"
    n_items: int = 24
    eligible_share: float = 0.7
    n_reserved_for_live_add: int = 3


class GoldenPath(BaseModel):
    enabled: bool = True
    prompt_name: str = "credit_decision"
    judge_model: str = "claude-sonnet-4-6"
    task_model: str = "claude-sonnet-4-6"
    task_provider: Literal["anthropic", "bedrock"] = "anthropic"
    grant_effective_day_offset: int = -7
    drift_window_days: int = 5
    grant_amount_eur: int = 6000
    price_cap_eur: int = 50000
    dti_threshold: float = 0.45
    prompt_v1_register: bool = True
    prompt_v2_register: bool = True
    borderline_clustering: bool = True
    baseline_disagreement_rate: float = 0.03
    drift_disagreement_rate: float = 0.55
    dataset: DatasetCfg = Field(default_factory=DatasetCfg)


class Incident(BaseModel):
    enabled: bool = False
    day_offset: int = -10
    duration_hours: int = 6
    factor: float = 3.0


class AmbientIncidents(BaseModel):
    cost_spike: Incident = Field(default_factory=Incident)
    latency_degrade: Incident = Field(default_factory=Incident)
    error_burst: Incident = Field(default_factory=Incident)


class Scoring(BaseModel):
    # Coverage by instrument kind (spec §6): deterministic checks run on everything,
    # LLM-judges on a thin sample, customer surveys at a response rate.
    format_check_coverage: float = 1.0       # deterministic schema check — every trace
    quality_judge_ratio: float = 0.15        # LLM judge: answer_quality + tone (bundled)
    disagreement_judge_ratio: float = 0.15   # LLM judge: user_disagreement (ambient sample)
    csat_response_ratio: float = 0.3         # per-session customer survey response rate


class Config(BaseModel):
    target: Target = Field(default_factory=Target)
    generation: Generation = Field(default_factory=Generation)
    models: list[Model]
    model_mix: ModelMix = Field(default_factory=ModelMix)
    golden_path: GoldenPath = Field(default_factory=GoldenPath)
    ambient_incidents: AmbientIncidents = Field(default_factory=AmbientIncidents)
    scoring: Scoring = Field(default_factory=Scoring)

    # --- convenience accessors -------------------------------------------
    def model_by_role(self, role: str) -> Model:
        for m in self.models:
            if m.role == role:
                return m
        raise KeyError(f"no model configured for role={role!r}")


def _set_dotted(raw: dict, dotted_key: str, value) -> None:
    """Set ``value`` at the dotted path ``a.b.c`` in the raw config dict, creating
    intermediate mappings as needed (overwriting a non-mapping intermediate)."""
    keys = dotted_key.split(".")
    node = raw
    for k in keys[:-1]:
        child = node.get(k)
        if not isinstance(child, dict):
            child = {}
            node[k] = child
        node = child
    node[keys[-1]] = value


def apply_overrides(raw: dict, overrides: list[str] | None) -> dict:
    """Apply ``--set dotted.key=value`` overrides to the RAW yaml dict before validation.

    Each value is coerced with ``yaml.safe_load`` so ``800``→int, ``true``→bool,
    ``1.5``→float, quoted/other→str — matching how the same value would parse in the
    yaml file. Mutates and returns ``raw``. Used to let the portal scale a single
    shipped config via the manifest ``config_schema`` (e.g. ``generation.total_traces``).
    """
    for item in overrides or []:
        key, sep, rawval = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise ValueError(f"--set expects dotted.key=value, got {item!r}")
        _set_dotted(raw, key, yaml.safe_load(rawval))
    return raw


def load_config(path: str | Path, overrides: list[str] | None = None) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    apply_overrides(raw, overrides)
    return Config.model_validate(raw)
