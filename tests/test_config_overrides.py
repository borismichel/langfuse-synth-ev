"""`--set dotted.key=value` overrides + the SYNTH_OUT_DIR artifact dir (E2a kit contract).

These cover the manifest integration surface: the portal scales the single shipped config
via `--set` (config_schema keys) and collects artifacts from SYNTH_OUT_DIR.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from synth import script
from synth.config import apply_overrides, load_config
from synth.state import REPO_ROOT

CONFIG = str(REPO_ROOT / "config" / "demo.yaml")


def test_apply_overrides_coerces_types_like_yaml():
    raw = {"generation": {}, "ambient_incidents": {"cost_spike": {}}}
    apply_overrides(raw, [
        "generation.total_traces=800",       # int
        "generation.window_days=14",          # int
        "ambient_incidents.cost_spike.enabled=false",  # bool
    ])
    assert raw["generation"]["total_traces"] == 800
    assert isinstance(raw["generation"]["total_traces"], int)
    assert raw["generation"]["window_days"] == 14
    assert raw["ambient_incidents"]["cost_spike"]["enabled"] is False


def test_apply_overrides_creates_missing_intermediate_mappings():
    raw = {}
    apply_overrides(raw, ["a.b.c=1.5"])  # float coercion + nested creation
    assert raw == {"a": {"b": {"c": 1.5}}}


@pytest.mark.parametrize("bad", ["nokey", "=value", "  =v"])
def test_apply_overrides_rejects_malformed(bad):
    with pytest.raises(ValueError):
        apply_overrides({}, [bad])


def test_load_config_applies_overrides_to_manifest_schema_keys():
    cfg = load_config(CONFIG, [
        "generation.total_traces=800",
        "generation.window_days=14",
        "ambient_incidents.cost_spike.enabled=false",
    ])
    assert cfg.generation.total_traces == 800
    assert cfg.generation.window_days == 14
    assert cfg.ambient_incidents.cost_spike.enabled is False


def test_load_config_without_overrides_is_unchanged():
    cfg = load_config(CONFIG)
    assert cfg.generation.total_traces == 4000  # shipped default


def test_output_dir_defaults_to_repo_root(monkeypatch):
    monkeypatch.delenv("SYNTH_OUT_DIR", raising=False)
    assert script.output_dir() == REPO_ROOT


def test_output_dir_honours_synth_out_dir(monkeypatch):
    monkeypatch.setenv("SYNTH_OUT_DIR", "/app/out")
    assert script.output_dir() == Path("/app/out")
