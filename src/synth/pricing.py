"""Cost = token counts x per-model pricing (spec §5). Pricing lives in config (auditable).

We emit ``usageDetails`` (map str->int tokens) and ``costDetails`` (map str->float EUR)
on each generation, so Langfuse's cost view is driven by the same numbers a reviewer
can read in ``config/demo.yaml``.
"""
from __future__ import annotations

from .config import Config, Model


def cost_details(model: Model, input_tokens: int, output_tokens: int) -> dict[str, float]:
    inp = input_tokens / 1000.0 * model.input_per_1k
    out = output_tokens / 1000.0 * model.output_per_1k
    return {
        "input": round(inp, 6),
        "output": round(out, 6),
        "total": round(inp + out, 6),
    }


def usage_details(input_tokens: int, output_tokens: int) -> dict[str, int]:
    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": input_tokens + output_tokens,
    }


# Per-model token profiles (median input/output) and latency medians, by role.
# Opus reasons (larger, slower); Haiku is small and fast — so call-count and spend
# views disagree, which is the point worth showing (spec §5).
ROLE_PROFILES = {
    "plan":  {"in_med": 1400, "in_sig": 0.35, "out_med": 700, "out_sig": 0.45, "lat_med_ms": 4200, "lat_sig": 0.5},
    "work":  {"in_med": 650,  "in_sig": 0.3,  "out_med": 180, "out_sig": 0.35, "lat_med_ms": 1500, "lat_sig": 0.45},
    "light": {"in_med": 300,  "in_sig": 0.3,  "out_med": 120, "out_sig": 0.4,  "lat_med_ms": 600,  "lat_sig": 0.4},
}


def model_for_role(cfg: Config, role: str) -> Model:
    return cfg.model_by_role(role)
