"""Realistic distributions (spec §5): log-normal latency, model-appropriate tokens.

All sampling routes through the seeded ``Rng`` so it is reproducible. Latency is
returned in milliseconds; the caller turns step latencies into nested start/end
timestamps (latency = endTime - startTime, per spec §2).
"""
from __future__ import annotations

from .pricing import ROLE_PROFILES
from .rng import Rng

CACHE_HIT_RATE = 0.82  # warm prompt-cache hit rate on the stable prefix (after warmup)


def cache_split(rng: Rng, role: str, input_tokens: int) -> tuple[int, int, int]:
    """Split total input into ``(regular_input, cache_read, cache_creation)``.

    The stable system/policy/tools prefix is read from cache on a warm hit (~82%) and
    written on a miss; the variable remainder (application + history) is always fresh."""
    prefix_med = ROLE_PROFILES[role].get("cache_prefix", 0)
    if prefix_med <= 0 or input_tokens <= 1:
        return input_tokens, 0, 0
    prefix = min(max(1, int(rng.lognormal(prefix_med, 0.15))), input_tokens - 1)
    variable = input_tokens - prefix
    if rng.chance(CACHE_HIT_RATE):
        return variable, prefix, 0   # warm hit: prefix served from cache (~0.1x)
    return variable, 0, prefix       # miss: prefix written to cache (~1.25x)


def sample_tokens(rng: Rng, role: str, context_tokens: int = 0) -> tuple[int, int]:
    """Base input/output for ``role``; ``context_tokens`` (multi-turn history + any
    upstream reasoning fed into this call) is added on top of the sampled base input."""
    p = ROLE_PROFILES[role]
    inp = max(1, int(rng.lognormal(p["in_med"], p["in_sig"]))) + max(0, int(context_tokens))
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
