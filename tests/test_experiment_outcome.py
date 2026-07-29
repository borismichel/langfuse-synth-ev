"""The in-scene red/green verdict (#180).

The playground's eval buttons render an outcome *in the scene*, and they render it before
the managed UI judge necessarily exists (the runbook builds that judge in beat 3). So the
verdict is arithmetic over the dataset's own ``expected_output`` versus what the labelled
prompt actually decided — which is precisely the contrast the demo turns on: ``production``
(v1, no grant applied) misses every eligible false negative → RED; ``development`` (v2, the
fix) matches → GREEN.

Pure and offline: these fakes stand in for the SDK's ``ExperimentItemResult``, which carries
a ``.item`` (dict *or* Langfuse ``DatasetItem``) and a ``.output``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synth.experiment.outcome import ExperimentOutcome, summarize


@dataclass
class _DatasetItem:
    """Attribute-style item — what a hosted Langfuse dataset yields."""

    expected_output: Any


@dataclass
class _ItemResult:
    item: Any
    output: Any


def _res(expected: str | None, got: str | None, *, dict_item: bool = False) -> _ItemResult:
    item = {"expected_output": {"decision": expected}} if dict_item else _DatasetItem({"decision": expected})
    return _ItemResult(item=item, output=None if got is None else {"decision": got})


def test_all_matching_is_green():
    out = summarize([_res("approve", "approve"), _res("reject", "reject")])
    assert (out.total, out.passed, out.failed, out.errored) == (2, 2, 0, 0)
    assert out.green is True
    assert out.verdict == "GREEN"


def test_any_mismatch_is_red():
    """One wrong decision is enough — the demo's red run is *every* item wrong, but the
    gate is "not perfect", not "mostly wrong"."""
    out = summarize([_res("approve", "reject"), _res("reject", "reject")])
    assert (out.total, out.passed, out.failed, out.errored) == (2, 1, 1, 0)
    assert out.green is False
    assert out.verdict == "RED"


def test_production_style_run_all_rejected_is_red():
    """The v1 shape: every eligible false negative expected ``approve``, all came back
    ``reject``."""
    out = summarize([_res("approve", "reject") for _ in range(6)])
    assert (out.passed, out.failed) == (0, 6)
    assert out.verdict == "RED"


def test_dict_items_are_read_like_dataset_items():
    """The SDK hands back either shape; both must summarise identically."""
    attr = summarize([_res("approve", "approve"), _res("reject", "approve")])
    dicts = summarize([_res("approve", "approve", dict_item=True),
                       _res("reject", "approve", dict_item=True)])
    assert attr == dicts


def test_item_without_a_usable_decision_counts_as_errored_and_failed():
    """A task that blew up (no output) or an item with no expectation can never be a pass —
    it is counted as failed *and* surfaced separately so the card can say so."""
    out = summarize([_res("approve", "approve"), _res("approve", None), _res(None, "approve")])
    assert (out.total, out.passed, out.failed, out.errored) == (3, 1, 2, 2)
    assert out.mismatched == 0  # nothing here is the prompt's fault
    assert out.verdict == "RED"


def test_mismatches_are_countable_apart_from_errors():
    """The card blames the prompt only for real disagreements, so the two kinds of failure
    have to stay separable."""
    out = summarize([_res("approve", "reject"), _res("approve", None), _res("reject", "reject")])
    assert (out.failed, out.errored, out.mismatched) == (2, 1, 1)


def test_empty_run_is_red_not_green():
    """Zero items is a broken run, not a perfect one — never let it render GREEN."""
    out = summarize([])
    assert out == ExperimentOutcome(total=0, passed=0, failed=0, errored=0)
    assert out.green is False
