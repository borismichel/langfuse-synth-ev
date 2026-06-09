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


def register_prompts(lf, cfg, effective_date: datetime, *, register_v1: bool = True,
                     register_v2: bool = True) -> dict[str, int]:
    """Create v1 then v2; return {'v1': version, 'v2': version}. Idempotent-ish: re-runs add
    new versions but labels move to the latest, which is fine for a fresh demo project."""
    from ..timegen import iso_date

    name = cfg.golden_path.prompt_name
    versions: dict[str, int] = {}

    if register_v1:
        v1 = lf.create_prompt(name=name, type="chat", prompt=_chat_prompt(_read("v1")),
                              labels=["v1"], commit_message="stale prompt: gross-price affordability")
        versions["v1"] = getattr(v1, "version", 1)

    if register_v2:
        v2_text = _read("v2").replace("{{grant_date}}", iso_date(effective_date))
        v2 = lf.create_prompt(name=name, type="chat", prompt=_chat_prompt(v2_text),
                              labels=["v2"], commit_message="fix: apply EV purchase grant before affordability")
        versions["v2"] = getattr(v2, "version", 2)

    return versions
