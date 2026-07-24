"""Determinism law (spec §9): same (config, seed) => byte-identical output.

Two tiers, weakest to strongest:

* **plan-level repeatability** — two runs of the *same* code produce identical trace IDs
  and summary (the historical guarantee); and
* **the full-payload golden gate** (Spec A · Step 0 · #30) — a fresh materialization of the
  *entire pre-ingestion Spool* (traces + observations + scores) is byte-identical to a
  blessed golden snapshot, run offline in a subprocess under the deny-LLM egress block.
  This is the migration oracle: any refactor or story change that silently perturbs the
  deterministic pool fails here, loudly, before ingestion.
"""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from synth.config import load_config
from synth.rng import Rng
from synth.seed.generator import build_plan

RUN_DATE = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
CONFIG = "config/demo.yaml"


def _plan(seed=None):
    cfg = load_config(CONFIG)
    cfg.generation.total_traces = 300  # keep the test fast; determinism is scale-independent
    if seed is not None:
        cfg.generation.seed = seed
    return build_plan(cfg, RUN_DATE)


def test_same_seed_same_trace_ids():
    a = _plan()
    b = _plan()
    assert [s.trace_id for s in a.specs] == [s.trace_id for s in b.specs]
    assert a.summary == b.summary
    assert [it.item_id for it in a.golden.dataset_plan] == [it.item_id for it in b.golden.dataset_plan]


def test_different_seed_different_ids():
    a = _plan(seed=42)
    b = _plan(seed=43)
    assert [s.trace_id for s in a.specs] != [s.trace_id for s in b.specs]


def test_id_widths_are_w3c():
    rng = Rng(42)
    assert len(rng.trace_id("x")) == 32
    assert len(rng.obs_id("x")) == 16
    assert all(c in "0123456789abcdef" for c in rng.trace_id("x"))


# --------------------------------------------------------------------------------------
# Full-payload golden gate (Spec A · Step 0 · #30) — the byte-for-byte migration oracle.
# --------------------------------------------------------------------------------------
# The oracle is pinned at target_traces=300: the floor that still exercises the ambient
# `incident:cost_spike` window, while keeping the committed golden ~2.7 MB. The whole
# hand-authored narrative (golden-path disputes, the hosted dataset, multi-turn CSAT, and
# every score family) is present at this volume because those assets are config-sized, not
# ambient-scaled. KNOWN ORACLE BOUNDARY: `incident:error_burst` is so low-probability it
# only surfaces near production volume (~4000), so it is out of this oracle by design — see
# VERIFICATION.md. Re-bless deliberately with:
#     synth-authoring freeze golden_seed:seed \
#         --golden tests/golden/ev_spool.ndjson --target-traces 300 --search-path tests
GOLDEN_TARGET_TRACES = 300
GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "ev_spool.ndjson"
TESTS_DIR = str(Path(__file__).resolve().parent)


def _authoring_installed() -> bool:
    """True iff langfuse-synth-core[authoring] (the golden gate) is importable.

    Probes ``jsonschema`` — the [authoring] extra's marker dep, the same signal
    langfuse-synth-core's own gate tests skip on — so this matches what the gate actually
    needs to import. Guarded per-test, not at module scope, so the plan-level determinism
    tests above keep running on a bare install that has not pulled the dev extra."""
    return importlib.util.find_spec("jsonschema") is not None


def _golden_spec():
    from langfuse_synth_core.authoring.golden import GoldenSpec

    return GoldenSpec(
        seed_ref="golden_seed:seed",
        target_traces=GOLDEN_TARGET_TRACES,
        golden_path=GOLDEN_PATH,
        params={},
        search_paths=(TESTS_DIR,),
    )


@pytest.mark.skipif(
    not _authoring_installed(),
    reason="golden gate ships in langfuse-synth-core[authoring]; install the dev extra to run it",
)
def test_full_payload_golden_is_byte_identical():
    """A fresh full-Spool materialization is byte-identical to the blessed oracle.

    Runs `seed` in a subprocess under PYTHONHASHSEED=0 and the deny-LLM egress block, so
    this simultaneously proves the seed is deterministic AND model-free-at-seed-runtime."""
    from langfuse_synth_core.authoring.golden import assert_golden

    assert_golden(_golden_spec())


@pytest.mark.skipif(not _authoring_installed(), reason="requires langfuse-synth-core[authoring]")
def test_golden_is_full_payload_not_ids_and_summary():
    """The blessed oracle is the whole Spool — observations and scores, not just IDs."""
    blob = GOLDEN_PATH.read_bytes()
    assert b'"type":"trace-create"' in blob
    assert b'"type":"generation-create"' in blob
    assert b'"type":"score-create"' in blob

