"""The §17 truth table: the exact rules that produce the demo."""
from synth.agent import GrantRule, decide
from synth.models import Application, Vehicle

RULE = GrantRule(amount_eur=6000, price_cap_eur=50000, effective_date="2026-06-02")


def _app(vtype, price, line, date="2026-06-05"):
    return Application(applicant_id="anon_0001", approved_line_eur=line,
                       vehicle=Vehicle(type=vtype, list_price_eur=price), application_date=date)


def test_eligible_borderline_is_the_false_negative():
    app = _app("BEV", 42000, 40000)
    v1 = decide(app, "v1", rule=RULE)
    v2 = decide(app, "v2", rule=RULE)
    assert v1.decision == "reject" and v1.applied_grant_eur == 0
    assert v1.financed_principal_eur == 42000
    assert v2.decision == "approve" and v2.applied_grant_eur == 6000
    assert v2.financed_principal_eur == 36000


def test_over_cap_bev_is_a_control():
    app = _app("BEV", 58000, 55000)
    assert decide(app, "v1", rule=RULE).decision == "reject"
    v2 = decide(app, "v2", rule=RULE)
    assert v2.decision == "reject" and v2.applied_grant_eur == 0  # over cap -> no grant


def test_phev_is_a_control():
    app = _app("PHEV", 42000, 40000)
    assert decide(app, "v1", rule=RULE).decision == "reject"
    v2 = decide(app, "v2", rule=RULE)
    assert v2.decision == "reject" and v2.applied_grant_eur == 0  # not BEV -> no grant


def test_grant_not_applied_before_effective_date():
    before = _app("BEV", 42000, 40000, date="2026-05-01")  # before effective
    v2 = decide(before, "v2", rule=RULE)
    assert v2.applied_grant_eur == 0 and v2.decision == "reject"


def test_decision_is_deterministic():
    app = _app("BEV", 42000, 40000)
    assert decide(app, "v2", rule=RULE) == decide(app, "v2", rule=RULE)


def test_dict_input_coerces():
    d = {"applicant_id": "anon_x", "approved_line_eur": 40000,
         "vehicle": {"type": "BEV", "list_price_eur": 42000}, "application_date": "2026-06-05"}
    assert decide(d, "v2", rule=RULE).decision == "approve"
