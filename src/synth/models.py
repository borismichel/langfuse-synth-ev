"""Data contracts (spec §16): the application input and the agent's structured Decision.

The judge adjudicates these *structured fields*, not free prose — pinning the shapes
is what makes the demo's red->green flip reliable.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

VehicleType = Literal["BEV", "PHEV", "ICE"]
DecisionType = Literal["approve", "reject"]


class Vehicle(BaseModel):
    type: VehicleType
    list_price_eur: int


class Application(BaseModel):
    """The dataset-item ``input`` (spec §16)."""

    applicant_id: str
    approved_line_eur: int
    vehicle: Vehicle
    application_date: str  # ISO date (YYYY-MM-DD)

    @classmethod
    def from_input(cls, data: "Application | dict") -> "Application":
        """Coerce whatever ``run_experiment`` hands the task back into an Application."""
        if isinstance(data, Application):
            return data
        return cls.model_validate(data)


class Decision(BaseModel):
    """What ``decide()`` returns and what seeded ``decision`` generations emit (spec §16)."""

    decision: DecisionType
    list_price_eur: int
    applied_grant_eur: int
    financed_principal_eur: int
    approved_line_eur: int
    reason: str
