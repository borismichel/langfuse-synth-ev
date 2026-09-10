"""Deployment policy facts agree at the managed-prompt and presenter boundaries (#233)."""
from datetime import datetime, timezone
from types import SimpleNamespace

from synth.config import load_config
from synth.seed.prompts import register_prompts


class PromptStore:
    def __init__(self):
        self.created = []

    def get_prompt(self, *args, **kwargs):
        raise LookupError("no prompt yet")

    def create_prompt(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(version=len(self.created))


def test_registered_prompt_bakes_all_deployment_policy_facts():
    cfg = load_config("config/demo.yaml", overrides=[
        "golden_path.grant_amount_eur=4000", "golden_path.price_cap_eur=45000"])
    store = PromptStore()
    register_prompts(store, cfg, datetime(2026, 6, 2, tzinfo=timezone.utc))
    fixed = store.created[1]["prompt"]
    system = fixed[0]["content"]
    assert "EUR 4,000" in system and "45000" in system and "EUR 45,000" in system
    assert "on/after 2026-06-02" in system
    assert "before the effective date" in system
    assert "50,000" not in system and "6,000" not in system and "{{" not in system
    assert fixed[1] == {"role": "user", "content": "{{application}}"}


def test_presenter_uses_saved_policy_and_labels_execution_truthfully(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from synth.live.app import create_app
    from synth.script import render_script
    from synth.seed.run import run_seed

    cfg = load_config("config/demo.yaml", overrides=[
        "generation.target_traces=120", "generation.as_of_date=2026-06-09",
        "golden_path.grant_amount_eur=4000", "golden_path.price_cap_eur=45000"])
    monkeypatch.setenv("SYNTH_STATE_DIR", str(tmp_path / "state"))
    state = run_seed(cfg, dry_run=True, persist=False, do_import=False,
                     spool_path=tmp_path / "events.ndjson", log=lambda _: None)
    state.save()
    # Even if runtime defaults change, the seeded deployment remains the reference.
    runtime_cfg = load_config("config/demo.yaml", overrides=["generation.target_traces=120"])
    client = TestClient(create_app(runtime_cfg))
    text = client.get("/").text
    assert "at or below €45,000" in text and "€4,000 EV purchase grant" in text
    assert "on or after 2026-06-02" in text
    assert 'id="line" type="number" value="34000"' in text
    assert 'data-p="53000"' in text
    assert "€50,000" not in text and "€6,000" not in text
    assert "decision prompt" in text and "simulated" in text
    analytics = client.get("/analytics").text
    assert "historical snapshot" in analytics and "of reviewed decisions" in analytics
    assert "€45,000" in analytics and "€50,000" not in analytics
    runbook = render_script(cfg, state, out_path=tmp_path / "DEMO_SCRIPT.md").read_text()
    assert "model-free" in runbook and "representative simulated" in runbook
    assert "decision prompt" in runbook and "reviewed decisions" in runbook
    assert "nudges the appeal rate" not in runbook and "returns *no subsidy*" not in runbook
