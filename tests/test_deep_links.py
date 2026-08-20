"""Every Langfuse deep link this kit hands a presenter resolves to a page under v4.

A deep link is a delivery surface: it is clicked in front of a customer, and a 404 there is
caught by no other gate. v4 reorganised the Langfuse UI, so the routes this kit builds are
pinned here (portal #212). This kit has no Links class — its URLs are built inline in three
places — so the test reads the source rather than calling helpers, which also means a new
link added anywhere under `src/` is held to the same set.
"""
from __future__ import annotations

import pathlib
import re

#: Every project-scoped route this kit may link to, as templates with `{}` for an id.
#: Checked against the v4 app's own routing. Notable: `datasets/{id}/runs` has no page —
#: a dataset run is an *experiment* under v4 — and the bare `datasets/{id}` is an alias
#: that redirects to the Items tab.
ROUTES = frozenset({
    "",
    "traces",
    "traces/{}",
    "sessions",
    "scores",
    "dashboards",
    "datasets",
    "datasets/{}/items",
    "datasets/{}/experiments",
    "prompts",
    "prompts/{}",
})

SECTIONS = {"traces", "sessions", "scores", "dashboards", "datasets", "items",
            "experiments", "prompts", "annotation-queues", "evals"}

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

#: Matches the suffix of an f-string project URL: `/project/{...}/<suffix>`. The suffix
#: charset stops at the closing quote, and at the backtick a docstring wraps a route in.
_URL = re.compile(r"/project/\{[^}]+\}/([A-Za-z0-9_{}/-]*)")


def _template(suffix: str) -> str:
    """`datasets/{dataset_id}/experiments` -> `datasets/{}/experiments`."""
    suffix = re.sub(r"\{[^}]*\}", "{}", suffix).rstrip("/")
    return "/".join(p if p in SECTIONS else "{}" for p in suffix.split("/") if p) \
        if suffix else ""


def _links_in_source() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        for suffix in _URL.findall(path.read_text()):
            if re.fullmatch(r"\{[^}]*\}", suffix):
                continue        # a generic helper; its call sites are checked below
            found.setdefault(str(path.relative_to(SRC)), []).append(suffix)
    return found


def test_the_kit_builds_no_link_outside_the_v4_route_set():
    found = _links_in_source()
    assert found, "no project-scoped URLs found — did the URL shape change?"
    for where, suffixes in found.items():
        for suffix in suffixes:
            assert _template(suffix) in ROUTES, f"{where}: /project/…/{suffix}"


def test_the_dataset_run_link_lands_on_the_experiments_tab():
    """The presenter clicks this to reach the comparison view. `datasets/{id}` alone
    redirects to Items, and `datasets/{id}/runs` does not exist at all."""
    text = (SRC / "synth" / "experiment" / "run.py").read_text()
    built = {_template(s) for s in _URL.findall(text)}
    assert built == {"datasets/{}/experiments"}, built


def test_the_runbook_links_use_known_routes():
    """`script.py` builds the DEMO_SCRIPT's links from bare suffixes."""
    text = (SRC / "synth" / "script.py").read_text()
    suffixes = set(re.findall(r"_deep_link\(state, [\"']([a-z-]+)[\"']", text))
    suffixes |= set(re.findall(r"_deep_link\(state, f[\"']([a-z-]+)/", text))
    assert suffixes
    for s in suffixes:
        assert _template(s) in ROUTES or _template(f"{s}/x") in ROUTES, s
