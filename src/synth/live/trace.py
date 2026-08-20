"""The live submission's trace, emitted at *now* through the live-emission seam (#211).

A submission produces the same agent graph the seeded pool is made of — that is the whole
point of the playground, a live decision that sits at the top of the same timeline and
renders the same way:

    credit_agent.assess_application            (the trace: its root observation)
     └─ AGENT: credit_agent
         ├─ span: load_application
         │    └─ generation: extract_fields
         ├─ RETRIEVER: retrieve_policy
         ├─ TOOL: check_subsidy_eligibility
         ├─ TOOL: compute_affordability
         ├─ generation: decision            ← the one real model call
         └─ generation: explain

What it does **not** share with the seeded pool is the writer. ``seed/traces.py`` builds
backdated event envelopes for the Spool: producer-supplied timestamps, producer-minted ids,
byte-compared against a golden. A submission has none of that — it happens now, it calls a
model, and it is outside the golden gate — so it rides ``langfuse_synth_core.live.emit``,
whose whole design is that it takes no timestamp (CONTRACT.md, the determinism line).

The two writers share the *scenario* instead: every string in the graph below comes from
``synth.content``, the same module the seeder renders from. Shape and content stay in step;
only the timestamps differ, and they differ because they must.
"""
from __future__ import annotations

from typing import Any

from langfuse_synth_core.distributions import cache_split, sample_tokens, text_tokens
from langfuse_synth_core.pricing import cost_details, usage_details
from langfuse_synth_core.rng import Rng

from ..config import Config
from ..content import explain_io, extract_io, model_label, retrieve_io
from ..models import Application, Decision

TRACE_NAME = "credit_agent.assess_application"


def live_subsidy_eligibility(cfg: Config, app: Application, decision: Decision) -> tuple[dict, bool]:
    """What ``check_subsidy_eligibility`` reports for a submission, and whether the agent
    ignored it.

    A live submission runs against *today's* policy, so an eligible BEV sees the real grant
    — and a v1 decision that did not apply it is flagged ``ignored_by_agent``: the bug, made
    visible in the tool step the presenter opens. (The seeded pool's stale-window text is a
    different story with a different mechanism, and it lives in ``seed/traces.py``.)
    """
    if app.vehicle.type == "BEV" and app.vehicle.list_price_eur <= cfg.golden_path.price_cap_eur:
        grant = cfg.golden_path.grant_amount_eur
        report = {
            "applicable_subsidies": [{"name": "EV Purchase Grant", "amount_eur": grant}],
            "note": (f"BEV ≤ €{cfg.golden_path.price_cap_eur:,} qualifies for the "
                     f"€{grant:,} EV purchase grant"),
        }
        return report, decision.applied_grant_eur == 0   # offered, but not applied
    return {"applicable_subsidies": [], "note": "no subsidy applies to this vehicle"}, False


def emit_live_trace(emitter: Any, cfg: Config, *, application: Application, decision: Decision,
                    decision_input: list[dict], decision_usage: tuple[int, int],
                    prompt: Any = None, tags: list[str] | None = None,
                    user_id: str = "playground_user", environment: str = "production") -> str:
    """Emit the submission's agent graph and return its trace id (for the deep link).

    ``decision_usage`` is the model's real ``(input, output)`` token count,
    ``decision_input`` the chat turn it actually saw, and ``prompt`` the managed prompt
    object that produced it — the SDK links a generation to a prompt version by the object,
    not by name and number, which is what makes "which version decided this?" answerable in
    the UI; every other step is templated, and its
    tokens are sampled the way the seeder samples them so the cost column stays plausible.
    Latencies are not passed at all — the seam stamps wall clock, which for a live surface
    is the true number.
    """
    r = Rng(cfg.generation.seed).sub("live", str(application.application_date))
    # No planner step: the ambiguous-application plan generation belongs to the seeded
    # pool, and a submission runs the production path straight through.
    sonnet = cfg.model_by_role("work")
    haiku = cfg.model_by_role("light")

    def _sampled(role, model, inp, outp):
        it, ot, _ = sample_tokens(r, role, visible_input=text_tokens(inp),
                                  visible_output=text_tokens(outp))
        ti, cr, cc = cache_split(r, role, it)
        return usage_details(ti, ot, cr, cc), cost_details(model, ti, ot, cr, cc)

    with emitter.trace(TRACE_NAME, user_id=user_id, environment=environment,
                       tags=list(tags or []), input=application.model_dump(),
                       metadata={"kind": "live", "vehicle_type": application.vehicle.type}) as trace:
        # Everything hangs off the orchestrator, so the trace renders as an agent graph.
        elig_call_id = r.obs_id("toolcall_elig", trace.id)
        afford_call_id = r.obs_id("toolcall_afford", trace.id)
        tool_calls = [{"id": elig_call_id, "name": "check_subsidy_eligibility"},
                      {"id": afford_call_id, "name": "compute_affordability"}]

        with trace.observation("credit_agent", as_type="agent",
                               input=application.model_dump(),
                               metadata={"tool_calls": tool_calls,
                                         "stale_grant_window": False}) as agent:
            raw, extract_in, extract_out = extract_io(application)
            with agent.span("load_application", input={"raw": raw}) as load:
                usage, cost = _sampled("light", haiku, extract_in, extract_out)
                with load.generation("extract_fields", model=haiku.name, usage=usage,
                                     cost=cost, input=extract_in,
                                     metadata={"vehicle_model": model_label(
                                         r, application.vehicle.type)}) as gen:
                    gen.update(output=extract_out)
                load.update(output=extract_out)

            query, documents = retrieve_io()
            with agent.observation("retrieve_policy", as_type="retriever", input=query,
                                   metadata={"retriever": "vector_search"}) as retrieve:
                retrieve.update(output={"documents": documents})

            elig_out, ignored_by_agent = live_subsidy_eligibility(cfg, application, decision)
            with agent.observation("check_subsidy_eligibility", as_type="tool",
                                   input={"vehicle": application.vehicle.model_dump()},
                                   metadata={"tool": "subsidy_lookup",
                                             "toolCallId": elig_call_id,
                                             "ignored_by_agent": ignored_by_agent}) as elig:
                elig.update(output=elig_out)

            with agent.observation("compute_affordability", as_type="tool",
                                   input={"financed_principal_eur": decision.financed_principal_eur,
                                          "approved_line_eur": application.approved_line_eur},
                                   metadata={"tool": "affordability_engine",
                                             "toolCallId": afford_call_id}) as afford:
                afford.update(output={"within_line": decision.financed_principal_eur
                                      <= application.approved_line_eur})

            # The one real model call: real tokens, real cost, and the prompt link that
            # makes "which version decided this?" answerable in the UI.
            in_tok, out_tok = decision_usage
            with agent.generation("decision", model=sonnet.name,
                                  usage=usage_details(in_tok, out_tok, 0, 0),
                                  cost=cost_details(sonnet, in_tok, out_tok, 0, 0),
                                  input=decision_input, model_parameters={"temperature": 0},
                                  metadata={"tool_calls": tool_calls},
                                  prompt=prompt) as gen:
                gen.update(output=decision.model_dump())

            explain_in, explain_out = explain_io(r, decision)
            usage, cost = _sampled("light", haiku, explain_in, explain_out)
            with agent.generation("explain", model=haiku.name, usage=usage, cost=cost,
                                  input=explain_in) as gen:
                gen.update(output=explain_out)

            agent.update(output=decision.model_dump())
        trace.update(output=decision.model_dump())
        trace_id = trace.id
    return trace_id
