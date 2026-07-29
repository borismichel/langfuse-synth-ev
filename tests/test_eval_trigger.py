"""The playground's presenter-triggered evaluator runs (#180).

Two things are under test, and they pull in opposite directions on purpose:

* the **trigger** must be recessive — collapsed, muted, at the very bottom, invisible to a
  prospect reading the loan application (the acceptance criterion Boris wrote as
  "tucked away, not on-the-nose");
* the **result** must be full-size and in-scene — verdict, counts, Langfuse deep link — with
  failures landing in the ordinary in-scene error card rather than a raw 500.

The route is exercised against a stubbed ``run_experiment`` so no model call, no Langfuse
connection, and no key is needed: what is verified here is the wiring and the rendering, not
the experiment itself (that arithmetic is ``test_experiment_outcome.py``).
"""
from __future__ import annotations

import pytest

from synth.experiment.outcome import ExperimentOutcome
from synth.live import app as evapp
from synth.live import evalpanel

DATASET = "ev-grant-disputed-rejections"


# ---------------------------------------------------------------------------
# The trigger: recessive by construction
# ---------------------------------------------------------------------------
def test_trigger_offers_both_labelled_runs(monkeypatch):
    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    panel = evalpanel.trigger_panel(DATASET, 24)
    assert panel.count('action="/eval"') == 2
    assert 'value="production"' in panel and 'value="development"' in panel
    assert "Run eval · production" in panel and "Run eval · development" in panel


def test_trigger_is_collapsed_and_muted():
    """The acceptance criterion, asserted structurally: a ``<details>`` with no ``open``
    attribute (collapsed), and no accent token anywhere in its styling."""
    panel = evalpanel.trigger_panel(DATASET, 24)
    assert '<details class="pnl">' in panel
    assert "<details open" not in panel
    assert "--cta-primary" not in panel and "--active-tint" not in panel
    assert "var(--text-disabled)" in panel  # the muted summary colour
    assert "background:transparent" in panel  # buttons opt out of the lime CTA


def test_trigger_sits_at_the_very_bottom_of_the_index(monkeypatch, tmp_path):
    """Below the application form *and* below the staff link — the last thing on the page."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from synth.config import load_config

    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path))  # no state: count simply omitted
    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    text = TestClient(evapp.create_app(load_config("config/demo.yaml"))).get("/").text
    assert text.index('class="pnl"') > text.index("staff · lending analytics")
    assert text.index('class="pnl"') > text.index('action="/submit"')


def test_trigger_shows_the_dataset_size_when_state_has_it():
    """"Show the dataset item count on or near the buttons so the presenter knows the size
    of what they're about to run"."""
    assert "· 24 items" in evalpanel.trigger_panel(DATASET, 24)
    assert DATASET in evalpanel.trigger_panel(DATASET, 24)


def test_trigger_omits_the_count_when_state_is_unreadable():
    """Outside a seeded deployment there is no run state — the panel degrades to no count
    rather than rendering a wrong or empty one."""
    panel = evalpanel.trigger_panel(DATASET, None)
    assert "items" not in panel
    assert 'action="/eval"' in panel


def test_trigger_respects_live_base_path(monkeypatch):
    monkeypatch.setenv("LIVE_BASE_PATH", "/live/x")
    panel = evalpanel.trigger_panel(DATASET, 24)
    assert panel.count('action="/live/x/eval"') == 2
    assert 'action="/eval"' not in panel


def test_index_item_count_survives_a_broken_state_file(monkeypatch, tmp_path):
    """A cosmetic count must never take the page down."""
    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path))
    (tmp_path / ".synth_state.json").write_text("{not json")
    assert evapp._dataset_item_count() is None


# ---------------------------------------------------------------------------
# The result: full-size, in-scene
# ---------------------------------------------------------------------------
def test_result_card_renders_red_with_counts_and_link(monkeypatch):
    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    card = evalpanel.result_card(
        "production", 1, ExperimentOutcome(total=24, passed=0, failed=24, errored=0),
        dataset_name=DATASET, run_name="ev-grant-production-v1",
        run_url="https://lf.example/project/p1/datasets/d1")
    assert "RED" in card and 'class="verdict reject"' in card
    assert "0 / 24" in card
    assert "production v1" in card
    assert 'href="https://lf.example/project/p1/datasets/d1"' in card
    assert 'href="/"' in card


def test_result_card_renders_green():
    card = evalpanel.result_card(
        "development", 2, ExperimentOutcome(total=24, passed=24, failed=0, errored=0),
        dataset_name=DATASET, run_name="ev-grant-development-v2", run_url=None)
    assert "GREEN" in card and 'class="verdict approve"' in card
    assert "24 / 24" in card
    assert "Compare in Langfuse" not in card  # no link resolved → the row is dropped


def test_result_card_surfaces_unusable_decisions():
    card = evalpanel.result_card(
        "production", 1, ExperimentOutcome(total=24, passed=20, failed=4, errored=4),
        dataset_name=DATASET, run_name="r", run_url=None)
    assert "No usable decision" in card


def test_result_card_never_blames_the_prompt_for_a_hiccup():
    """A mismatch and an error mean opposite things in front of a room. If the only failures
    are items that came back with no usable decision, the card must not say the prompt got
    them wrong — one unparseable reply on the green run would otherwise both flip the climax
    to RED *and* misattribute a transport hiccup to the fix."""
    card = evalpanel.result_card(
        "development", 2, ExperimentOutcome(total=24, passed=23, failed=1, errored=1),
        dataset_name=DATASET, run_name="r", run_url=None)
    assert "not applying the grant" not in card
    assert "no usable decision" in card and "says nothing about the development prompt" in card


def test_result_card_reports_mismatches_and_errors_separately():
    """Both kinds present: the headline counts only the real disagreements, and the errors
    are called out as unjudged rather than folded into the blame."""
    card = evalpanel.result_card(
        "production", 1, ExperimentOutcome(total=24, passed=18, failed=6, errored=2),
        dataset_name=DATASET, run_name="r", run_url=None)
    assert "4 of 24 items disagreed" in card       # 6 failed − 2 errored
    assert "A further 2" in card and "not judged either way" in card


def test_result_card_handles_an_empty_run():
    card = evalpanel.result_card(
        "production", 1, ExperimentOutcome(total=0, passed=0, failed=0, errored=0),
        dataset_name=DATASET, run_name="r", run_url=None)
    assert "RED" in card and "no items at all" in card
    assert "not applying the grant" not in card


# ---------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------
def _client(monkeypatch, tmp_path, stub):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from synth.config import load_config
    from synth.experiment import run as exprun

    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    monkeypatch.setattr(exprun, "run_experiment", stub)
    return TestClient(evapp.create_app(load_config("config/demo.yaml")))


def test_eval_route_runs_the_requested_label_and_renders_the_card(monkeypatch, tmp_path):
    seen = {}

    def stub(cfg, *, label, adapter=None, **kw):
        seen["label"], seen["adapter"] = label, adapter
        return {"label": label, "version": 2, "run_name": f"ev-grant-{label}-v2",
                "run_url": "https://lf.example/runs", "dataset_name": DATASET,
                "outcome": ExperimentOutcome(total=24, passed=24, failed=0, errored=0)}

    resp = _client(monkeypatch, tmp_path, stub).post("/eval", data={"label": "development"})
    assert resp.status_code == 200
    assert seen["label"] == "development"
    assert "GREEN" in resp.text and "24 / 24" in resp.text


def test_eval_route_passes_the_adapter_through(monkeypatch, tmp_path):
    """Live LLM usage must ride the adapter's resolved client — the Surface never resolves a
    key itself (Spec G · D4/D6)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from synth.config import load_config
    from synth.experiment import run as exprun

    seen = {}

    def stub(cfg, *, label, adapter=None, **kw):
        seen["adapter"] = adapter
        return {"label": label, "version": 1, "run_name": "r", "run_url": None,
                "dataset_name": DATASET,
                "outcome": ExperimentOutcome(total=1, passed=0, failed=1, errored=0)}

    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(exprun, "run_experiment", stub)
    sentinel = object()
    TestClient(evapp.create_app(load_config("config/demo.yaml"), sentinel)).post("/eval")
    assert seen["adapter"] is sentinel


def test_eval_route_defaults_to_production(monkeypatch, tmp_path):
    seen = {}

    def stub(cfg, *, label, adapter=None, **kw):
        seen["label"] = label
        return {"label": label, "version": 1, "run_name": "r", "run_url": None,
                "dataset_name": DATASET,
                "outcome": ExperimentOutcome(total=24, passed=0, failed=24, errored=0)}

    resp = _client(monkeypatch, tmp_path, stub).post("/eval")
    assert seen["label"] == "production"
    assert "RED" in resp.text


def test_eval_route_renders_the_in_scene_error_card_never_a_500(monkeypatch, tmp_path):
    """Missing keys outside a deployment must degrade like the submit path does."""
    def stub(cfg, *, label, adapter=None, **kw):
        raise RuntimeError("LLM_API_KEY is not set")

    resp = _client(monkeypatch, tmp_path, stub).post("/eval", data={"label": "production"})
    assert resp.status_code == 200
    assert "We couldn't run the evaluation" in resp.text
    assert "LLM_API_KEY is not set" in resp.text


def test_eval_route_rejects_an_unknown_label(monkeypatch, tmp_path):
    """Only the two labelled runs the panel offers — an arbitrary label never reaches the
    experiment (and so never spends)."""
    def stub(cfg, *, label, adapter=None, **kw):  # pragma: no cover — must not be called
        raise AssertionError("unknown label reached the experiment")

    resp = _client(monkeypatch, tmp_path, stub).post("/eval", data={"label": "staging"})
    assert resp.status_code == 200
    assert "isn't available" in resp.text
