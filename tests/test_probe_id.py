"""The probe trace id must be UNIQUE per run, not deterministic (LAN-324).

A id keyed only off ``generation.seed`` collides across every deployment to the same
project and can land on a tombstoned id after cleanup. ``probe._probe_ids`` salts the
throwaway probe ids with a per-run nonce; these tests guard that behaviour so it can't
silently regress back to a fixed id.
"""
from __future__ import annotations

from synth.probe import _probe_ids
from synth.rng import Rng

# The pre-fix collision id (seed 42, deterministic) documented on LAN-324.
OLD_COLLISION_TID = "ebc16bd0f806178ea49c5e8d0d546015"


def test_probe_ids_differ_across_runs_with_the_same_seed():
    rng = Rng(42)
    t1, o1 = _probe_ids(rng)
    t2, o2 = _probe_ids(rng)
    assert t1 != t2, "probe trace id must be unique per run, not deterministic"
    assert o1 != o2, "probe marker obs id must be unique per run too"


def test_probe_ids_never_reuse_the_old_deterministic_collision():
    rng = Rng(42)
    for _ in range(50):
        tid, _obs = _probe_ids(rng)
        assert tid != OLD_COLLISION_TID


def test_probe_ids_keep_w3c_trace_context_widths():
    tid, obs = _probe_ids(Rng(42))
    assert len(tid) == 32 and int(tid, 16) >= 0   # 16-byte trace id, valid hex
    assert len(obs) == 16 and int(obs, 16) >= 0   # 8-byte observation id, valid hex
