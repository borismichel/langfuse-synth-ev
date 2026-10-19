"""The single agent function — the only lever is the prompt label (spec §7, §17).

``decide(application, prompt_label) -> Decision`` is the shared spine: seeding and
the live experiment both route through it. History is deterministic; live execution
calls a model.

Two execution paths, identical contract:

- **Deterministic (seed path, default).** Pure arithmetic that mirrors the evidence
  supplied by each template: v1 finances the gross list price; v2 subtracts a qualifying
  EV grant first. No model call — a few-thousand-trace seed is free and reproducible
  (spec §2, §9). The seeded v1 rejections are exactly what ``decide(app, "v1")``
  produces, so they are reproducible policy failures a judge can detect.

- **Live (demo path).** ``decide(app, label, live=True, lf=..., llm=...)`` fetches the
  system prompt from Langfuse prompt management by label, calls the configured model,
  and parses the structured Decision. Experiments exercise this decision prompt.

The grant rule is fixture data in retrieved policy updates, sourced from configuration.
The baseline template omits that field; the candidate binds it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

from .models import Application, Decision


@dataclass(frozen=True)
class GrantRule:
    """The fictional EV Purchase Grant (spec §7) — self-contained, no model knowledge."""

    amount_eur: int = 6000
    price_cap_eur: int = 50000
    effective_date: str = ""  # ISO date; applications on/after this date may qualify

    @classmethod
    def from_config(cls, cfg: Config, effective_date: str) -> GrantRule:
        return cls(amount_eur=cfg.golden_path.grant_amount_eur,
                   price_cap_eur=cfg.golden_path.price_cap_eur, effective_date=effective_date)

    def qualifies(self, app: Application) -> bool:
        """BEV, at/under the cap, on/after the effective date."""
        if app.vehicle.type != "BEV":
            return False
        if app.vehicle.list_price_eur > self.price_cap_eur:
            return False
        if self.effective_date and app.application_date < self.effective_date:
            return False
        return True


    def subsidy_evidence(self, app: Application, decision: Decision) -> tuple[dict, bool]:
        """Representative tool evidence, shared by generated history and live traces."""
        eligible = self.qualifies(app)
        if eligible:
            note = "qualifying EV purchase grant available at application date"
        elif self.effective_date and app.application_date < self.effective_date:
            note = "grant not yet effective at application date"
        else:
            note = "vehicle does not qualify for the EV purchase grant"
        report = {
            "applicable_subsidies": ([{"name": "EV Purchase Grant", "amount_eur": self.amount_eur}]
                                    if eligible else []),
            "policy": asdict(self),
            "note": note,
        }
        return report, eligible and decision.applied_grant_eur == 0


DEFAULT_RULE = GrantRule()


# ---------------------------------------------------------------------------
# Deterministic policy — a faithful mirror of prompts/credit_decision.v{1,2}.txt
# ---------------------------------------------------------------------------
def _decide_deterministic(app: Application, prompt_label: str, rule: GrantRule) -> Decision:
    list_price = app.vehicle.list_price_eur
    line = app.approved_line_eur

    if prompt_label == "v1":
        grant = 0
    elif prompt_label == "v2":
        grant = rule.amount_eur if rule.qualifies(app) else 0
    else:
        raise ValueError(f"unknown prompt_label {prompt_label!r} (expected 'v1' or 'v2')")

    financed = list_price - grant
    approve = financed <= line

    if approve and grant:
        reason = (
            f"BEV qualifies for the EUR {grant:,} purchase grant, reducing the financed "
            f"amount to EUR {financed:,}, within the approved line of EUR {line:,}."
        )
    elif approve:
        reason = (
            f"Financed amount of EUR {financed:,} is within the approved line of EUR {line:,}."
        )
    else:
        reason = (
            f"Financed amount of EUR {financed:,} exceeds the approved line of EUR {line:,}."
        )

    return Decision(
        decision="approve" if approve else "reject",
        list_price_eur=list_price,
        applied_grant_eur=grant,
        financed_principal_eur=financed,
        approved_line_eur=line,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Live path — fetch the managed prompt by label and call the model (demo time)
# ---------------------------------------------------------------------------
def _decide_live(
    app: Application,
    prompt_label: str,
    *,
    lf,
    llm,
    prompt_name: str,
    rule: GrantRule,
    variables: dict | None = None,
) -> Decision:
    # cache_ttl_seconds=0: always pull the *current* labelled version, so promoting a new
    # prompt to `production` in the UI takes effect on the very next experiment run.
    prompt = lf.get_prompt(prompt_name, label=prompt_label, type="chat", cache_ttl_seconds=0)
    from .policy import policy_variables
    from .seed.prompts import decision_schema
    application_json = app.model_dump_json()
    variables = variables if variables is not None else policy_variables(app, rule)
    messages = prompt.compile(**variables)

    # Split Langfuse chat messages into a system prompt + turns (the provider layer
    # re-attaches the system prompt in each SDK's native shape).
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    turns = [m for m in messages if m.get("role") != "system"]
    if not turns:
        turns = [{"role": "user", "content": application_json}]

    # Log the model call as a `decision` generation nested in the caller's trace (the
    # experiment item's trace), with the compiled chat turn as input and the managed
    # prompt linked — same shape as the seeded decision generations.
    chat = [{"role": m.get("role"), "content": m.get("content")} for m in messages]
    with lf.start_as_current_observation(
        as_type="generation", name="decision", model=llm.model, input=chat,
        model_parameters={"max_tokens": 512}, prompt=prompt,
        metadata={"prompt_variables": variables, "response_schema": decision_schema()},
    ) as gen:
        result = llm.complete(system=system, messages=turns, max_tokens=512,
                              response_schema=decision_schema())
        gen.update(output=result.text, usage_details={"input": result.input_tokens, "output": result.output_tokens})
        decision = parse_decision(result.text, app)
        gen.update(output=decision.model_dump(),
                   usage_details={"input": result.input_tokens,
                                  "output": result.output_tokens})
    return decision


def parse_decision(text: str, app: Application) -> Decision:
    """Validate one complete response; never repair or select a later correction."""
    decision = Decision.model_validate_json(text, strict=True)
    if decision.list_price_eur != app.vehicle.list_price_eur or decision.approved_line_eur != app.approved_line_eur:
        raise ValueError("decision amounts do not match the application")
    if not 0 <= decision.applied_grant_eur <= decision.list_price_eur:
        raise ValueError("applied grant must be between zero and the purchase price")
    if decision.financed_principal_eur != decision.list_price_eur - decision.applied_grant_eur:
        raise ValueError("financed principal does not match purchase price minus grant")
    expected = "approve" if decision.financed_principal_eur <= decision.approved_line_eur else "reject"
    if decision.decision != expected:
        raise ValueError("decision contradicts financed principal and approved line")
    return decision


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def decide(
    application: "Application | dict",
    prompt_label: str,
    *,
    rule: GrantRule = DEFAULT_RULE,
    live: bool = False,
    lf=None,
    llm=None,
    prompt_name: str = "credit_decision",
) -> Decision:
    """Return a structured Decision. ``prompt_label`` ('v1'|'v2') is the only lever.

    Default (seed path) is deterministic and model-free. Pass ``live=True`` with a
    Langfuse client (``lf``) and an :class:`~langfuse_synth_core.companion.llm.LLMClient`
    (``llm``) to run the
    real agent path used by the demo-time experiment; the client owns the resolved
    provider and model.
    """
    app = Application.from_input(application)
    if live:
        if lf is None or llm is None:
            raise ValueError("live=True requires both lf (Langfuse) and llm (LLMClient) clients")
        variables = application if isinstance(application, dict) and "handbook" in application and "policy_updates" in application else None
        return _decide_live(app, prompt_label, lf=lf, llm=llm, prompt_name=prompt_name,
                            rule=rule, variables=variables)
    return _decide_deterministic(app, prompt_label, rule)
