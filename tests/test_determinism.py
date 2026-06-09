"""Same (config, seed) => byte-identical plan, including IDs (spec §9)."""
from datetime import datetime, timezone

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
