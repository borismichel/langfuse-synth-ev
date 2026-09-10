"""Presenter delivery uses saved seed anchors and stays honest about missing resources."""
import json
from datetime import datetime, timezone

from synth.config import load_config
from synth.script import render_script
from synth.seed.generator import build_plan
from synth.seed.run import _build_state, run_seed
from synth.state import RunState


def test_runbook_keeps_uploaded_counts_policy_and_curation_when_config_changes(tmp_path):
    cfg = load_config('config/demo.yaml', overrides=[
        'generation.target_traces=100', 'generation.window_days=14',
        'golden_path.grant_amount_eur=4000', 'golden_path.price_cap_eur=45000',
        'golden_path.dataset.name=custom-regression',
        'ambient_incidents.cost_spike.enabled=false',
        'ambient_incidents.error_burst.enabled=false',
    ])
    plan = build_plan(cfg, datetime(2026, 6, 9, tzinfo=timezone.utc))
    state = _build_state(cfg, plan, {'v1': 8, 'v2': 11}, 'custom-demo', {
        'demo_name': 'custom-regression-demo', 'demo_id': 'returned-dataset-id',
        'demo_items_created': 11,
    }, False)
    state.project_id = 'returned-project-id'
    # Re-rendering uses seed anchors even if runtime configuration has drifted.
    text = render_script(load_config('config/demo.yaml'), state,
                         out_path=tmp_path / 'DEMO_SCRIPT.md').read_text()
    assert 'across 14 days' in text and 'across 30 days' not in text
    assert '€4,000' in text and '€45,000' in text and '2026-06-02' in text
    assert 'custom-regression-demo' in text and '11 authored' in text and '12 after' in text
    assert '/datasets/returned-dataset-id/items' in text
    assert 'Baseline **v8**' in text and 'candidate **v11**' in text
    assert 'all ambient incident cohorts were disabled' in text
    application = json.loads(state.reserved_item['input']['application'])
    expected = state.reserved_item['expected_output']
    assert expected['financed_principal_eur'] == application['vehicle']['list_price_eur'] - 4000
    assert state.reserved_item['source_trace_id'] == state.reserved_example['trace_id']
    state.history_imported = False
    pending = render_script(cfg, state, out_path=tmp_path / 'pending.md').read_text()
    assert 'without importing it' in pending
    assert '/traces/' not in pending
    assert '/datasets/returned-dataset-id/items' in pending


def test_older_empty_state_and_dry_run_have_setup_instead_of_invented_links(tmp_path):
    cfg = load_config('config/demo.yaml', overrides=[
        'generation.target_traces=100', 'golden_path.enabled=false',
        'generation.as_of_date=2026-06-09',
    ])
    state = run_seed(cfg, dry_run=True, persist=False,
                     spool_path=tmp_path / 'events.ndjson', log=lambda _: None)
    # Simulate a saved run from before presenter anchors were introduced.
    raw = state.__dict__.copy()
    for key in ('history_window_days', 'history_imported', 'demo_dataset_name', 'demo_dataset_id',
                'demo_dataset_items', 'reserved_item', 'ambient_incidents', 'dataset_id'):
        raw.pop(key)
    raw.update(project_id='unverified-project')
    older = RunState(**raw)
    text = render_script(cfg, older, out_path=tmp_path / 'DEMO_SCRIPT.md').read_text()
    assert '/project/unverified-project' not in text
    assert 'Preview only' in text
    assert 'No disputed example recorded' in text
    assert 'No reserved curation payload recorded' in text
    assert 'No rejection control recorded' in text
    assert 'Short comparison not recorded' in text
    assert 'Baseline version not verified' in text
    assert 'incident settings were not saved' in text
    assert 'across 30 days' not in text


def test_seed_delivers_declared_presenter_artifacts_without_model_calls(tmp_path, monkeypatch):
    import yaml
    import synth.seed.run as seed

    monkeypatch.setenv('SYNTH_OUT_DIR', str(tmp_path / 'out'))
    monkeypatch.setenv('SYNTH_STATE_DIR', str(tmp_path / 'state'))
    monkeypatch.setattr(seed, 'FIXTURES_DIR', tmp_path / 'fixtures')
    cfg = load_config('config/demo.yaml', overrides=[
        'generation.target_traces=100', 'generation.as_of_date=2026-06-09',
    ])
    state = seed.run_seed(cfg, dry_run=True, spool_path=tmp_path / 'events.ndjson',
                          log=lambda _: None)
    runbook = render_script(cfg, state)
    from pathlib import Path
    manifest = yaml.safe_load(Path('usecase.yaml').read_text())
    assert manifest['artifacts'][0] == {
        'path': 'DEMO_SCRIPT.md', 'render': 'markdown', 'title': 'Presenter Runbook',
    }
    for artifact in manifest['artifacts']:
        assert (runbook.parent / artifact['path']).is_file(), artifact['path']
    assert RunState.load().reserved_item == state.reserved_item
    assert state.reserved_item.get('source_observation_id')
