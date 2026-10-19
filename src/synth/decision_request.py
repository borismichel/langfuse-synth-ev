"""Prepare one decision request and its matching observation input."""
from dataclasses import dataclass
from typing import Any

from .seed.prompts import decision_schema


@dataclass(frozen=True)
class DecisionRequest:
    messages: list[dict]
    parameters: dict
    kwargs: dict


def prepare_decision_request(prompt: Any, variables: dict[str, str], provider: str) -> DecisionRequest:
    """Keep provider arguments, recorded messages and effective parameters together."""
    messages = [{"role": message["role"], "content": message["content"]}
                for message in prompt.compile(**variables)]
    turns = [message for message in messages if message["role"] != "system"]
    if not turns:
        turns = [{"role": "user", "content": variables["application"]}]
        messages.extend(turns)
    parameters = {"max_tokens": 512}
    if provider == "openai":
        parameters["temperature"] = 0
    kwargs = {"system": "\n\n".join(message["content"] for message in messages
                                     if message["role"] == "system"),
              "messages": turns, "response_schema": decision_schema(), **parameters}
    return DecisionRequest(messages=messages, parameters=parameters, kwargs=kwargs)
