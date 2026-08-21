"""`verify` reads through the seam, and asserts the same things it always did.

This served one canned seeded project **twice** while the seam had two arms — once as a
deprecated-API Langfuse and once as a v4 one — because #211's acceptance criterion was that
every assertion survives the remap, and identical reports on both arms was the proof. It
did, and that equivalence is what let #213 delete the deprecated arm. The canned server
answers the v4 endpoints only now, and **404s every deprecated one**, so a `verify` that
quietly reached for one would fail here rather than pass on a fallback.

The read path is faked at the transport (`read.request_retry`), not at the assertions, so
normalisation — v4's raw-JSON-string `input`, its `subject` object, its cursor pagination —
runs for real. Flipping one seeded signal must flip exactly the check that owns it, so these
are the real assertions rather than always-pass stubs.
"""

from __future__ import annotations

import pathlib
import re

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


def _install_seeded_env(monkeypatch, *, disagreement_during_value: float = 1.0) -> None:
    """Serve the canned seeded project as a v4 Langfuse — and only as one.

    Every deprecated endpoint answers a 404, so an assertion that silently kept reading one
    fails rather than passing on a fallback.
    """
    disagreement = [
        (BEFORE_TS, 0.0),
        (DURING_TS, disagreement_during_value),
        (DURING_TS, disagreement_during_value),
    ]

    def v3_scores(name):
        if name == "user_disagreement":
            return [{"id": f"d{i}", "name": name, "dataType": "BOOLEAN", "timestamp": ts,
                     "value": v, "subject": {"kind": "trace", "id": "t1"}}
                    for i, (ts, v) in enumerate(disagreement)]
        return [{"id": "q1", "name": name, "dataType": "NUMERIC", "timestamp": DURING_TS,
                 "value": 0.9, "subject": {"kind": "trace", "id": "t1"}}]

    # The disputed trace: one prompt-linked `decision` generation carrying the chat turn.
    # v4 sends `input` as a raw JSON string, which the seam decodes.
    import json

    def decision_row():
        return {"id": "o1", "traceId": "d1", "type": "GENERATION", "name": "decision",
                "startTime": DURING_TS, "promptName": "credit_decision", "promptVersion": 1,
                "input": json.dumps(SYSTEM_TURN)}

    def handler(method, url, *, params=None, auth=None, timeout=30, throttle_s=0.0,
                attempts=8):
        params = params or {}
        path = url.replace("http://localhost:3000", "")

        if path == "/api/public/dataset-items":
            return _Resp(200, {"data": [{"sourceTraceId": f"s{i}"} for i in (1, 2, 3)]})

        # -- every deprecated endpoint is gone from this server ------------
        if re.match(r"/api/public/(traces|observations|sessions|v2/scores|metrics)\b", path):
            return _Resp(404, {})

        # -- the v4 endpoints ---------------------------------------------
        if path == "/api/public/v2/observations":
            tid = params.get("traceId")
            rows = [decision_row()] if tid == "d1" else (
                [{"id": f"root-{tid}", "traceId": tid, "type": "SPAN", "name": "root"}]
                if tid in ("r1", "r2") else [])
            return _Resp(200, {"data": rows, "meta": {}})
        if path == "/api/public/v3/scores":
            return _Resp(200, {"data": v3_scores(params.get("name")), "meta": {}})

        raise AssertionError(f"unexpected read: {path!r}")

    monkeypatch.setattr(read, "request_retry", handler)
    monkeypatch.setattr(V, "get_json",
                        lambda base, path, params=None, *, throttle=0.0:
                        handler("GET", f"{base}{path}", params=params).json())


def _run() -> dict:
    report = V.run_verify(load_config("config/demo.yaml"), _state(), log=lambda _m: None)
    return {c.name: c.ok for c in report.checks}


ALL_CHECKS = ("dataset_items", "reserved_pool", "disagreement_drift", "quality_green",
              "prompt_v1_linkage", "decision_input_chat")


def test_healthy_seeded_env_passes_every_assertion(monkeypatch):
    _install_seeded_env(monkeypatch)
    assert _run() == dict.fromkeys(ALL_CHECKS, True)


def test_flipping_the_drift_signal_flips_only_that_assertion(monkeypatch):
    # No elevation in the drift window → the drift assertion (and only it) must fail,
    # proving verify runs the REAL assertion, not an always-pass stub.
    _install_seeded_env(monkeypatch, disagreement_during_value=0.0)
    checks = _run()
    assert checks["disagreement_drift"] is False
    for name in ALL_CHECKS:
        if name != "disagreement_drift":
            assert checks[name] is True, f"{name} regressed — the remap changed an assertion"


def test_verify_names_no_deprecated_endpoint_itself(monkeypatch):
    """The seam is the only place this kit reaches Langfuse, so `verify` naming an endpoint
    at all would be the thing #211 exists to prevent — and #213 makes it a live failure
    rather than future debt, since the endpoints it would name have no successor here."""
    body = "\n".join(line for line in pathlib.Path("src/synth/verify.py")
                      .read_text(encoding="utf-8").splitlines()
                      if not line.lstrip().startswith("#"))
    body = body.split('"""', 2)[-1]           # the docstring discusses the migration
    for retired in ("/api/public/traces", "/api/public/observations",
                    "/api/public/v2/scores", "/api/public/sessions"):
        assert retired not in body, retired


def test_verify_names_the_v4_read_apis_in_its_log(monkeypatch):
    """The log line names what answered, which is the first thing to know when a passing
    check starts failing."""
    _install_seeded_env(monkeypatch)
    lines: list[str] = []
    V.run_verify(load_config("config/demo.yaml"), _state(), log=lines.append)
    assert any("v4 read APIs" in line for line in lines), lines


def test_an_unreadable_target_is_reported_rather_than_raised(monkeypatch):
    """Bad keys, a wrong host, a server error: the seam's probe cannot tell those apart and
    refuses to guess. `verify` is a report, though, so it must come back with every check
    failed and the reason on each line — never a traceback in place of the report
    (portal #211)."""
    class _Resp:
        status_code = 403

        def json(self):
            return {}

        def raise_for_status(self):
            import requests
            raise requests.HTTPError("403")

    monkeypatch.setattr(read, "request_retry", lambda *a, **k: _Resp())
    monkeypatch.setattr(V, "get_json",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("403")))

    checks = _run()

    assert set(checks) == set(ALL_CHECKS)
    assert not any(checks.values()), checks
