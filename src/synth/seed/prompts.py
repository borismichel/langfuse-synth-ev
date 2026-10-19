"""Register context-assembly baseline and candidate as versioned chat prompts."""
from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from langfuse_synth_core.http import request_retry

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


@lru_cache(maxsize=None)
def prompt_text(label: str) -> str:
    """The user-message template registered and replayed in historical inputs."""
    return (PROMPTS_DIR / f"credit_decision.{label}.txt").read_text().rstrip() + "\n"


def set_version_labels(base_url: str, name: str, version: int, labels: list[str]) -> None:
    """Set the labels on a specific prompt version (PATCH /versions/{version}).

    Run on every seed so the demo's environment labels are (re)asserted — ``production``→v1
    (stale) and ``development``→v2 (the fix) — even on a re-seed where idempotent
    registration reused the versions without re-applying labels. ``newLabels`` replaces the
    version's labels and is unique across versions, so re-asserting also moves a label back
    if it was promoted elsewhere (e.g. ``production`` flipped to v2 during a prior demo)."""
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sec = os.environ.get("LANGFUSE_SECRET_KEY", "")
    resp = request_retry(
        "PATCH", f"{base_url.rstrip('/')}/api/public/v2/prompts/{name}/versions/{version}",
        json={"newLabels": labels}, auth=(pub, sec), timeout=15)
    resp.raise_for_status()


def chat_prompt(label: str) -> list[dict]:
    """Both templates share instructions; v2 adds only the updates binding."""
    return [
        {"role": "system", "content": (PROMPTS_DIR / "credit_decision.system.txt").read_text()},
        {"role": "user", "content": prompt_text(label).rstrip()},
    ]


def decision_schema() -> dict:
    import json
    return json.loads((PROMPTS_DIR / "decision-schema.json").read_text())


def prompt_config(cfg) -> dict:
    return {"model": cfg.model_by_role("work").name, "max_tokens": 512,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "credit_decision", "strict": True, "schema": decision_schema()}}}


def _norm(msgs) -> list[tuple]:
    # Langfuse stores chat messages with an extra ``type: "message"`` key, so compare on
    # (role, content) only — otherwise the round-tripped prompt never equals what we built.
    return [(m.get("role"), m.get("content")) for m in (msgs or [])]


def _reuse_or_create(lf, name: str, prompt: list[dict], lookup_label: str,
                     create_labels: list[str], commit: str, config: dict) -> int:
    """Return the version for ``lookup_label``: reuse the existing labelled version if its
    content already matches (idempotent re-seed — no version churn), else create a new
    version carrying ``create_labels``.

    Without this, every re-seed appends a fresh version (v1/v2 drift to 3/4, 5/6, …); the
    demo wants ``decision`` generations to link to a stable v1 == version 1."""
    try:
        existing = lf.get_prompt(name, label=lookup_label, type="chat", cache_ttl_seconds=0)
        if (_norm(getattr(existing, "prompt", None)) == _norm(prompt)
                and getattr(existing, "config", None) == config):
            return getattr(existing, "version", None)
    except Exception:  # noqa: BLE001 — not found / first run: fall through to create
        pass
    created = lf.create_prompt(name=name, type="chat", prompt=prompt,
                               labels=create_labels, commit_message=commit, config=config)
    return getattr(created, "version", None)


def register_prompts(lf, cfg, effective_date: datetime, *, register_v1: bool = True,
                     register_v2: bool = True) -> dict[str, int]:
    """Create v1 then v2; return {'v1': version, 'v2': version}. Idempotent on content.

    v1 is seeded as the **incumbent `production` prompt** (the one quietly mis-deciding);
    v2 is registered as the fix but **not** promoted. The demo's experiment runs whatever
    is labelled ``production``, so the presenter flips ``production`` v1 → v2 to go red → green.
    A fresh seed always starts with production == v1 (the reset state)."""
    name = cfg.golden_path.prompt_name
    versions: dict[str, int] = {}

    for label, enabled in (("v1", register_v1), ("v2", register_v2)):
        if enabled:
            versions[label] = _reuse_or_create(
                lf, name, chat_prompt(label), label, [label],
                "application and handbook" if label == "v1" else "bind retrieved policy updates",
                prompt_config(cfg))
    return versions
