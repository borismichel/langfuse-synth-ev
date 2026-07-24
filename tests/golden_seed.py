"""Golden-gate seed adapter (Spec A · Step 0 · #30) — dev-only, never shipped.

The determinism golden gate in ``langfuse-synth-core[authoring]`` drives a kit through
one uniform contract::

    seed(target_traces: int, params: Mapping) -> bytes   # the full materialized Spool

This module is that adapter for the EV kit. It materializes the kit **exactly as it is
on today's ``main``** — no plumbing extracted — and returns the byte-for-byte
pre-ingestion Spool (the NDJSON event stream the real ``synth seed`` writes to
``.synth_spool/events.ndjson``). That byte stream is the migration oracle every later
ring (and the lib-side ``count_spool``) must reproduce.

Why it lives in ``tests/`` and not ``src/synth/``: the golden gate is *authoring-time*
tooling behind the ``[authoring]`` extra. The deployed runtime image must never carry it
(Spec A §3), so the adapter is a dev-only test asset the gate imports via ``search_paths``,
not part of the shipped ``synth`` package.

Determinism note: the gate runs this in a subprocess under ``PYTHONHASHSEED=0`` and the
deny-LLM egress block. The EV seed path is model-free (every Decision is templated), so it
passes the block; the hash-seed pin makes any incidental set/dict ordering reproducible.
"""
from __future__ import annotations

import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from synth.config import load_config
from synth.seed.run import run_seed
from synth.state import REPO_ROOT

# Fixed oracle inputs. The run date is pinned (identical to the determinism test's anchor)
# so the backdated timestamps are reproducible; the config seed (42) is the declared seed.
CONFIG = REPO_ROOT / "config" / "demo.yaml"
RUN_DATE = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


def seed(target_traces: int, params: Mapping[str, Any]) -> bytes:
    """Materialize the full pre-ingestion Spool for a fixed ``target_traces``; return bytes.

    EV derivation hook (Spec A §4 — "EV: direct count"): ``target_traces`` maps **identity**
    to the kit's internal absolute-count knob ``generation.total_traces``. This is the real,
    vendor-approved EV mapping, exact and stable through the Ring 1/2 migration.

    ``params`` completes the ``seed(target_traces, params)`` gate contract; the Step-0 oracle
    pins the config defaults (seed 42), so nothing is read from it here — declared-param
    knobs land when Ring 1/2 wires the real derivation.
    """
    cfg = load_config(str(CONFIG))
    cfg.generation.total_traces = int(target_traces)

    with tempfile.TemporaryDirectory(prefix="ev-golden-") as tmp:
        spool_path = Path(tmp) / "events.ndjson"
        # dry_run: no network (model-free, no ingestion); persist=False: no fixtures/state
        # written to the repo; do_import=False: never touch Langfuse. Pure CPU generation.
        run_seed(
            cfg,
            dry_run=True,
            persist=False,
            run_date=RUN_DATE,
            spool_path=spool_path,
            do_import=False,
            log=lambda _m: None,
        )
        return spool_path.read_bytes()
