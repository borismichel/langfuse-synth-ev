"""Local, versioned policy lookup and the native prompt-variable contract."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .agent import GrantRule
    from .models import Application


def lookup_policy(application: Application, rule: GrantRule | None) -> dict:
    """Read the bundled documents, resolving dates from the deployment policy anchor."""
    fixture = json.loads(Path(__file__).with_name("fixtures").joinpath("policy.json").read_text())
    anchor = date.fromisoformat(rule.effective_date if rule and rule.effective_date else application.application_date)
    values = {"handbook_date": (anchor - timedelta(days=180)).isoformat(),
              "published_date": (anchor - timedelta(days=7)).isoformat(),
              "effective_date": anchor.isoformat(),
              "price_cap": f"{rule.price_cap_eur:,}" if rule else "",
              "grant_amount": f"{rule.amount_eur:,}" if rule else ""}
    def render(document):
        return {key: value.format(**values) for key, value in document.items()}
    return {"handbook": render(fixture["handbook"]),
            "policy_updates": [render(fixture["policy_update"])] if rule else []}


def policy_variables(application: Application, rule: GrantRule | None, *, documents: dict | None = None) -> dict[str, str]:
    """Same complete string dictionary for both templates and native datasets."""
    documents = lookup_policy(application, rule) if documents is None else documents
    return {"application": application.model_dump_json(),
            **{key: json.dumps(documents[key], sort_keys=True, ensure_ascii=False)
               for key in ("handbook", "policy_updates")}}
