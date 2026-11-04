"""One persisted metadata shape for seeded, companion and experiment decisions.

Langfuse's SDK-v5 ingestion flattens nested objects into literal dotted keys;
raw OTLP seed metadata takes a different decoding path. Emit those keys
explicitly through both public writers so ingestion cannot change their shape.
Prompt-variable JSON strings remain leaves, including the explicit empty list
for policy updates that were not published at the application date.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def decision_metadata(variables: Mapping[str, str], response_schema: dict,
                      *, execution: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"decision_metadata_version": 1}
    if execution is not None:
        metadata["execution"] = execution
    for name in ("application", "handbook", "policy_updates"):
        metadata[f"prompt_variables.{name}"] = variables[name]

    def add_schema(path: str, value: Any) -> None:
        if isinstance(value, dict) and value:
            for key, child in value.items():
                add_schema(f"{path}.{key}", child)
        else:
            metadata[path] = value

    add_schema("response_schema", response_schema)
    return metadata
