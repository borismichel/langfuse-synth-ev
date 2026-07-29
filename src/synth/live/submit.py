"""Run a live submission: pull the current ``production`` prompt, get a real decision,
and emit it as a native agent-graph trace at *now*.

Only the ``decision`` generation is a real model call (its tokens are the real usage); the
surrounding spans are templated/computed exactly like the seed, so the trace is shape-
identical to the seeded data and lands at the top of the timeline.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from ..agent import GrantRule, decide, parse_decision
from ..config import Config
from ..models import Application
from .. import clients
from langfuse_synth_core.rng import Rng
from langfuse_synth_core.seed.events import score_event
from langfuse_synth_core.seed.ingest import assert_demo_project
from ..seed.traces import TraceSpec, build_trace_events
from langfuse_synth_core.timegen import day_anchor, iso_date

if TYPE_CHECKING:
    from langfuse_synth_core.companion import CompanionAdapter

PRODUCTION_LABEL = "production"


def _clients(cfg: Config, adapter: "CompanionAdapter | None"):
    """The ``(langfuse, llm, ingestor)`` triple the live submission needs — taken from the
    Companion Adapter on the live-surface path (Spec G · G4, #142), built off the env on the
    headless ``synth submit`` path. The fork itself lives in :mod:`synth.clients`, so every
    caller in the kit resolves its clients the same way."""
    return (clients.langfuse_client(cfg, adapter), clients.llm_client(cfg, adapter),
            clients.ingestor(cfg, adapter))


def _live_decision(cfg: Config, lf, llm, app: Application) -> tuple:
    """Pull the current ``production`` prompt (cache_ttl=0 → a promotion is caught) and run it.
    Returns ``(decision, input_tokens, output_tokens, prompt_version, latency_ms, messages)``
    where ``messages`` is the compiled chat turn the model actually saw."""
    name = cfg.golden_path.prompt_name
    prompt = lf.get_prompt(name, label=PRODUCTION_LABEL, type="chat", cache_ttl_seconds=0)
    application_json = app.model_dump_json()
    messages = prompt.compile(application=application_json)
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    turns = [m for m in messages if m.get("role") != "system"] or \
        [{"role": "user", "content": application_json}]
    t0 = time.monotonic()
    result = llm.complete(system=system, messages=turns, temperature=0, max_tokens=512)
    latency_ms = int((time.monotonic() - t0) * 1000)
    chat = [{"role": m.get("role"), "content": m.get("content")} for m in messages]
    return (parse_decision(result.text, app), result.input_tokens, result.output_tokens,
            getattr(prompt, "version", None), latency_ms, chat)


def submit(cfg: Config, application: Application, *, adapter: "CompanionAdapter | None" = None,
           log: Callable[[str], None] = print) -> dict:
    """Run a live application through the production prompt and emit its trace.

    Returns the decision, the deterministic v2 ``expected`` (for contrast), the prompt
    version that ran, and a deep link to the freshly emitted trace.

    ``adapter`` is the Companion Adapter (Spec G · G4, #142): when the live surface hands one
    in, the ready Langfuse SDK, LLM, and ingestion clients come from it (the adapter owns
    secret intake + resolution). When absent — the headless ``synth submit`` path — the same
    clients are built directly off the core resolution module, so that path is unchanged."""
    base_url = cfg.target.base_url
    project_id, project_name = assert_demo_project(base_url, cfg.target.project_hint)

    now = datetime.now(timezone.utc)
    application = application.model_copy(update={"application_date": iso_date(now)})

    lf, llm, ing = _clients(cfg, adapter)
    decision, in_tok, out_tok, version, latency_ms, messages = _live_decision(cfg, lf, llm, application)
    log(f"· production prompt v{version} decided: {decision.decision} "
        f"(grant €{decision.applied_grant_eur:,}, financed €{decision.financed_principal_eur:,}; {latency_ms}ms)")

    # Emit a native-looking agent-graph trace at *now*, with the real decision + usage.
    trace_id = uuid.uuid4().hex
    spec = TraceSpec(
        trace_id=trace_id, timestamp=now, application=application, decision=decision,
        user_id="playground_user", session_id=None, environment="production",
        kind="live", stale_grant_window=False, plan_step=False,
        tags=["ev-grant", "playground"])
    events = build_trace_events(Rng(cfg.generation.seed), cfg, spec, version,
                                decision_usage=(in_tok, out_tok), decision_latency_ms=latency_ms,
                                decision_input=messages)
    ing.extend(events)
    ing.flush()

    # The deterministic "correct under v2" answer, for side-by-side contrast.
    rule = GrantRule(amount_eur=cfg.golden_path.grant_amount_eur,
                     price_cap_eur=cfg.golden_path.price_cap_eur,
                     effective_date=iso_date(day_anchor(now, cfg.golden_path.grant_effective_day_offset)))
    expected = decide(application, "v2", rule=rule)

    trace_url = f"{base_url.rstrip('/')}/project/{project_id}/traces/{trace_id}"
    return {
        "decision": decision,
        "expected": expected,
        "prompt_version": version,
        "trace_id": trace_id,
        "trace_url": trace_url,
        "project_name": project_name,
    }


def dispute(cfg: Config, trace_id: str, comment: str, *, adapter: "CompanionAdapter | None" = None,
            log: Callable[[str], None] = print) -> dict:
    """Attach a ``user_disagreement = true`` score (with the submitter's free-text comment)
    to a previously-emitted trace — the same lagging signal the dashboard's appeal rate
    tracks. Idempotent per trace (the score id is derived from the trace id), so re-disputing
    updates the comment rather than duplicating. ``adapter`` supplies the ready ingestion
    client when the live surface hands one in (Spec G · G4, #142); otherwise it is built off
    the env, unchanged."""
    base_url = cfg.target.base_url
    project_id, _ = assert_demo_project(base_url, cfg.target.project_hint)
    note = (comment or "").strip() or "customer disputed the decision"
    s = Rng(cfg.generation.seed).sub("dispute", trace_id)
    ev = score_event(score_id=s.score_id("disagree", trace_id), name="user_disagreement",
                     value=1, data_type="BOOLEAN", timestamp=datetime.now(timezone.utc),
                     trace_id=trace_id, environment="production", comment=note)
    ing = clients.ingestor(cfg, adapter)
    ing.add(ev)
    ing.flush()
    log(f"· dispute logged on {trace_id[:12]}…: {note[:60]}")
    return {"trace_id": trace_id, "comment": note,
            "trace_url": f"{base_url.rstrip('/')}/project/{project_id}/traces/{trace_id}"}
