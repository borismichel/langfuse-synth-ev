"""Builders for batch-ingestion event envelopes (spec §2, §3).

Each returns the ``{id, type, timestamp, body}`` envelope the ingestion endpoint
expects. Envelope ids are derived from the object id + type so re-runs are idempotent.
Field names match the OpenAPI bodies exactly (TraceBody / CreateSpanBody /
CreateGenerationBody / CreateEventBody / ScoreBody).
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from ..timegen import iso


def _envelope_id(obj_id: str, etype: str) -> str:
    return hashlib.blake2b(f"{etype}:{obj_id}".encode(), digest_size=16).hexdigest()


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def trace_event(
    *,
    trace_id: str,
    timestamp: datetime,
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    environment: str = "production",
    metadata: dict | None = None,
    input=None,
    output=None,
) -> dict:
    body = _clean(
        {
            "id": trace_id,
            "timestamp": iso(timestamp),
            "name": name,
            "userId": user_id,
            "sessionId": session_id,
            "tags": tags,
            "environment": environment,
            "metadata": metadata,
            "input": input,
            "output": output,
        }
    )
    return {"id": _envelope_id(trace_id, "trace-create"), "type": "trace-create",
            "timestamp": iso(timestamp), "body": body}


def span_event(
    *,
    obs_id: str,
    trace_id: str,
    name: str,
    start: datetime,
    end: datetime,
    parent_id: str | None = None,
    environment: str = "production",
    input=None,
    output=None,
    level: str | None = None,
    status_message: str | None = None,
    metadata: dict | None = None,
) -> dict:
    body = _clean(
        {
            "id": obs_id,
            "traceId": trace_id,
            "name": name,
            "startTime": iso(start),
            "endTime": iso(end),
            "parentObservationId": parent_id,
            "environment": environment,
            "input": input,
            "output": output,
            "level": level,
            "statusMessage": status_message,
            "metadata": metadata,
        }
    )
    return {"id": _envelope_id(obs_id, "span-create"), "type": "span-create",
            "timestamp": iso(start), "body": body}


def generation_event(
    *,
    obs_id: str,
    trace_id: str,
    name: str,
    start: datetime,
    end: datetime,
    model: str,
    usage_details: dict,
    cost_details: dict,
    parent_id: str | None = None,
    environment: str = "production",
    input=None,
    output=None,
    level: str | None = None,
    status_message: str | None = None,
    metadata: dict | None = None,
    prompt_name: str | None = None,
    prompt_version: int | None = None,
    model_parameters: dict | None = None,
) -> dict:
    body = _clean(
        {
            "id": obs_id,
            "traceId": trace_id,
            "name": name,
            "startTime": iso(start),
            "endTime": iso(end),
            "completionStartTime": iso(start),
            "parentObservationId": parent_id,
            "environment": environment,
            "model": model,
            "modelParameters": model_parameters,
            "usageDetails": usage_details,
            "costDetails": cost_details,
            "input": input,
            "output": output,
            "level": level,
            "statusMessage": status_message,
            "metadata": metadata,
            "promptName": prompt_name,
            "promptVersion": prompt_version,
        }
    )
    return {"id": _envelope_id(obs_id, "generation-create"), "type": "generation-create",
            "timestamp": iso(start), "body": body}


def event_event(
    *,
    obs_id: str,
    trace_id: str,
    name: str,
    start: datetime,
    parent_id: str | None = None,
    environment: str = "production",
    level: str | None = None,
    metadata: dict | None = None,
    input=None,
    output=None,
) -> dict:
    """Zero-duration discrete marker (cache hit, guardrail trip) — spec §3."""
    body = _clean(
        {
            "id": obs_id,
            "traceId": trace_id,
            "name": name,
            "startTime": iso(start),
            "parentObservationId": parent_id,
            "environment": environment,
            "level": level,
            "metadata": metadata,
            "input": input,
            "output": output,
        }
    )
    return {"id": _envelope_id(obs_id, "event-create"), "type": "event-create",
            "timestamp": iso(start), "body": body}


def score_event(
    *,
    score_id: str,
    name: str,
    value,
    data_type: str,
    timestamp: datetime,
    trace_id: str | None = None,
    observation_id: str | None = None,
    session_id: str | None = None,
    comment: str | None = None,
    config_id: str | None = None,
    environment: str = "production",
) -> dict:
    """Score on a trace / observation / session. ``value`` is a string for CATEGORICAL,
    numeric for NUMERIC/BOOLEAN (BOOLEAN must be 0 or 1) — per the ScoreBody contract."""
    body = _clean(
        {
            "id": score_id,
            "name": name,
            "value": value,
            "dataType": data_type,
            "traceId": trace_id,
            "observationId": observation_id,
            "sessionId": session_id,
            "comment": comment,
            "configId": config_id,
            "environment": environment,
        }
    )
    return {"id": _envelope_id(score_id, "score-create"), "type": "score-create",
            "timestamp": iso(timestamp), "body": body}
