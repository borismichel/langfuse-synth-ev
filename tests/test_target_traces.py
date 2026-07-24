"""EV's operator surface is the canonical target_traces knob + direct-count hook (#33).

Acceptance (#33):
  * EV's operator surface is the canonical ``generation.target_traces``; no bespoke
    ``generation.total_traces`` operator knob remains (internal only);
  * the derivation hook does direct-count identity.

The manifest half (knob shape) is an authoring-time check (needs ``inject_target_traces``
behind the ``[authoring]`` extra / ``jsonschema``); the hook half is pure runtime.
"""

from __future__ import annotations

import importlib.util

import pytest
import yaml

from synth.config import (
    Config,
    direct_count_derivation,
    load_config,
    resolve_target_traces,
)

REPO_ROOT = __import__("synth.state", fromlist=["REPO_ROOT"]).REPO_ROOT
MANIFEST = REPO_ROOT / "usecase.yaml"

# The bounds EV declares for the canonical knob (must match usecase.yaml verbatim).
EV_MIN, EV_MAX, EV_DEFAULT = 100, 6000, 800
EV_TITLE = "Target traces"
EV_DESCRIPTION = (
    "Total number of backdated traces to generate — the single, uniform volume knob for "
    "this demo. 800 is Cloud-free-tier safe; 4000 is the full self-hosted story. The kit "
    "deterministically derives its internal generation params from it (EV: direct count)."
)

_authoring = importlib.util.find_spec("jsonschema") is not None


# --- the hook (runtime) --------------------------------------------------------------
def test_direct_count_is_identity_on_the_value():
    assert direct_count_derivation(800, {}) == {"total_traces": 800}
    assert direct_count_derivation(4000, {"anything": 1}) == {"total_traces": 4000}


def test_hook_satisfies_the_lib_derivation_contract():
    from langfuse_synth_core.derivation import DerivationHook

    hook: DerivationHook = direct_count_derivation
    assert hook(250, {}) == {"total_traces": 250}


def test_set_target_traces_derives_total_traces_at_load():
    cfg = load_config(str(REPO_ROOT / "config" / "demo.yaml"),
                      ["generation.target_traces=250"])
    assert cfg.generation.total_traces == 250
    assert cfg.generation.target_traces == 250


def test_unset_target_traces_keeps_the_internal_default():
    cfg = load_config(str(REPO_ROOT / "config" / "demo.yaml"))
    assert cfg.generation.target_traces is None
    assert cfg.generation.total_traces == 4000  # shipped internal default, untouched


def test_resolve_is_idempotent_and_returns_cfg():
    cfg = Config.model_validate(yaml.safe_load(
        (REPO_ROOT / "config" / "demo.yaml").read_text()))
    cfg.generation.target_traces = 900
    assert resolve_target_traces(cfg) is cfg
    assert cfg.generation.total_traces == 900
    resolve_target_traces(cfg)  # again — stable
    assert cfg.generation.total_traces == 900


# --- the manifest operator surface ---------------------------------------------------
def _config_schema() -> dict:
    return yaml.safe_load(MANIFEST.read_text())["config_schema"]["properties"]


def test_manifest_exposes_only_the_canonical_volume_knob():
    props = _config_schema()
    assert "generation.target_traces" in props
    # The bespoke operator knob is GONE from the operator surface (internal only now).
    assert "generation.total_traces" not in props


def test_canonical_knob_has_the_full_required_shape():
    knob = _config_schema()["generation.target_traces"]
    assert knob["type"] == "integer"
    assert (knob["minimum"], knob["maximum"], knob["default"]) == (EV_MIN, EV_MAX, EV_DEFAULT)
    assert knob["minimum"] <= knob["default"] <= knob["maximum"]
    for field in ("title", "description"):
        assert isinstance(knob[field], str) and knob[field]


@pytest.mark.skipif(not _authoring, reason="inject_target_traces lives behind [authoring]")
def test_manifest_knob_matches_the_sdk_injector_output():
    """The committed knob is exactly what the SDK one-liner would emit for EV's bounds —
    so the manifest can't drift from the canonical shape."""
    from langfuse_synth_core.authoring import inject_target_traces
    from langfuse_synth_core.derivation import TARGET_TRACES_KEY

    expected = inject_target_traces(
        minimum=EV_MIN, maximum=EV_MAX, default=EV_DEFAULT,
        title=EV_TITLE, description=EV_DESCRIPTION,
    )["properties"][TARGET_TRACES_KEY]
    assert _config_schema()["generation.target_traces"] == expected
