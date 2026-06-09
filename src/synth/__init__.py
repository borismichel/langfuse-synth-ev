"""Langfuse demo-data synthesiser — the EV-subsidy regression scenario.

See the spec (``langfuse-demo-synth-spec.md``) and ``README.md``. The package is
organised as:

- ``config``       — typed load of ``config/demo.yaml``
- ``rng``          — single-seed deterministic RNG + W3C-format ID derivation
- ``models``       — ``Application`` / ``Decision`` data contracts (spec §16)
- ``agent``        — ``decide(application, prompt_label)`` (the one lever, spec §17)
- ``seed/*``       — backdated batch ingestion, traces, scores, prompts, dataset, incidents
- ``experiment/*`` — the live ``run_experiment`` fix runner (spec §7)
- ``verify``       — query-back assertions for the golden path
- ``script``       — render ``DEMO_SCRIPT.md`` from run state (spec §18)
- ``cli``          — ``synth plan | seed | verify | experiment | script``
"""

__version__ = "0.1.0"
