"""`synth probe` — verify backdated ingestion EARLY (contract parity; PLAN.md §1).

The manifest's Cloud pipeline (`when: host_kind != self_hosted`) runs `probe` before any
bulk seed: ingest ONE trace with an explicit historical timestamp, poll it back via the
public API, and FAIL LOUDLY (non-zero exit) if the host dropped or normalised the backdate
(e.g. a Cloud tier behaving differently from self-hosted). Catching that here saves a full
4,000-trace seed collapsing onto today.

Modelled on ``langfuse-synth-lender``'s probe, adapted to EV's own ingest primitives
(``seed.events`` + ``seed.ingest``). The probe trace's id is salted with a per-run
nonce (see ``_probe_ids``) so it is UNIQUE per run, and tagged ``synth-probe`` so it is
trivial to spot and ignore in the project.
"""
from __future__ import annotations

import secrets
import time
from datetime import timedelta
from typing import Callable

import requests

from .config import Config
from .rng import Rng
from .seed.events import span_event, trace_event
from .seed.ingest import Ingestor, assert_demo_project
from .timegen import now_utc


def _probe_ids(rng: Rng) -> tuple[str, str]:
    """Return ``(trace_id, marker_obs_id)`` for ONE probe run.

    The probe trace is throwaway by design (tagged ``synth-probe``), so its id must be
    UNIQUE per run — determinism buys nothing here and actively harms us. A id keyed only
    off ``generation.seed`` (default 42) is identical across every deployment to the same
    project, which produces two failure modes on re-used Cloud projects (LAN-324):

      1. First-write-wins: a stale probe trace makes the readback return the OLD
         timestamp → false-negative "backdating is dropped or normalised" failure.
      2. Tombstone poisoning: after the stale trace is DELETED, re-ingesting the same id
         is unreadable for the async-delete window → "trace not retrievable after ~65s".

    Salting the ids with a fresh per-run nonce writes a distinct throwaway trace every
    run, so the readback always reflects THIS run and never lands on a tombstoned id. The
    bulk ``seed`` ids stay deterministic (idempotent upsert) — only the probe is salted.
    """
    nonce = secrets.token_hex(8)
    return rng.trace_id("probe", "backdate-check", nonce), rng.obs_id("probe", "marker", nonce)


def run_probe(cfg: Config, log: Callable[[str], None] = print) -> bool:
    base = cfg.target.base_url
    _pid, project_name = assert_demo_project(base, cfg.target.project_hint)
    log(f"✓ guardrail passed: project {project_name!r}")

    rng = Rng(cfg.generation.seed)
    backdate = now_utc() - timedelta(days=3, hours=2)
    tid, marker_obs_id = _probe_ids(rng)

    # A minimal but fully-formed backdated trace: one trace + one child span, all with
    # explicit historical timestamps so we can assert the host preserved them.
    span_start = backdate + timedelta(milliseconds=120)
    span_end = span_start + timedelta(milliseconds=180)
    events = [
        trace_event(
            trace_id=tid, timestamp=backdate, name="synth.probe.backdate_check",
            user_id="synth_probe", environment="staging", tags=["synth-probe"],
            input={"probe": "backdated ingestion timestamp check"},
            output={"ok": True},
        ),
        span_event(
            obs_id=marker_obs_id, trace_id=tid, name="probe.marker",
            start=span_start, end=span_end, environment="staging",
            metadata={"purpose": "assert the historical timestamp survives ingestion"},
        ),
    ]
    ing = Ingestor.from_env(base)
    ing.extend(events)
    ing.flush()
    log(f"· probe trace {tid[:16]}… ingested with timestamp {backdate.isoformat()}")

    # Ingestion is async; poll the read API with a growing backoff (~65s worst case).
    pub_auth = ing.public_key, ing.secret_key
    got = None
    for attempt in range(10):
        time.sleep(2 + attempt)
        resp = requests.get(f"{base}/api/public/traces/{tid}", auth=pub_auth, timeout=20)
        if resp.status_code == 200:
            got = resp.json()
            break
    if got is None:
        log("✗ PROBE FAILED: trace not retrievable after ~65s — check keys/host/ingestion.")
        return False

    stored = (got.get("timestamp") or "").replace("Z", "+00:00")
    want = backdate.strftime("%Y-%m-%dT%H:%M")
    ok = stored.startswith(want)
    if ok:
        n_obs = len(got.get("observations") or [])
        log(f"✓ PROBE PASSED: stored timestamp {stored} matches the backdate; "
            f"{n_obs} observation(s) attached. Backdated bulk seeding is safe on this host.")
    else:
        log(f"✗ PROBE FAILED: sent {backdate.isoformat()} but the host stored {stored!r} — "
            "backdating is dropped or normalised here. DO NOT bulk-seed; the "
            f"{cfg.generation.window_days}-day window would collapse onto today.")
    return ok
