"""Typed configuration loaded from ``config/demo.yaml``.

The full run is determined by ``(this config, generation.seed)``. Env vars supply
only secrets/URL (``LANGFUSE_*``, ``ANTHROPIC_API_KEY``); everything that affects
the *shape* of the generated data lives here so a run is auditable and reproducible.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

from langfuse_synth_core import config as core_config
from langfuse_synth_core.derivation import DerivationHook


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
    # `target_traces` is the CANONICAL, cross-kit operator volume knob (the portal passes
    # `--set generation.target_traces=N`). It is resolved to the internal `total_traces`
    # below via EV's direct-count derivation hook. None (the local/default case) means "no
    # operator knob set" → fall back to the `total_traces` internal default. `total_traces`
    # is now INTERNAL only — no longer an operator knob in the manifest (Ring 2, #33).
    target_traces: int | None = None
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


# The load-and-override *mechanism* moved into the lib (Ring 2, #33) as
# "library-with-parameters": reading YAML and applying `--set dotted.key=value` is
# scenario-agnostic plumbing. EV keeps its own concrete pydantic models above and passes
# `Config.model_validate` as the factory. `apply_overrides` is re-exported so the kit's own
# override tests and any callers keep their import surface.
apply_overrides = core_config.apply_overrides


# --- the canonical target_traces knob → EV internals (derivation hook, #29/#33) ---------
#
# EV's derivation is a **direct count (identity)**: the operator's `target_traces` IS the
# absolute number of backdated traces to generate, so it maps straight onto EV's internal
# `total_traces` knob. This is the kit-side, deterministic `DerivationHook` the contract
# describes — it runs at seed time (here, at config-load). The lib ships an
# `identity_derivation`, but its key is the generic `"target_traces"`; EV names its own
# internal knob `"total_traces"`, so the mapping lives here in the kit.
def direct_count_derivation(target_traces: int, declared: Mapping[str, Any]) -> Mapping[str, Any]:
    """EV direct count: ``target_traces -> {"total_traces": target_traces}`` (identity value).

    ``declared`` (the other declared generation params) completes the ``DerivationHook``
    signature and is intentionally ignored — EV's volume is a pure count, derived from
    nothing but the knob itself."""
    return {"total_traces": int(target_traces)}


# Assert the kit hook satisfies the lib's DerivationHook contract at import time.
_EV_DERIVATION: DerivationHook = direct_count_derivation


def resolve_target_traces(cfg: Config) -> Config:
    """Resolve the canonical ``generation.target_traces`` operator knob to EV's internal
    ``generation.total_traces`` via the direct-count hook. No-op when the knob is unset
    (local/default runs keep the shipped ``total_traces``). Mutates and returns ``cfg``."""
    tt = cfg.generation.target_traces
    if tt is not None:
        declared = cfg.generation.model_dump(exclude={"target_traces", "total_traces"})
        cfg.generation.total_traces = int(direct_count_derivation(tt, declared)["total_traces"])
    return cfg


def load_config(path: str | Path, overrides: list[str] | None = None) -> Config:
    """Load ``config/demo.yaml`` into EV's :class:`Config`, applying ``--set`` overrides.

    Delegates the YAML-read + override plumbing to the shared lib loader; the pydantic
    model is EV's own. The canonical ``generation.target_traces`` operator knob is resolved
    to EV's internal ``generation.total_traces`` here via the kit-side direct-count
    derivation hook (see :func:`resolve_target_traces`), so every command (plan/seed/verify)
    sees the derived volume."""
    cfg: Config = core_config.load_config(path, Config.model_validate, overrides)
    resolve_target_traces(cfg)
    return cfg
