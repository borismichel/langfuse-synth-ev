"""Spool-count exposure for the EV kit (#35).

Two things this locks:

* the lib-side ``count_spool`` measures the **Step 0 golden** (``tests/golden/ev_spool.ndjson``)
  exactly, cross-checked against the snapshot's own tallies — the trace count equals the
  pinned ``target_traces`` volume, and an independent recount agrees type-for-type; and
* the kit exposes it to the portal the same way ``import-spool`` is exposed — a ``synth``
  console verb — printing the measured count as JSON with no new plumbing shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from langfuse_synth_core.seed.count import count_spool
from synth.cli import app

# The Step 0 oracle and its declared volume (kept in lockstep with test_determinism.py).
GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "ev_spool.ndjson"
GOLDEN_TARGET_TRACES = 300
# The snapshot's own billable tallies, frozen alongside the byte-identical oracle (a
# deliberate re-bless of ev_spool.ndjson updates both). EV maps target_traces 1:1 to traces.
GOLDEN_TALLIES = {"traces": 300, "observations": 2562, "scores": 483}

# Independent (whitelist duplicated here on purpose) recount, a different code path than
# the library's, so agreement is a real cross-check rather than a tautology.
_OBSERVATION_TYPES = {"span-create", "generation-create", "event-create", "observation-create"}


def _independent_tally(path: Path) -> dict[str, int]:
    counts = {"traces": 0, "observations": 0, "scores": 0}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        etype = json.loads(line)["type"]
        if etype == "trace-create":
            counts["traces"] += 1
        elif etype in _OBSERVATION_TYPES:
            counts["observations"] += 1
        elif etype == "score-create":
            counts["scores"] += 1
    return counts


def test_count_spool_matches_golden_step0_tallies():
    counts = count_spool(GOLDEN_PATH)
    # The snapshot's own declared tally: EV maps target_traces 1:1 to traces (direct count).
    assert counts["traces"] == GOLDEN_TARGET_TRACES
    # Anchor to the snapshot's own recorded tallies, and cross-check that against an
    # independent recount of the same bytes.
    assert counts == GOLDEN_TALLIES
    assert counts == _independent_tally(GOLDEN_PATH)


def test_count_spool_cli_verb_prints_json(tmp_path: Path):
    """`synth count-spool <spool>` — exposed exactly like `synth import-spool`."""
    spool = tmp_path / "events.ndjson"
    spool.write_text(
        '{"type":"trace-create","id":"t"}\n'
        '{"type":"generation-create","id":"o"}\n'
        '{"type":"score-create","id":"s"}\n'
        '{"type":"dataset-item-create","id":"d"}\n',  # excluded
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["count-spool", str(spool)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"traces": 1, "observations": 1, "scores": 1}
