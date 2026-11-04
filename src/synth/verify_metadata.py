"""Read-only release check for full Langfuse observation-list JSON exports."""
import argparse
import json
from pathlib import Path
from typing import Any

from .models import Application


def check_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Reject missing evidence and dotted keys instead of repairing their shape."""
    if observation.get("name") != "decision" or observation.get("type") != "GENERATION":
        raise ValueError("expected one decision generation")
    if observation.get("promptName") != "credit_decision" or type(observation.get("promptVersion")) is not int:
        raise ValueError("expected a recorded credit_decision prompt version")
    metadata = observation.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("missing observation metadata")
    if any(key.startswith(("prompt_variables.", "response_schema.")) for key in metadata):
        raise ValueError("literal dotted metadata keys do not match historical selectors")
    variables = metadata.get("prompt_variables")
    if not isinstance(variables, dict):
        raise ValueError("prompt_variables must be a nested object; export expanded metadata")
    decoded = {}
    for key in ("application", "handbook", "policy_updates"):
        if not isinstance(variables.get(key), str):
            raise ValueError(f"prompt_variables.{key} must be a JSON string")
        try:
            decoded[key] = json.loads(variables[key])
        except ValueError:
            raise ValueError(f"prompt_variables.{key} is invalid or truncated JSON") from None
    application = Application.model_validate(decoded["application"])
    handbook = decoded["handbook"]
    updates = decoded["policy_updates"]
    if not isinstance(handbook, dict) or not handbook.get("content"):
        raise ValueError("handbook must contain policy text")
    if not isinstance(updates, list):
        raise ValueError("policy_updates must encode an array; only [] means no published updates")
    if any(not isinstance(update, dict) or not update.get("content") for update in updates):
        raise ValueError("each policy update must contain policy text")
    schema = metadata.get("response_schema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("response_schema must be a nested JSON Schema object")
    if schema.get("properties", {}).get("decision", {}).get("enum") != ["approve", "reject"]:
        raise ValueError("response_schema must preserve the approve/reject decision enum")
    return {
        "trace_id": observation["traceId"], "observation_id": observation["id"],
        "prompt_version": observation["promptVersion"],
        "application_date": application.application_date, "policy_update_count": len(updates),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", type=Path, nargs="+", help="CLI exports, one decision observation per file")
    args = parser.parse_args()
    receipts = []
    for path in args.exports:
        try:
            export = json.loads(path.read_text())
            body = export.get("body", export)
            observations = body["data"]
            if not isinstance(observations, list) or len(observations) != 1:
                raise ValueError("export exactly one decision using --trace-id and --name decision")
            receipts.append({"file": str(path), **check_observation(observations[0])})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            parser.exit(1, f"metadata check failed for {path}: {error}\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
