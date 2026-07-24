"""The verify SPLIT yields identical assertions to the pre-split verify (Ring 2, #33).

Acceptance (#33): "the split ``verify`` (lib read-client + kit assertions) yields assertions
identical to the pre-split ``verify`` against a seeded Langfuse env."

We prove that OFFLINE and deterministically. The read-client (auth + paginated GET of
scores/traces) now lives in ``langfuse_synth_core.lfread``; the ``run_verify`` assertion body
is byte-unchanged and still calls those helpers under their original local names. Here we
stand up a *canned* seeded environment — the exact JSON shapes a real seeded Langfuse would
return — feed it through the split read path, and assert:

  1. a healthy seeded env passes every check (the golden-path assertions the pre-split verify
     made), and
  2. flipping one seeded signal flips exactly the check that owns it (so the assertions are
     the real ones, not stubbed to always-pass).

By construction this equals the pre-split behaviour: only the helper *definitions* moved
across the seam (same auth, same pagination), while the assertion code that consumes them is
identical. Against a live seeded env the two therefore produce the same report.
"""

from __future__ import annotations

import pytest

from synth import verify as V
from synth.config import load_config
from synth.state import RunState

DRIFT_START = "2026-06-02"
BEFORE_TS = "2026-05-30T12:00:00.000Z"  # < drift_start
DURING_TS = "2026-06-04T12:00:00.000Z"  # >= drift_start


def _state() -> RunState:
    return RunState(
        base_url="http://localhost:3000",
        project_name="demo",
        run_date="2026-06-09T12:00:00+00:00",
        grant_effective_date="2026-06-02",
        drift_window=f"{DRIFT_START} .. 2026-06-07",
        drift_window_days=5,
        prompt_name="credit_decision",
        prompt_versions={"v1": 1, "v2": 2},
        dataset_name="ev-grant-disputed-rejections",
        dataset_items=3,
        judge_model="claude-sonnet-4-6",
        task_model="claude-sonnet-4-6",
        grant_amount_eur=6000,
        price_cap_eur=50000,
        disputed_example={"trace_id": "d1"},
        reserved_trace_ids=["r1", "r2"],
    )


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _install_seeded_env(monkeypatch, *, disagreement_during_value: float = 1.0) -> None:
    """Patch the split read path to return the JSON a healthy seeded Langfuse would."""

    def fake_get(base, path, params=None, *, throttle=0.0):
        if path == "/api/public/dataset-items":
            return {"data": [{"sourceTraceId": f"s{i}"} for i in (1, 2, 3)]}
        if path == "/api/public/traces/d1":
            return {"observations": [{
                "name": "decision",
                "promptName": "credit_decision",
                "promptVersion": 1,
                "input": [{"role": "system", "content": "You are a credit-decision agent."}],
            }]}
        raise AssertionError(f"unexpected GET path {path!r}")

    def fake_get_all_scores(base, name, limit_pages=30, *, throttle=0.0):
        if name == "user_disagreement":
            return [
                {"timestamp": BEFORE_TS, "value": 0.0},
                {"timestamp": DURING_TS, "value": disagreement_during_value},
                {"timestamp": DURING_TS, "value": disagreement_during_value},
            ]
        if name == "answer_quality":
            return [{"timestamp": DURING_TS, "value": 0.9}]
        raise AssertionError(f"unexpected score name {name!r}")

    def fake_request_retry(method, url, **kwargs):
        return _Resp(200)  # every reserved trace exists

    monkeypatch.setattr(V, "_get", fake_get)
    monkeypatch.setattr(V, "_get_all_scores", fake_get_all_scores)
    monkeypatch.setattr(V, "request_retry", fake_request_retry)


def _run() -> dict:
    report = V.run_verify(load_config("config/demo.yaml"), _state(), log=lambda _m: None)
    return {c.name: c.ok for c in report.checks}


def test_healthy_seeded_env_passes_every_assertion(monkeypatch):
    _install_seeded_env(monkeypatch)
    checks = _run()
    assert checks == {
        "dataset_items": True,
        "reserved_pool": True,
        "disagreement_drift": True,
        "quality_green": True,
        "prompt_v1_linkage": True,
        "decision_input_chat": True,
    }


def test_flipping_the_drift_signal_flips_only_that_assertion(monkeypatch):
    # No elevation in the drift window → the drift assertion (and only it) must fail,
    # proving the split verify runs the REAL pre-split assertion, not an always-pass stub.
    _install_seeded_env(monkeypatch, disagreement_during_value=0.0)
    checks = _run()
    assert checks["disagreement_drift"] is False
    for name in ("dataset_items", "reserved_pool", "quality_green",
                 "prompt_v1_linkage", "decision_input_chat"):
        assert checks[name] is True, f"{name} regressed — the split changed an assertion"
