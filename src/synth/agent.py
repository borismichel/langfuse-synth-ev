"""The single agent function — the only lever is the prompt label (spec §7, §17).

``decide(application, prompt_label) -> Decision`` is the shared spine: seeding and
the live experiment both route through it, so they can never drift apart.

Two execution paths, identical contract:

- **Deterministic (seed path, default).** Pure arithmetic that *mirrors the prompt
  text byte-for-byte*: v1 finances the gross list price; v2 subtracts a qualifying
  EV grant first. No model call — a few-thousand-trace seed is free and reproducible
  (spec §2, §9). The seeded v1 rejections are exactly what ``decide(app, "v1")``
  produces, so they are authentic *and* judge-failable.

- **Live (demo path).** ``decide(app, label, live=True, lf=..., llm=...)`` fetches the
  system prompt from Langfuse prompt management by label, calls the model at
  temperature 0, and parses the structured Decision. This is the production agent
  path the experiment exercises with the fixed prompt.

The grant rule (amount, cap, effective date) is data, passed in ``GrantRule`` — the
same numbers the v2 prompt and the judge reference, sourced from ``config/demo.yaml``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .models import Application, Decision


@dataclass(frozen=True)
class GrantRule:
    """The fictional EV Purchase Grant (spec §7) — self-contained, no model knowledge."""

    amount_eur: int = 6000
    price_cap_eur: int = 50000
    effective_date: str = ""  # ISO date; applications on/after this date may qualify

    def qualifies(self, app: Application) -> bool:
        """BEV, at/under the cap, on/after the effective date."""
        if app.vehicle.type != "BEV":
            return False
        if app.vehicle.list_price_eur > self.price_cap_eur:
            return False
        if self.effective_date and app.application_date < self.effective_date:
            return False
        return True


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
) -> Decision:
    # cache_ttl_seconds=0: always pull the *current* labelled version, so promoting a new
    # prompt to `production` in the UI takes effect on the very next experiment run.
    prompt = lf.get_prompt(prompt_name, label=prompt_label, type="chat", cache_ttl_seconds=0)
    application_json = app.model_dump_json()
    messages = prompt.compile(application=application_json)

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
        model_parameters={"temperature": 0, "max_tokens": 512}, prompt=prompt,
    ) as gen:
        result = llm.complete(system=system, messages=turns, temperature=0, max_tokens=512)
        decision = parse_decision(result.text, app)
        gen.update(output=decision.model_dump(),
                   usage_details={"input": result.input_tokens,
                                  "output": result.output_tokens})
    return decision


def parse_decision(text: str, app: Application) -> Decision:
    """Parse the model's JSON object into a Decision, tolerating code fences/prose."""
    raw = _extract_json(text)
    data = json.loads(raw)
    # Backfill any field the model omitted from the application so the contract holds.
    data.setdefault("list_price_eur", app.vehicle.list_price_eur)
    data.setdefault("approved_line_eur", app.approved_line_eur)
    if "financed_principal_eur" not in data and "applied_grant_eur" in data:
        data["financed_principal_eur"] = app.vehicle.list_price_eur - int(data["applied_grant_eur"])
    return Decision.model_validate(data)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in model output: {text[:200]!r}")
    return text[start : end + 1]


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
        return _decide_live(app, prompt_label, lf=lf, llm=llm, prompt_name=prompt_name)
    return _decide_deterministic(app, prompt_label, rule)
