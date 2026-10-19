"""Run a live policy lookup and decision using the current production prompt."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from langfuse_synth_core.rng import Rng
from langfuse_synth_core.seed.ingest import assert_demo_project
from langfuse_synth_core.timegen import iso_date

from .. import clients
from ..agent import decide
from ..config import Config
from ..models import Application
from ..state import deployment_rule
from .trace import emit_live_trace

if TYPE_CHECKING:
    from langfuse_synth_core.companion import CompanionAdapter

PRODUCTION_LABEL = "production"


def _clients(cfg: Config, adapter: "CompanionAdapter | None"):
    """The ``(langfuse, llm, emitter)`` triple the live submission needs — taken from the
    Companion Adapter on the live-surface path (Spec G · G4, #142), built off the env on the
    headless ``synth submit`` path. The fork itself lives in :mod:`synth.clients`, so every
    caller in the kit resolves its clients the same way."""
    return (clients.langfuse_client(cfg, adapter), clients.llm_client(cfg, adapter),
            clients.emitter(cfg, adapter, environment="production"))




def submit(cfg: Config, application: Application, *, adapter: "CompanionAdapter | None" = None,
           log: Callable[[str], None] = print) -> dict:
    """Run a live application through the production prompt and emit its trace.

    Returns the decision, the deterministic v2 ``expected`` (for contrast), the prompt
    version that ran, and a deep link to the freshly emitted trace.

    ``adapter`` is the Companion Adapter (Spec G · G4, #142): when the live surface hands one
    in, the ready Langfuse SDK, LLM, and emission clients come from it (the adapter owns
    secret intake + resolution). When absent — the headless ``synth submit`` path — the same
    clients are built directly off the core resolution module, so that path is unchanged."""
    base_url = cfg.target.base_url
    project_id, project_name = assert_demo_project(base_url, cfg.target.project_hint)

    now = datetime.now(timezone.utc)
    application = application.model_copy(update={"application_date": iso_date(now)})

    rule = deployment_rule(cfg)
    lf, llm, emitter = _clients(cfg, adapter)
    prompt = lf.get_prompt(cfg.golden_path.prompt_name, label=PRODUCTION_LABEL,
                           type="chat", cache_ttl_seconds=0)
    version = getattr(prompt, "version", None)
    decision, trace_id = emit_live_trace(
        emitter, cfg, application=application, rule=rule, llm=llm, prompt=prompt,
        tags=["ev-grant", "playground"])
    log(f"· production prompt v{version} decided: {decision.decision} "
        f"(grant €{decision.applied_grant_eur:,}, financed €{decision.financed_principal_eur:,})")

    # The deterministic "correct under v2" answer, for side-by-side contrast.
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
    to a previously-emitted trace. The cached historical dashboard does not refresh
    from these live scores. Idempotent per trace (the score id is derived from the trace id), so re-disputing
    updates the comment rather than duplicating. ``adapter`` supplies the ready emission
    client when the live surface hands one in (Spec G · G4, #142); otherwise it is built off
    the env, unchanged."""
    base_url = cfg.target.base_url
    project_id, _ = assert_demo_project(base_url, cfg.target.project_hint)
    note = (comment or "").strip() or "customer disputed the decision"
    s = Rng(cfg.generation.seed).sub("dispute", trace_id)
    emitter = clients.emitter(cfg, adapter, environment="production")
    emitter.score("user_disagreement", 1, trace_id=trace_id, data_type="BOOLEAN",
                  comment=note, score_id=s.score_id("disagree", trace_id))
    emitter.flush()
    log(f"· dispute logged on {trace_id[:12]}…: {note[:60]}")
    return {"trace_id": trace_id, "comment": note,
            "trace_url": f"{base_url.rstrip('/')}/project/{project_id}/traces/{trace_id}"}
