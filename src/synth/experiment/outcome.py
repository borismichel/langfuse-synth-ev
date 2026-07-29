"""Red/green arithmetic over an experiment's item results — the in-scene verdict (#180).

The playground's presenter-triggered eval runs (``POST /eval``) render their outcome in the
scene, and they render it *before the managed UI judge necessarily exists* — the runbook has
the presenter build that judge in beat 3, and the buttons work from the moment the kit is
deployed. So the card's verdict cannot come from the judge. It comes from the dataset's own
``expected_output`` compared against what the labelled prompt actually decided, which is
exactly the contrast the demo turns on: ``production`` (v1, the stale grant window) misses
every eligible false negative → RED; ``development`` (v2, the fix) matches → GREEN.

This is deliberately the same comparison ``pass_rate_offline`` makes for the CI gate, but
over the *live* run's real outputs rather than replayed arithmetic.

Pure: no network, no SDK types, no config — just the already-collected results. That keeps
it testable offline and keeps the route in ``live/app.py`` a thin call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ExperimentOutcome:
    """Counts over one experiment run. ``errored`` is a *subset* of ``failed``: items whose
    task produced no usable decision, or which carry no expectation to check against."""

    total: int
    passed: int
    failed: int
    errored: int

    @property
    def green(self) -> bool:
        """Green only on a clean sweep. An empty run is a broken run, never a pass."""
        return self.total > 0 and self.failed == 0

    @property
    def verdict(self) -> str:
        return "GREEN" if self.green else "RED"


def _decision(payload: Any) -> str | None:
    """The ``decision`` field out of a task output / expected output, or None if there
    isn't one (task raised, model returned something unparseable, item has no expectation)."""
    if isinstance(payload, dict):
        value = payload.get("decision")
        return value if isinstance(value, str) else None
    return None


def _expected_of(item: Any) -> Any:
    """``expected_output`` off either shape the SDK yields: a hosted Langfuse ``DatasetItem``
    (attribute) or a local experiment item (dict key)."""
    if isinstance(item, dict):
        return item.get("expected_output")
    return getattr(item, "expected_output", None)


def summarize(item_results: Iterable[Any]) -> ExperimentOutcome:
    """Count passes/failures across an ``ExperimentResult.item_results`` sequence."""
    total = passed = errored = 0
    for result in item_results:
        total += 1
        got = _decision(getattr(result, "output", None))
        want = _decision(_expected_of(getattr(result, "item", None)))
        if got is None or want is None:
            errored += 1
        elif got == want:
            passed += 1
    return ExperimentOutcome(total=total, passed=passed, failed=total - passed, errored=errored)
