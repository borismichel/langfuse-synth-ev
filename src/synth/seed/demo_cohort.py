"""Small model-free policy cohort for native prompt experiments (portal #234).

The table specifies expectations independently of the agent's v2 implementation.
Offsets keep the cases on the configured policy boundaries when a run is retargeted.
No synthetic trace IDs: these are authored policy cases, not observed production data.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid5

from ..agent import GrantRule
from ..models import Application, Decision, Vehicle, VehicleType


def demonstration_items(rule: GrantRule, dataset_name: str) -> list[dict]:
    cap, grant = rule.price_cap_eur, rule.amount_eur
    day = date.fromisoformat(rule.effective_date)
    price = cap * 21 // 25
    gap = min(2000, max(1, grant // 2))
    near_cap = cap - max(1, cap // 25)
    net = price - grant
    # scenario, type, price, credit line, day offset, grant, principal, decision
    cases: list[tuple[str, VehicleType, int, int, int, int, int, str]] = [
        ("false_negative", "BEV", price, price - gap, 0, grant, net, "approve"),
        ("grant_still_above_line", "BEV", near_cap, near_cap - grant - gap,
         0, grant, near_cap - grant, "reject"),
        ("cap_equal", "BEV", cap, cap - grant, 0, grant, cap - grant, "approve"),
        ("cap_above", "BEV", cap + 1, cap - 1000, 0, 0, cap + 1, "reject"),
        ("control_phev", "PHEV", price, price - gap, 0, 0, price, "reject"),
        ("control_ice", "ICE", price, price, 0, 0, price, "approve"),
        ("date_before", "BEV", price, price - gap, -1, 0, price, "reject"),
        ("date_on_line_equal", "BEV", price, net, 0, grant, net, "approve"),
        ("date_after_line_below", "BEV", price, net - 1, 1, grant, net, "reject"),
        ("cap_below", "BEV", cap - 1, cap - grant, 0, grant, cap - 1 - grant, "approve"),
        ("line_above", "BEV", price, net + 1, 0, grant, net, "approve"),
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
            "input": {"application": application.model_dump_json()},
            "expected_output": expected.model_dump(),
            "metadata": {"scenario": scenario, "source": "hand-worked fictional policy cases",
                         "expectation_basis": basis, "grant_effective_date": str(day)},
        })
    return rows
