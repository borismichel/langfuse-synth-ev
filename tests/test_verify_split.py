"""`verify` reads through the seam, and asserts the same things it always did.

Two acceptance criteria meet here (portal #211):

  * *"every assertion each verify makes today is still made after the remap"* — so the same
    canned seeded environment is served **twice**, once as a deprecated-API Langfuse and
    once as a v4 one, and the report must come out identical. That is a stronger claim than
    the pre-remap version of this file made: it used to prove the assertions survived a
    refactor, and now it proves they survive a change of API generation;
  * *"target detection recognises a v4 host"* — nothing below is configured with a
    generation. The seam probes, and the two arms are reached by what the canned server
    answers to that probe.

The read path is faked at the transport (`read.request_retry`), not at the assertions, so
normalisation — v4's raw-JSON-string `input`, its `subject` object, its cursor pagination —
runs for real. Flipping one seeded signal must flip exactly the check that owns it, on both
arms, so these are the real assertions rather than always-pass stubs.
"""

from __future__ import annotations

import pytest

from langfuse_synth_core import read

from synth import verify as V
from synth.config import load_config
from synth.state import RunState

DRIFT_START = "2026-06-02"
BEFORE_TS = "2026-05-30T12:00:00.000Z"  # < drift_start
DURING_TS = "2026-06-04T12:00:00.000Z"  # >= drift_start

SYSTEM_TURN = [{"role": "system", "content": "You are a credit-decision agent."}]


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
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def _install_seeded_env(monkeypatch, *, generation: str,
                        disagreement_during_value: float = 1.0) -> None:
    """Serve the canned seeded project as `generation` would — and only as it would.

    Every endpoint the other generation would have used answers a 404, so an assertion that
    silently kept reading a deprecated endpoint fails rather than passing on a fallback.
    """
    legacy = generation == read.LEGACY

    disagreement = [
        (BEFORE_TS, 0.0),
        (DURING_TS, disagreement_during_value),
        (DURING_TS, disagreement_during_value),
    ]

    def legacy_scores(name):
        if name == "user_disagreement":
            return [{"id": f"d{i}", "name": name, "dataType": "BOOLEAN", "timestamp": ts,
                     "value": v, "stringValue": None, "traceId": "t1"}
                    for i, (ts, v) in enumerate(disagreement)]
        return [{"id": "q1", "name": name, "dataType": "NUMERIC", "timestamp": DURING_TS,
                 "value": 0.9, "stringValue": None, "traceId": "t1"}]

    def v3_scores(name):
        if name == "user_disagreement":
            return [{"id": f"d{i}", "name": name, "dataType": "BOOLEAN", "timestamp": ts,
                     "value": v, "subject": {"kind": "trace", "id": "t1"}}
                    for i, (ts, v) in enumerate(disagreement)]
        return [{"id": "q1", "name": name, "dataType": "NUMERIC", "timestamp": DURING_TS,
                 "value": 0.9, "subject": {"kind": "trace", "id": "t1"}}]

    # The disputed trace: one prompt-linked `decision` generation carrying the chat turn.
    # v4 sends `input` as a raw JSON string; the deprecated API sent it parsed.
    import json

    def decision_row(*, raw_io: bool):
        return {"id": "o1", "traceId": "d1", "type": "GENERATION", "name": "decision",
                "startTime": DURING_TS, "promptName": "credit_decision", "promptVersion": 1,
                "input": json.dumps(SYSTEM_TURN) if raw_io else SYSTEM_TURN}

    def handler(method, url, *, params=None, auth=None, timeout=30, throttle_s=0.0,
                attempts=8):
        params = params or {}
        path = url.replace("http://localhost:3000", "")

        if path == "/api/public/dataset-items":
            return _Resp(200, {"data": [{"sourceTraceId": f"s{i}"} for i in (1, 2, 3)]})

        # -- the generation probe, and the deprecated endpoints ------------
        if path == "/api/public/traces":
            return _Resp(200, {"data": [], "meta": {"totalPages": 1}}) if legacy else _Resp(404, {})
        if path.startswith("/api/public/traces/"):
            if not legacy:
                return _Resp(404, {})
            tid = path.rsplit("/", 1)[-1]
            if tid in ("r1", "r2"):
                return _Resp(200, {"id": tid, "observations": [], "scores": []})
            if tid == "d1":
                return _Resp(200, {"id": "d1", "observations": [decision_row(raw_io=False)],
                                   "scores": []})
            return _Resp(404, {})
        if path == "/api/public/v2/scores":
            if not legacy:
                return _Resp(404, {})
            return _Resp(200, {"data": legacy_scores(params.get("name")),
                               "meta": {"totalPages": 1}})

        # -- the v4 endpoints ---------------------------------------------
        if path == "/api/public/v2/observations":
            if legacy:
                return _Resp(404, {})
            tid = params.get("traceId")
            rows = [decision_row(raw_io=True)] if tid == "d1" else (
                [{"id": f"root-{tid}", "traceId": tid, "type": "SPAN", "name": "root"}]
                if tid in ("r1", "r2") else [])
            return _Resp(200, {"data": rows, "meta": {}})
        if path == "/api/public/v3/scores":
            if legacy:
                return _Resp(404, {})
            return _Resp(200, {"data": v3_scores(params.get("name")), "meta": {}})

        raise AssertionError(f"unexpected read: {path!r} (generation={generation})")

    monkeypatch.setattr(read, "request_retry", handler)
    monkeypatch.setattr(V, "get_json",
                        lambda base, path, params=None, *, throttle=0.0:
                        handler("GET", f"{base}{path}", params=params).json())


def _run() -> dict:
    report = V.run_verify(load_config("config/demo.yaml"), _state(), log=lambda _m: None)
    return {c.name: c.ok for c in report.checks}


ALL_CHECKS = ("dataset_items", "reserved_pool", "disagreement_drift", "quality_green",
              "prompt_v1_linkage", "decision_input_chat")


@pytest.mark.parametrize("generation", [read.LEGACY, read.V4])
def test_healthy_seeded_env_passes_every_assertion(monkeypatch, generation):
    _install_seeded_env(monkeypatch, generation=generation)
    assert _run() == dict.fromkeys(ALL_CHECKS, True)


@pytest.mark.parametrize("generation", [read.LEGACY, read.V4])
def test_flipping_the_drift_signal_flips_only_that_assertion(monkeypatch, generation):
    # No elevation in the drift window → the drift assertion (and only it) must fail,
    # proving verify runs the REAL assertion, not an always-pass stub.
    _install_seeded_env(monkeypatch, generation=generation, disagreement_during_value=0.0)
    checks = _run()
    assert checks["disagreement_drift"] is False
    for name in ALL_CHECKS:
        if name != "disagreement_drift":
            assert checks[name] is True, f"{name} regressed — the remap changed an assertion"


def test_the_report_is_identical_on_both_generations(monkeypatch):
    """The point of the seam, stated as a test: the same project, read through either API,
    yields the same verdict — so a target's cutover cannot change what `verify` says."""
    _install_seeded_env(monkeypatch, generation=read.LEGACY)
    legacy = _run()
    _install_seeded_env(monkeypatch, generation=read.V4)
    assert _run() == legacy


def test_verify_recognises_a_v4_host_and_says_so(monkeypatch):
    """Nothing configures the generation — detection probes for it, and the log line names
    what answered, which is the first thing to know when a passing check starts failing."""
    _install_seeded_env(monkeypatch, generation=read.V4)
    lines: list[str] = []
    V.run_verify(load_config("config/demo.yaml"), _state(), log=lines.append)
    assert any("v4 read APIs" in line for line in lines), lines
