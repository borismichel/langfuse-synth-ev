"""Register the v1 (stale) and v2 (fixed) system prompts in prompt management (spec §7, §17).

Registered as **chat** prompts: a system message (the policy) plus a ``{{application}}``
user message, so ``decide()``'s live path can ``compile(application=...)`` and split into
Anthropic system + messages. ``{{grant_date}}`` in v2 is baked to the seeded effective
date so the stored prompt shows the real date and matches the judge's constant.

v1 is registered first so its version is 1 — the version the backdated ``decision``
generations link to ("every bad decision used v1" is visibly true).
"""
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
    """The system-prompt text for a label ('v1'|'v2') — the same bytes that get
    registered in prompt management and that seeded decision inputs display."""
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


def _chat_prompt(system_text: str) -> list[dict]:
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": "{{application}}"},
    ]


def _norm(msgs) -> list[tuple]:
    # Langfuse stores chat messages with an extra ``type: "message"`` key, so compare on
    # (role, content) only — otherwise the round-tripped prompt never equals what we built.
    return [(m.get("role"), m.get("content")) for m in (msgs or [])]


def _reuse_or_create(lf, name: str, prompt: list[dict], lookup_label: str,
                     create_labels: list[str], commit: str) -> int:
    """Return the version for ``lookup_label``: reuse the existing labelled version if its
    content already matches (idempotent re-seed — no version churn), else create a new
    version carrying ``create_labels``.

    Without this, every re-seed appends a fresh version (v1/v2 drift to 3/4, 5/6, …); the
    demo wants ``decision`` generations to link to a stable v1 == version 1."""
    try:
        existing = lf.get_prompt(name, label=lookup_label, type="chat", cache_ttl_seconds=0)
        if _norm(getattr(existing, "prompt", None)) == _norm(prompt):
            return getattr(existing, "version", None)
    except Exception:  # noqa: BLE001 — not found / first run: fall through to create
        pass
    created = lf.create_prompt(name=name, type="chat", prompt=prompt,
                               labels=create_labels, commit_message=commit)
    return getattr(created, "version", None)


def register_prompts(lf, cfg, effective_date: datetime, *, register_v1: bool = True,
                     register_v2: bool = True) -> dict[str, int]:
    """Create v1 then v2; return {'v1': version, 'v2': version}. Idempotent on content.

    v1 is seeded as the **incumbent `production` prompt** (the one quietly mis-deciding);
    v2 is registered as the fix but **not** promoted. The demo's experiment runs whatever
    is labelled ``production``, so the presenter flips ``production`` v1 → v2 to go red → green.
    A fresh seed always starts with production == v1 (the reset state)."""
    from langfuse_synth_core.timegen import iso_date

    name = cfg.golden_path.prompt_name
    versions: dict[str, int] = {}

    if register_v1:
        # production is asserted separately (set_production_label) so it resets on re-seed.
        versions["v1"] = _reuse_or_create(
            lf, name, _chat_prompt(prompt_text("v1")), "v1", ["v1"],
            "stale prompt: gross-price affordability")

    if register_v2:
        v2_text = prompt_text("v2").replace("{{grant_date}}", iso_date(effective_date))
        versions["v2"] = _reuse_or_create(
            lf, name, _chat_prompt(v2_text), "v2", ["v2"],
            "fix: apply EV purchase grant before affordability")

    return versions
