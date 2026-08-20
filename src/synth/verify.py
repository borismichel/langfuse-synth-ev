"""`synth verify` — query the data back through the read seam and assert the golden path (spec §11).

Asserts specifically:
- the ``user_disagreement`` drift (elevated in the drift window vs the baseline before it),
- green ``answer_quality`` in that same window (the failure is silent),
- prompt-v1 linkage on ``decision`` generations,
- the ``decision`` input is the actual LLM turn (system prompt + application messages) —
  also catches the ingestion-merge staleness trap: a re-seed after a content change keeps
  first-seen values, so old-shape inputs survive in the same project and fail here,
- dataset item count + ``sourceTraceId`` links,
- the reserved false-negatives exist as traces but are NOT in the dataset.

Reads go through the **read seam** (``langfuse_synth_core.read``), which owns the endpoints
and answers the same normalised rows on either API generation — so nothing below knows
whether a v4 or a deprecated Langfuse answered, and this file needs no edit when the target
cuts over (portal #211). ``TargetProfile.resolved()`` is what asks; its label says which
generation answered, because that is the first thing to know when a check that passed
yesterday fails today.

``/api/public/dataset-items`` is read with ``lfread.get_json``: datasets were never
deprecated, so the seam does not model them — but the auth and the Retry-After-aware backoff
are still the library's, not this kit's. Each check is independent and reported pass/fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from langfuse_synth_core.lfread import get_json

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


def _system_prompt_of(observation) -> str:
    """The system turn of a chat-shaped generation input, or ``""`` when it is not one.

    The seam decodes v4's raw-JSON-string `input` back into the list of messages the
    deprecated API returned parsed, so this reads the same either way.
    """
    inp = observation.input
    if isinstance(inp, list) and inp and isinstance(inp[0], dict) and inp[0].get("role") == "system":
        return str(inp[0].get("content", ""))
    return ""


def run_verify(cfg: Config, state: RunState, *, log=print) -> VerifyReport:
    profile = TargetProfile.detect(cfg.target.base_url).resolved()
    base = profile.base_url
    reader = profile.reader()
    throttle = profile.post_throttle_s  # space out the reads on Cloud (0 self-hosted)
    log(f"· verifying against {profile.label} ({base})")
    report = VerifyReport()
    drift_start_s, drift_end_s = [p.strip() for p in state.drift_window.split("..")]
    drift_start = datetime.fromisoformat(drift_start_s + "T00:00:00+00:00")

    # -- dataset items + sourceTraceId links ------------------------------
    try:
        items = get_json(base, "/api/public/dataset-items",
                         {"datasetName": state.dataset_name, "limit": 100},
                         throttle=throttle).get("data", [])
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
        # "Does this trace exist?" is the assertion, and the seam answers None for one that
        # does not — under v4 that means no observation carries the id, since there is no
        # trace row to 404.
        exists = sum(1 for tid in reserved
                     if reader.trace(tid, with_scores=False) is not None)
        ok = (not leaked) and exists == len(reserved) and len(reserved) > 0
        report.add("reserved_pool", ok,
                   f"{exists}/{len(reserved)} reserved traces exist; {len(leaked)} leaked into dataset")
    except Exception as exc:  # noqa: BLE001
        report.add("reserved_pool", False, f"error: {exc}")

    # -- user_disagreement drift vs baseline ------------------------------
    try:
        scores = reader.scores(name="user_disagreement")
        before = [s for s in scores if s.timestamp and s.timestamp < drift_start]
        during = [s for s in scores if s.timestamp and s.timestamp >= drift_start]

        def rate(rows):
            # BOOLEAN scores, so the appeal rate is the mean of their numeric values.
            vals = [s.numeric_value or 0.0 for s in rows]
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
        aq = reader.scores(name="answer_quality")
        during = [s.numeric_value for s in aq
                  if s.timestamp and s.timestamp >= drift_start and s.numeric_value is not None]
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
            trace = reader.trace(tid, with_scores=False)
            decisions = [o for o in (trace.observations if trace else []) if o.name == "decision"]
            for o in decisions:
                if o.prompt_name == state.prompt_name and o.prompt_version == state.prompt_versions.get("v1"):
                    linked = True
                if "credit-decision agent" in _system_prompt_of(o):
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
