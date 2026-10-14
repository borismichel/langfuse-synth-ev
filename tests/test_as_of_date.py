"""The operator's as-of date reaches the seed (portal #229).

The portal has sent ``--set generation.as_of_date=YYYY-MM-DD`` on every forward generate
since #72; until #229 this kit's config model silently dropped it, so the third leg of the
determinism law (``seed + target_traces + as-of → byte-identical Spool``) was a lie. These
pin the knob end to end through the REAL operator path: the ``--set`` override, the
pydantic model, and ``run_seed``'s default run anchor.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from synth.config import load_config
from synth.seed.run import run_seed
from synth.state import REPO_ROOT

CONFIG = str(REPO_ROOT / "config" / "demo.yaml")
SMALL = "generation.target_traces=120"


def _seed(tmp_path: Path, *overrides: str):
    cfg = load_config(CONFIG, overrides=[SMALL, *overrides])
    return run_seed(cfg, dry_run=True, persist=False, do_import=False,
                    spool_path=tmp_path / "events.ndjson", log=lambda _m: None)


def test_the_override_lands_on_the_config_as_a_date():
    cfg = load_config(CONFIG, overrides=["generation.as_of_date=2026-09-04"])
    assert cfg.generation.as_of_date == date(2026, 9, 4)


def test_absent_means_no_tether():
    assert load_config(CONFIG).generation.as_of_date is None


def test_seed_anchors_the_window_on_the_as_of_date(tmp_path):
    state = _seed(tmp_path, "generation.as_of_date=2026-09-04")
    assert state.run_date == "2026-09-04T12:00:00+00:00"
    assert state.summary["run_date"] == "2026-09-04T12:00:00+00:00"


def test_a_future_as_of_date_is_honoured_not_clamped(tmp_path):
    """By design: an AE tethers next week's demo to the meeting. The window simply ends on
    that date — no error, no warning, no clamp to today."""
    fortnight_out = date.today() + timedelta(days=14)
    state = _seed(tmp_path, f"generation.as_of_date={fortnight_out.isoformat()}")
    assert datetime.fromisoformat(state.run_date).date() == fortnight_out


def test_no_as_of_date_seeds_up_to_now(tmp_path):
    before = datetime.now(timezone.utc).replace(microsecond=0)
    state = _seed(tmp_path)
    assert before <= datetime.fromisoformat(state.run_date) <= datetime.now(timezone.utc)


def test_same_three_inputs_give_identical_bytes_regardless_of_the_clock(tmp_path):
    """The determinism law, third leg included: two runs with the same seed, target_traces
    and as-of date produce identical Spool bytes — the wall clock is not an input."""
    a = _seed(tmp_path / "a", "generation.as_of_date=2026-09-04")
    b = _seed(tmp_path / "b", "generation.as_of_date=2026-09-04")
    assert a.run_date == b.run_date
    assert (tmp_path / "a" / "events.ndjson").read_bytes() == \
        (tmp_path / "b" / "events.ndjson").read_bytes()


import json
import pytest


@pytest.mark.parametrize(('as_of', 'window', 'first'), [
    ('2026-10-16', 14, '2026-10-03'),
    ('2026-10-16', 30, '2026-09-17'),
    ('2027-01-02', 14, '2026-12-20'),
    ('2028-03-01', 14, '2028-02-17'),
])
def test_emitted_history_includes_the_selected_final_date(tmp_path, as_of, window, first):
    cfg = load_config(CONFIG, overrides=[
        'generation.target_traces=800', f'generation.as_of_date={as_of}',
        f'generation.window_days={window}',
    ])
    state = run_seed(cfg, dry_run=True, persist=False, do_import=False,
                     spool_path=tmp_path / 'events.ndjson', log=lambda _m: None)
    events = [json.loads(line) for line in (tmp_path / 'events.ndjson').read_text().splitlines()]
    traces = [datetime.fromtimestamp(int(e['startTimeUnixNano']) / 1e9, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') for e in events if 'spanId' in e and not e.get('parentSpanId')]
    assert min(traces)[:10] == first
    assert max(traces)[:10] == as_of
    assert state.summary['generated_range']['start'] == min(traces)
    ends = [datetime.fromtimestamp(int(e['endTimeUnixNano']) / 1e9, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') for e in events if 'spanId' in e]
    assert state.summary['generated_range']['end'] == max(ends)
    assert max(ends)[:10] == as_of
    assert state.summary['schedule']['as_of_date'] == as_of


def test_latest_day_observations_cannot_spill_into_tomorrow(tmp_path):
    # This seed samples a root at 23:59:59.950527; the unbounded graph ends tomorrow.
    cfg = load_config(CONFIG, overrides=['generation.target_traces=6000',
        'generation.seed=60', 'generation.window_days=14', 'generation.as_of_date=2026-10-16'])
    run_seed(cfg, dry_run=True, persist=False, do_import=False,
             spool_path=tmp_path / 'events.ndjson', log=lambda _m: None)
    events = [json.loads(line) for line in (tmp_path / 'events.ndjson').read_text().splitlines()]
    spans = [event for event in events if 'spanId' in event]
    assert max(int(event['endTimeUnixNano']) for event in spans) < 1792195200000000000
    assert all(int(event['startTimeUnixNano']) <= int(event['endTimeUnixNano']) for event in spans)
    last = max(spans, key=lambda event: int(event['endTimeUnixNano']))
    graph = [event for event in spans if event['traceId'] == last['traceId']]
    assert max(int(event['endTimeUnixNano']) for event in graph) - min(int(event['startTimeUnixNano']) for event in graph) == 3_688_000_000


@pytest.mark.parametrize('as_of', ['2026-10-16', '2026-10-17', '2026-10-18'])
@pytest.mark.parametrize('window', [14, 30])
@pytest.mark.parametrize('seed', [0, 10, 42])
def test_sparse_history_contains_selected_day_activity(tmp_path, as_of, window, seed):
    # Sunday / 30 days / seed 10 previously ended on October 17 despite selecting 18.
    cfg = load_config(CONFIG, overrides=[
        'generation.target_traces=100', f'generation.seed={seed}',
        f'generation.window_days={window}', f'generation.as_of_date={as_of}',
    ])
    state = run_seed(cfg, dry_run=True, persist=False, do_import=False,
                     spool_path=tmp_path / 'events.ndjson', log=lambda _m: None)
    events = [json.loads(line) for line in (tmp_path / 'events.ndjson').read_text().splitlines()]
    spans = [event for event in events if 'spanId' in event]
    roots = [event for event in spans if not event.get('parentSpanId')]
    selected_day = date.fromisoformat(as_of)
    assert len(roots) == 100
    assert max(datetime.fromtimestamp(int(event['startTimeUnixNano']) / 1e9, timezone.utc).date()
               for event in roots) == selected_day
    assert min(datetime.fromtimestamp(int(event['startTimeUnixNano']) / 1e9, timezone.utc).date()
               for event in spans) >= selected_day - timedelta(days=window - 1)
    assert max(datetime.fromtimestamp(int(event['endTimeUnixNano']) / 1e9, timezone.utc).date()
               for event in spans) == selected_day
    assert all(int(event['startTimeUnixNano']) <= int(event['endTimeUnixNano']) for event in spans)
    assert state.summary['generated_range']['end'].startswith(f'{as_of}T')
    assert state.dataset_items == 24
    assert len(state.reserved_trace_ids) == 3
