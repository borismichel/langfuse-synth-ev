"""Target-specific behaviour — the shared core's, re-exported under the kit's own name.

Two facts about the Langfuse this clone is pointed at change what the kit does: **is it
Cloud?** (URL-derived — Cloud rate-limits the one-at-a-time REST reads a `verify` sweep
fires, so they are spaced out and lean on the Retry-After-aware backoff in
``langfuse_synth_core.http``) and **which read API generation does it serve?** (probed —
Cloud goes v4-only on 2026-11-16 and a self-hosted host cuts over whenever its operator
upgrades it, so a host name answers nothing).

Both used to live here, and a byte-identical copy lived in the Lender kit. The verify
read-seam cutover (portal #211) moved them into :mod:`langfuse_synth_core.target` beside
the read seam that does the probing — one implementation, so the two kits cannot drift and
a third inherits it. This module is the kit's name for it; every call site is unchanged.
"""
from __future__ import annotations

from langfuse_synth_core.target import (
    CLOUD_HOST_MARKER,
    CLOUD_POST_THROTTLE_S,
    TargetProfile,
    post_throttle_seconds,
)

__all__ = ["CLOUD_HOST_MARKER", "CLOUD_POST_THROTTLE_S", "TargetProfile",
           "post_throttle_seconds"]
