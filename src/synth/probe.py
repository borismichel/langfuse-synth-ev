"""`synth probe` — kit adapter over the shared backdate-ingestion probe (Ring 2, #33).

The probe FLOW (ingest one backdated trace, poll it back, assert the timestamp survived)
moved into the shared core: :func:`langfuse_synth_core.probe.run_backdate_probe`. It is
scenario-agnostic — the per-kit deltas are just *values*. EV keeps this thin adapter, which
maps its own :class:`~synth.config.Config` onto the lib's explicit params.

``_probe_ids`` is re-exported under its original name so the LAN-324 uniqueness guard
(``tests/test_probe_id.py``) keeps its import surface — the throwaway probe trace's id is
nonce-salted so it is UNIQUE per run and never lands on a tombstoned id on a re-used project.
"""
from __future__ import annotations

from typing import Callable

from langfuse_synth_core.probe import probe_ids as _probe_ids
from langfuse_synth_core.probe import run_backdate_probe

from .config import Config

__all__ = ["run_probe", "_probe_ids"]


def run_probe(cfg: Config, log: Callable[[str], None] = print) -> bool:
    """Verify EARLY that backdated ingestion behaves on this host (Cloud pre-check)."""
    return run_backdate_probe(
        cfg.target.base_url,
        cfg.target.project_hint,
        cfg.generation.seed,
        window_days=cfg.generation.window_days,
        log=log,
    )
