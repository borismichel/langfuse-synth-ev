"""Standalone Langfuse Python evaluator; only standard-library imports.

The package writer replaces POLICY with this deployment's resolved constants.
Langfuse supplies ctx.observation and optional ctx.experiment; no sibling lookup.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

POLICY = {"amount_eur": 6000, "price_cap_eur": 50000, "effective_date": ""}


@dataclass
class Score:
    name: str
    value: bool
    data_type: str
    comment: str
    metadata: dict[str, Any]


@dataclass
class EvaluationResult:
    scores: list[Score]


def _object(value: Any, label: str) -> dict:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```json\n") and text.endswith("```"):
            text = text[8:-3].strip()
        try:
            value = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{label}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected an object")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label}: expected integer EUR")
    return value


def _day(value: Any, label: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{label}: expected YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid calendar date") from exc
    if result.isoformat() != value:
        raise ValueError(f"{label}: expected YYYY-MM-DD")
    return result


def _message(value: Any, role: str, label: str) -> Any:
    # Native experiment API exports may encode the whole chat array as JSON.
    # Decode the envelope before selecting its one user/assistant message.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass  # Plain output/fenced JSON is handled by _object below.
    if isinstance(value, list):
        messages = [m for m in value if isinstance(m, dict) and m.get("role") == role]
        if len(messages) != 1:
            raise ValueError(f"{label}: expected exactly one {role} message")
        return messages[0].get("content")
    if isinstance(value, dict) and value.get("role") == role:
        return value.get("content")
    return value


def evaluate(ctx: Any) -> EvaluationResult:
    """Score policy correctness; bad context/config raises, malformed output fails distinctly."""
    grant_amount = _integer(POLICY.get("amount_eur"), "policy.amount_eur")
    cap = _integer(POLICY.get("price_cap_eur"), "policy.price_cap_eur")
    effective = _day(POLICY.get("effective_date"), "policy.effective_date")
    if grant_amount < 0 or cap < 0:
        raise ValueError("policy: amount and cap must be non-negative")
    raw = _message(ctx.observation.input, "user", "input")
    app = _object(raw, "input")
    if "application" in app:
        app = _object(app["application"], "input.application")
    vehicle = _object(app.get("vehicle"), "input.vehicle")
    kind = vehicle.get("type")
    if kind not in ("BEV", "PHEV", "ICE"):
        raise ValueError("input.vehicle.type: expected BEV, PHEV or ICE")
    price = _integer(vehicle.get("list_price_eur"), "input.list_price_eur")
    line = _integer(app.get("approved_line_eur"), "input.approved_line_eur")
    applied_on = _day(app.get("application_date"), "input.application_date")
    benefit = grant_amount if kind == "BEV" and price <= cap and applied_on >= effective else 0
    principal = price - benefit
    expected = {"applied_grant_eur": benefit, "financed_principal_eur": principal,
                "decision": "approve" if principal <= line else "reject"}
    try:
        output = _object(_message(ctx.observation.output, "assistant", "output"), "output")
        for field in ("applied_grant_eur", "financed_principal_eur"):
            _integer(output.get(field), f"output.{field}")
        if output.get("decision") not in ("approve", "reject"):
            raise ValueError("output.decision: expected approve or reject")
    except ValueError as exc:
        return EvaluationResult([Score("policy_correctness", False, "BOOLEAN", str(exc),
                                       {"status": "malformed_output", "policy": POLICY})])
    mismatches = [f"{key}: expected {want}, got {output[key]}"
                  for key, want in expected.items() if output[key] != want]
    explanation = ("; ".join(mismatches) if mismatches else
                   f"Policy correct: grant EUR {benefit}; {price} - {benefit} = {principal}; "
                   f"principal {'<=' if principal <= line else '>'} line {line}: {expected['decision']}.")
    return EvaluationResult([Score("policy_correctness", not mismatches, "BOOLEAN", explanation,
                                  {"status": "policy_error" if mismatches else "pass",
                                   "expected": expected, "policy": POLICY})])
