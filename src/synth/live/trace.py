"""Instrument the work actually executed: local lookup, compilation and model call."""
from __future__ import annotations
from typing import Any
from ..agent import GrantRule, parse_decision
from ..config import Config
from ..evaluation.production import live_scope
from ..models import Application, Decision
from ..policy import lookup_policy, policy_variables
from ..seed.prompts import decision_schema

TRACE_NAME = "credit_agent.assess_application"


def emit_live_trace(emitter: Any, cfg: Config, *, application: Application,
                    rule: GrantRule, llm: Any, prompt: Any,
                    tags: list[str] | None = None, user_id: str = "playground_user",
                    environment: str = "production") -> tuple[Decision, str]:
    """Execute the decision inside real observation boundaries and flush its receipt."""
    with emitter.trace(TRACE_NAME, user_id=user_id, environment=environment,
                       tags=list(tags or []), input=application.model_dump(),
                       metadata={"kind": "live", "vehicle_type": application.vehicle.type,
                                 "execution": "live"}) as trace:
        with trace.observation("credit_agent", as_type="agent", input=application.model_dump(),
                metadata={"evaluation_scope": live_scope(cfg.golden_path.prompt_name, rule),
                          "prompt_name": cfg.golden_path.prompt_name,
                          "prompt_version": prompt.version, "execution": "live"}) as agent:
            with agent.observation("retrieve_policy", as_type="retriever",
                    input={"application_date": application.application_date},
                    metadata={"retriever": "bundled_policy_lookup", "execution": "live"}) as retrieval:
                documents = lookup_policy(application, rule)
                retrieval.update(output=documents)
            variables = policy_variables(application, rule, documents=documents)
            messages = prompt.compile(**variables)
            system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
            turns = [m for m in messages if m.get("role") != "system"]
            parameters = {"max_tokens": 512}
            if llm.provider == "openai":
                parameters["temperature"] = 0
            with agent.generation("decision", model=llm.model, input=messages,
                    model_parameters=parameters, prompt=prompt,
                    metadata={"execution": "live_model_call", "prompt_variables": variables,
                              "response_schema": decision_schema()}) as generation:
                result = llm.complete(system=system, messages=turns, max_tokens=512,
                                      response_schema=decision_schema())
                generation.update(output=result.text,
                                  usage_details={"input": result.input_tokens, "output": result.output_tokens})
                decision = parse_decision(result.text, application)
                generation.update(output=decision.model_dump())
            agent.update(output=decision.model_dump())
        trace.update(output=decision.model_dump())
        trace_id = trace.id
    return decision, trace_id
