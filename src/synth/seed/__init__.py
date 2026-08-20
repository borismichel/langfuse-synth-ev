"""Seed-time subsystems: backdated ingestion, traces, scores, prompts, dataset, incidents."""

from langfuse_synth_core.seed.writepath import OTLP, set_spool_write_path

# The kit's write path, pinned in code rather than left to the environment (core
# `docs/WRITE_PATHS.md`): flipped by portal #210, reverted by reverting this line. Every
# event-building entrypoint — `synth seed`, the golden-gate adapter, the live submission
# (which reuses `seed.traces`) — imports through this package, so the pin is in force
# before ANY builder runs.
set_spool_write_path(OTLP)
