"""Deployment-specific selection for the one live policy evaluation per submission."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from ..agent import GrantRule


def live_scope(prompt_name: str, rule: GrantRule) -> str:
    """Keep deployments with different prompt names or policy anchors out of this rule."""
    context = json.dumps({"prompt": prompt_name, "policy": asdict(rule)}, sort_keys=True)
    return "ev_live_decision_" + hashlib.sha256(context.encode()).hexdigest()[:16]


def production_rule(prompt_name: str, rule: GrantRule) -> dict:
    """Reviewable UI recipe, deliberately not an API request or automatic deployment."""
    return {
        "name": live_scope(prompt_name, rule),
        "target": "observation",
        "evaluator": "policy_correctness",
        "sampling": 1,
        "match_all": {"name": "credit_agent", "type": "AGENT",
                      "environment": "production",
                      "metadata.evaluation_scope": live_scope(prompt_name, rule)},
        "expected_observations_per_submission": 1,
        "requires_feedback": False,
        "requires_expected_output": False,
        "enable_after_scope_review": True,
    }
