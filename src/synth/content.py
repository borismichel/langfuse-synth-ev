"""Content pool (spec §4, §7): templated applications + step I/O.

For most traces this is set dressing. For the golden-path window it must be
*semantically real and judge-evaluable* — eligible borderline BEVs that v1 wrongly
rejects on gross price, plus correct-rejection controls. Generators below encode the
arithmetic from spec §17 so the cases produce the demo:

- ``eligible_borderline``: BEV <= cap, line in [list-grant, list-1]  -> v1 reject, v2 approve
- ``control_overcap``    : BEV > cap, line < list                    -> reject under both (no grant)
- ``control_phev``       : PHEV,      line < list                    -> reject under both (no grant)
"""
from __future__ import annotations

from datetime import datetime

from .agent import GrantRule
from .models import Application, Vehicle
from .rng import Rng

# Plausible model names per drivetrain, for set dressing in trace I/O.
_BEV_MODELS = ["Aurora e-300", "Volt EX", "Lumen EV", "Nordic e-Sedan", "Pulse 40", "Helix BEV"]
_PHEV_MODELS = ["Aurora PHEV", "Volt Hybrid", "Meridian e-Plus", "Nordic Hybrid"]
_ICE_MODELS = ["Aurora 2.0T", "Meridian GT", "Nordic Sedan", "Continental 3.0"]

_EXPLAIN_APPROVE = [
    "Good news — your auto loan is approved. The financed amount fits within your pre-approved line.",
    "Your application is approved. We were able to finance the vehicle within your existing credit line.",
]
_EXPLAIN_REJECT = [
    "We're unable to approve this application: the amount to finance exceeds your pre-approved credit line.",
    "Unfortunately we can't approve this loan as requested — the financed amount is above your approved line.",
]


def applicant_id(rng: Rng, n: int) -> str:
    return f"anon_{n:04d}"


def user_population(rng: Rng, n_users: int, power_share: float) -> list[dict]:
    """Synthetic users; a few loan-officer power users get outsized weight (Zipf-ish)."""
    rsub = rng.sub("users")
    n_power = max(1, int(n_users * power_share))
    users = []
    for i in range(n_users):
        is_power = i < n_power
        users.append(
            {
                "userId": f"officer_{i:03d}" if is_power else f"applicant_user_{i:03d}",
                "weight": rsub.uniform(6, 12) if is_power else rsub.uniform(0.5, 1.5),
                "is_power": is_power,
            }
        )
    return users


# ---------------------------------------------------------------------------
# Application generators
# ---------------------------------------------------------------------------
def ambient_application(rng: Rng, n: int, date: str) -> tuple[Application, str]:
    """A healthy-baseline application. Returns (application, expected_v1_decision_kind)."""
    vtype = rng.choices(["BEV", "PHEV", "ICE"], [0.4, 0.25, 0.35], k=1)[0]
    list_price = int(rng.uniform(22000, 60000) // 500 * 500)
    # Mostly comfortably-approvable to look like a healthy book of business.
    if rng.chance(0.78):
        line = list_price + int(rng.uniform(2000, 20000))
    else:
        line = list_price - int(rng.uniform(3000, 15000))
    app = Application(
        applicant_id=applicant_id(rng, n),
        approved_line_eur=max(8000, line),
        vehicle=Vehicle(type=vtype, list_price_eur=list_price),
        application_date=date,
    )
    return app, model_label(rng, vtype)


def eligible_borderline_application(rng: Rng, n: int, date: str, rule: GrantRule) -> Application:
    """BEV under the cap where gross > line but (gross - grant) <= line: the false negative."""
    list_price = int(rng.uniform(36000, min(48000, rule.price_cap_eur - 1000)) // 500 * 500)
    # line in [list - grant, list - 500]: v1 rejects (gross), v2 approves (post-grant)
    low = list_price - rule.amount_eur
    high = list_price - 500
    line = int(rng.uniform(low, high) // 500 * 500)
    line = max(low, min(line, high))
    return Application(
        applicant_id=applicant_id(rng, n),
        approved_line_eur=line,
        vehicle=Vehicle(type="BEV", list_price_eur=list_price),
        application_date=date,
    )


def control_overcap_application(rng: Rng, n: int, date: str, rule: GrantRule) -> Application:
    """BEV above the price cap: correctly rejected under both prompts (no grant applies)."""
    list_price = int(rng.uniform(rule.price_cap_eur + 2000, rule.price_cap_eur + 14000) // 500 * 500)
    line = list_price - int(rng.uniform(2000, 8000))
    return Application(
        applicant_id=applicant_id(rng, n),
        approved_line_eur=line,
        vehicle=Vehicle(type="BEV", list_price_eur=list_price),
        application_date=date,
    )


def control_phev_application(rng: Rng, n: int, date: str, rule: GrantRule) -> Application:
    """PHEV (not BEV): no grant, correctly rejected under both prompts."""
    list_price = int(rng.uniform(36000, 46000) // 500 * 500)
    line = list_price - int(rng.uniform(1500, 6000))
    return Application(
        applicant_id=applicant_id(rng, n),
        approved_line_eur=line,
        vehicle=Vehicle(type="PHEV", list_price_eur=list_price),
        application_date=date,
    )


def model_label(rng: Rng, vtype: str) -> str:
    pool = {"BEV": _BEV_MODELS, "PHEV": _PHEV_MODELS, "ICE": _ICE_MODELS}[vtype]
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# Step I/O (set dressing for the observation tree)
# ---------------------------------------------------------------------------
def plan_io(app: Application) -> tuple[str, str]:
    return (
        f"Assess auto-loan application for {app.applicant_id}: {app.vehicle.type} at "
        f"EUR {app.vehicle.list_price_eur:,}, approved line EUR {app.approved_line_eur:,}.",
        "Plan: normalize fields, retrieve current credit policy, check subsidy eligibility, "
        "compute affordability, then decide and explain.",
    )


def extract_io(app: Application) -> tuple[dict, dict]:
    return (
        {"raw_application": f"{app.vehicle.type} {app.vehicle.list_price_eur} line {app.approved_line_eur}"},
        app.model_dump(),
    )


def retrieve_io() -> tuple[str, list[str]]:
    return (
        "credit policy: auto-loan affordability rules",
        ["policy:affordability-v3", "policy:dti-thresholds", "policy:vehicle-classes"],
    )


def explain_io(rng: Rng, approved: bool) -> tuple[str, str]:
    txt = rng.choice(_EXPLAIN_APPROVE if approved else _EXPLAIN_REJECT)
    return ("Draft a one-paragraph customer-facing rationale.", txt)
