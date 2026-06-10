"""Five ready-made applications for the playground (plus free-form custom entry).

Each prefab sets a default ``approved_line_eur`` that the UI lets the submitter edit —
nudging the eligible case across the grant margin is the most instructive knob.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Application, Vehicle


@dataclass(frozen=True)
class Prefab:
    key: str
    label: str
    vehicle_type: str           # BEV | PHEV | ICE
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


# Tuned against the default rule (grant €6,000, cap €50,000).
PREFABS: list[Prefab] = [
    Prefab("eligible", "Eligible BEV (borderline) — the bug", "BEV", 38000, 32000,
           "BEV ≤ cap where the €6k grant brings the principal under the line: v1 rejects, v2 approves."),
    Prefab("overcap", "Over-cap BEV — control", "BEV", 58000, 54000,
           "BEV above the price cap: no grant applies, correctly rejected under both prompts."),
    Prefab("phev", "PHEV — control", "PHEV", 42000, 38000,
           "Not a BEV: no grant, correctly rejected under both prompts."),
    Prefab("approvable", "Comfortably approvable", "BEV", 30000, 40000,
           "Financed amount already under the line: approved under both prompts."),
    Prefab("rejected", "Clearly over the line", "BEV", 45000, 30000,
           "Even with the €6k grant the principal exceeds the line: rejected under both prompts."),
]
PREFABS_BY_KEY: dict[str, Prefab] = {p.key: p for p in PREFABS}
