"""Decision evidence shared by raw-OTLP history and SDK-v5 callers."""
import json
from typing import Any


def decision_metadata(variables: dict[str, str], response_schema: dict[str, Any]) -> dict[str, str]:
    """Keep structured evidence in JSON string leaves, preserving historical selectors.

    Raw OTLP passes strings through; SDK v5 JSON-encodes them and ingestion decodes
    that layer once. Both store the same leaf without flattening its nested keys.
    Compact encoding also preserves the existing historical spool byte for byte.
    See docs/decision-metadata.md for the persisted contract and release gate.
    """
    return {
        "prompt_variables": json.dumps(variables, separators=(",", ":")),
        "response_schema": json.dumps(response_schema, separators=(",", ":")),
    }
