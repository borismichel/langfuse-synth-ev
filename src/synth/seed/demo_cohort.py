"""Small model-free policy cohort for native prompt experiments (portal #234).

The table specifies expectations independently of the agent's v2 implementation.
Offsets keep the cases on the configured policy boundaries when a run is retargeted.
No synthetic trace IDs: these are authored policy cases, not observed production data.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid5

from ..agent import GrantRule
from ..policy import policy_variables
from ..models import Application, Decision, Vehicle, VehicleType


def demonstration_items(rule: GrantRule, dataset_name: str) -> list[dict]:
    cap, grant = rule.price_cap_eur, rule.amount_eur
    day = date.fromisoformat(rule.effective_date)
    price = cap * 9 // 10
    gap = min(cap // 10, max(1, grant - 1000))
    line = price - gap
    near_cap = cap - max(1, cap // 50)
    affordable = min(cap * 39 // 50, line)
    ice_price = min(cap * 7 // 10, line)
    # scenario, type, price, credit line, day offset, grant, principal, decision.
    # Default policy reproduces the eight independently reviewed simulation cases.
    # Configured policies retain their eligibility and affordability contrasts.
    cases: list[tuple[str, VehicleType, int, int, int, int, int, str]] = [
        ("false_negative", "BEV", price, line, 0, grant, price - grant, "approve"),
        ("date_before", "BEV", price, line, -1, 0, price, "reject"),
        ("control_phev", "PHEV", price, line, 0, 0, price, "reject"),
        ("cap_above", "BEV", cap + 1, line, 0, 0, cap + 1, "reject"),
        ("grant_still_above_line", "BEV", near_cap, min(line, near_cap - grant - 1),
         0, grant, near_cap - grant, "reject"),
        ("cap_date_line_equal", "BEV", cap, cap - grant, 0, grant, cap - grant, "approve"),
        ("eligible_already_affordable", "BEV", affordable, line,
         0, grant, affordable - grant, "approve"),
        ("control_ice", "ICE", ice_price, line, 0, 0, ice_price, "approve"),
    ]
    rows = []
    for scenario, kind, gross, line, offset, benefit, principal, verdict in cases:
        application = Application(
            applicant_id=f"demo_{scenario}", approved_line_eur=line,
            vehicle=Vehicle(type=kind, list_price_eur=gross),
            application_date=(day + timedelta(days=offset)).isoformat())
        basis = (f"Fictional policy effective {day}: BEV at or below EUR {cap} receives "
                 f"EUR {grant} on/after that date. EUR {gross} - EUR {benefit} = "
                 f"EUR {principal}; {'<=' if verdict == 'approve' else '>'} EUR {line}.")
        expected = Decision.model_validate({
            "decision": verdict, "list_price_eur": gross, "applied_grant_eur": benefit,
            "financed_principal_eur": principal, "approved_line_eur": line, "reason": basis})
        rows.append({
            "id": str(uuid5(NAMESPACE_URL, f"{dataset_name}/{scenario}")),
            "input": policy_variables(application, rule),
            "expected_output": expected.model_dump(),
            "metadata": {"scenario": scenario, "source": "hand-worked fictional policy cases",
                         "expectation_basis": basis, "grant_effective_date": str(day)},
        })
    return rows
