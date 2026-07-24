"""`synth verify` — query the data back via the v2 API and assert the golden path (spec §11).

Asserts specifically:
- the ``user_disagreement`` drift (elevated in the drift window vs the baseline before it),
- green ``answer_quality`` in that same window (the failure is silent),
- prompt-v1 linkage on ``decision`` generations,
- the ``decision`` input is the actual LLM turn (system prompt + application messages) —
  also catches the ingestion-merge staleness trap: a re-seed after a content change keeps
  first-seen values, so old-shape inputs survive in the same project and fail here,
- dataset item count + ``sourceTraceId`` links,
- the reserved false-negatives exist as traces but are NOT in the dataset.

Uses raw REST (HTTP Basic) against known public endpoints, so it is robust to SDK
method-name churn. Each check is independent and reported pass/fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from langfuse_synth_core.http import request_retry
from langfuse_synth_core.lfread import auth_from_env, get_all_scores, get_json, parse_ts

from .config import Config
from .state import RunState
from .target import TargetProfile


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class VerifyReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(Check(name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


# The read-client (auth + paginated GET of scores/traces) moved to the shared core
# (langfuse_synth_core.lfread) in the Ring 2 verify split (#33). What stays HERE is the
# scenario talking: which assertions to make about what landed. The read helpers are
# imported under their original local names so the assertion body below is unchanged.
_auth = auth_from_env
_get = get_json
_get_all_scores = get_all_scores
_parse_ts = parse_ts


def run_verify(cfg: Config, state: RunState, *, log=print) -> VerifyReport:
    base = cfg.target.base_url
    profile = TargetProfile.detect(base)
    throttle = profile.post_throttle_s  # space out the reads on Cloud (0 self-hosted)
    log(f"· verifying against {profile.label} ({base})")
    report = VerifyReport()
    drift_start_s, drift_end_s = [p.strip() for p in state.drift_window.split("..")]
    drift_start = datetime.fromisoformat(drift_start_s + "T00:00:00+00:00")

    # -- dataset items + sourceTraceId links ------------------------------
    try:
        items = _get(base, "/api/public/dataset-items",
                     {"datasetName": state.dataset_name, "limit": 100}, throttle=throttle).get("data", [])
        n = len(items)
        with_src = sum(1 for it in items if it.get("sourceTraceId"))
        ok = n == state.dataset_items and with_src == n
        report.add("dataset_items", ok,
                   f"{n} items (expected {state.dataset_items}); {with_src} carry sourceTraceId")
        item_src_ids = {it.get("sourceTraceId") for it in items}
    except Exception as exc:  # noqa: BLE001
        report.add("dataset_items", False, f"error: {exc}")
        item_src_ids = set()

    # -- reserved false-negatives: in traces, NOT in dataset --------------
    try:
        reserved = state.reserved_trace_ids
        leaked = [t for t in reserved if t in item_src_ids]
        exists = 0
        for tid in reserved:
            r = request_retry("GET", f"{base.rstrip('/')}/api/public/traces/{tid}",
                              auth=_auth(), timeout=20, throttle_s=throttle)
            exists += 1 if r.status_code == 200 else 0
        ok = (not leaked) and exists == len(reserved) and len(reserved) > 0
        report.add("reserved_pool", ok,
                   f"{exists}/{len(reserved)} reserved traces exist; {len(leaked)} leaked into dataset")
    except Exception as exc:  # noqa: BLE001
        report.add("reserved_pool", False, f"error: {exc}")

    # -- user_disagreement drift vs baseline ------------------------------
    try:
        scores = _get_all_scores(base, "user_disagreement", throttle=throttle)
        before = [s for s in scores if _parse_ts(s["timestamp"]) < drift_start]
        during = [s for s in scores if _parse_ts(s["timestamp"]) >= drift_start]

        def rate(rows):
            vals = [float(s.get("value", 0)) for s in rows]
            return (sum(vals) / len(vals)) if vals else 0.0

        rb, rd = rate(before), rate(during)
        ok = rd > rb and rd > 0.2
        report.add("disagreement_drift", ok,
                   f"appeal rate baseline={rb:.2f} -> drift={rd:.2f} "
                   f"({len(before)} before / {len(during)} during)")
    except Exception as exc:  # noqa: BLE001
        report.add("disagreement_drift", False, f"error: {exc}")

    # -- answer_quality stays green in the drift window -------------------
    try:
        aq = _get_all_scores(base, "answer_quality", throttle=throttle)
        during = [float(s["value"]) for s in aq if _parse_ts(s["timestamp"]) >= drift_start
                  and s.get("value") is not None]
        mean = (sum(during) / len(during)) if during else 0.0
        ok = mean >= 0.7 and len(during) > 0
        report.add("quality_green", ok,
                   f"answer_quality mean in drift window = {mean:.2f} over {len(during)} scores")
    except Exception as exc:  # noqa: BLE001
        report.add("quality_green", False, f"error: {exc}")

    # -- prompt v1 linkage + chat-shaped input on a disputed decision -----
    try:
        tid = state.disputed_example.get("trace_id")
        linked = False
        chat_ok = False
        detail = chat_detail = "no disputed example in state"
        if tid:
            trace = _get(base, f"/api/public/traces/{tid}", throttle=throttle)
            obs = trace.get("observations", [])
            decisions = [o for o in obs if o.get("name") == "decision"]
            for o in decisions:
                if o.get("promptName") == state.prompt_name and o.get("promptVersion") == state.prompt_versions.get("v1"):
                    linked = True
                inp = o.get("input")
                if (isinstance(inp, list) and inp and isinstance(inp[0], dict)
                        and inp[0].get("role") == "system"
                        and "credit-decision agent" in str(inp[0].get("content", ""))):
                    chat_ok = True
            detail = (f"trace {tid[:12]}… decision generations linked to "
                      f"{state.prompt_name} v{state.prompt_versions.get('v1')}: {linked}")
            chat_detail = (f"trace {tid[:12]}… decision input is chat messages with the system "
                           f"prompt: {chat_ok}" + ("" if chat_ok else
                           " (stale-merge? re-seeds keep first-seen values — use a fresh project)"))
        report.add("prompt_v1_linkage", linked, detail)
        report.add("decision_input_chat", chat_ok, chat_detail)
    except Exception as exc:  # noqa: BLE001
        report.add("prompt_v1_linkage", False, f"error: {exc}")
        report.add("decision_input_chat", False, f"error: {exc}")

    for c in report.checks:
        log(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
    return report
