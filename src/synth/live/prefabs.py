"""Five ready-made applications for the playground (plus free-form custom entry).

Each prefab sets a default ``approved_line_eur`` that the UI lets the submitter edit —
nudging the eligible case across the grant margin is the most instructive knob.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..agent import GrantRule
from ..models import Application, Vehicle, VehicleType


@dataclass(frozen=True)
class Prefab:
    key: str
    label: str
    vehicle_type: VehicleType           # BEV | PHEV | ICE
    list_price_eur: int
    approved_line_eur: int
    note: str

    def application(self, *, approved_line_eur: int | None = None,
                    application_date: str = "") -> Application:
        return Application(
            applicant_id="playground_applicant",
            approved_line_eur=approved_line_eur if approved_line_eur is not None else self.approved_line_eur,
            vehicle=Vehicle(type=self.vehicle_type, list_price_eur=self.list_price_eur),
            application_date=application_date,
        )


def prefabs_for_rule(rule: GrantRule) -> list[Prefab]:
    """Keep the ready-made cases on the deployment's grant margin and price cap."""
    eligible_price = min(38000, rule.price_cap_eur)
    rejected_price = min(45000, rule.price_cap_eur)
    return [
        Prefab("eligible", "Eligible BEV (borderline) — the bug", "BEV", eligible_price,
               eligible_price - rule.amount_eur,
               "On/after the effective date, the grant brings the principal within the line."),
        Prefab("overcap", "Over-cap BEV — control", "BEV", rule.price_cap_eur + 8000,
               rule.price_cap_eur + 4000,
               "BEV above the price cap: no grant applies, correctly rejected under both prompts."),
        Prefab("phev", "PHEV — control", "PHEV", 42000, 38000,
               "Not a BEV: no grant, correctly rejected under both prompts."),
        Prefab("approvable", "Comfortably approvable", "BEV", min(30000, rule.price_cap_eur), 40000,
               "Financed amount already under the line: approved under both prompts."),
        Prefab("rejected", "Clearly over the line", "BEV", rejected_price,
               rejected_price - rule.amount_eur - 9000,
               "Even with the grant the principal exceeds the line: rejected under both prompts."),
    ]
