"""Realistic distributions (spec §5): log-normal latency, model-appropriate tokens.

All sampling routes through the seeded ``Rng`` so it is reproducible. Latency is
returned in milliseconds; the caller turns step latencies into nested start/end
timestamps (latency = endTime - startTime, per spec §2).
"""
from __future__ import annotations

from .pricing import ROLE_PROFILES
from .rng import Rng


def sample_tokens(rng: Rng, role: str) -> tuple[int, int]:
    p = ROLE_PROFILES[role]
    inp = max(1, int(rng.lognormal(p["in_med"], p["in_sig"])))
    out = max(1, int(rng.lognormal(p["out_med"], p["out_sig"])))
    return inp, out


def sample_latency_ms(rng: Rng, role: str, slow_factor: float = 1.0) -> int:
    """Per-step latency, log-normal with a long tail. ``slow_factor`` injects degradation."""
    p = ROLE_PROFILES[role]
    base = rng.lognormal(p["lat_med_ms"], p["lat_sig"]) * slow_factor
    # occasional heavy tail outlier
    if rng.chance(0.02):
        base *= rng.uniform(3, 8)
    return max(1, int(base))


def tool_latency_ms(rng: Rng, median: float, sigma: float = 0.4, slow_factor: float = 1.0) -> int:
    base = rng.lognormal(median, sigma) * slow_factor
    if rng.chance(0.015):
        base *= rng.uniform(3, 6)
    return max(1, int(base))
