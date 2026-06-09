"""Register the v1 (stale) and v2 (fixed) system prompts in prompt management (spec §7, §17).

Registered as **chat** prompts: a system message (the policy) plus a ``{{application}}``
user message, so ``decide()``'s live path can ``compile(application=...)`` and split into
Anthropic system + messages. ``{{grant_date}}`` in v2 is baked to the seeded effective
date so the stored prompt shows the real date and matches the judge's constant.

v1 is registered first so its version is 1 — the version the backdated ``decision``
generations link to ("every bad decision used v1" is visibly true).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


def _read(label: str) -> str:
    return (PROMPTS_DIR / f"credit_decision.{label}.txt").read_text().rstrip() + "\n"


def _chat_prompt(system_text: str) -> list[dict]:
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": "{{application}}"},
    ]


def _norm(msgs) -> list[tuple]:
    # Langfuse stores chat messages with an extra ``type: "message"`` key, so compare on
    # (role, content) only — otherwise the round-tripped prompt never equals what we built.
    return [(m.get("role"), m.get("content")) for m in (msgs or [])]


def _reuse_or_create(lf, name: str, prompt: list[dict], label: str, commit: str) -> int:
    """Return the version for ``label``: reuse the existing labelled version if its content
    already matches (idempotent re-seed — no version churn), else create a new version.

    Without this, every re-seed appends a fresh version (v1/v2 drift to 3/4, 5/6, …); the
    demo wants ``decision`` generations to link to a stable v1 == version 1."""
    try:
        existing = lf.get_prompt(name, label=label, type="chat", cache_ttl_seconds=0)
        if _norm(getattr(existing, "prompt", None)) == _norm(prompt):
            return getattr(existing, "version", None)
    except Exception:  # noqa: BLE001 — not found / first run: fall through to create
        pass
    created = lf.create_prompt(name=name, type="chat", prompt=prompt,
                               labels=[label], commit_message=commit)
    return getattr(created, "version", None)


def register_prompts(lf, cfg, effective_date: datetime, *, register_v1: bool = True,
                     register_v2: bool = True) -> dict[str, int]:
    """Create v1 then v2; return {'v1': version, 'v2': version}. Idempotent on content: a
    re-seed reuses the existing versions instead of appending duplicates (so v1 stays == 1)."""
    from ..timegen import iso_date

    name = cfg.golden_path.prompt_name
    versions: dict[str, int] = {}

    if register_v1:
        versions["v1"] = _reuse_or_create(
            lf, name, _chat_prompt(_read("v1")), "v1",
            "stale prompt: gross-price affordability")

    if register_v2:
        v2_text = _read("v2").replace("{{grant_date}}", iso_date(effective_date))
        versions["v2"] = _reuse_or_create(
            lf, name, _chat_prompt(v2_text), "v2",
            "fix: apply EV purchase grant before affordability")

    return versions
