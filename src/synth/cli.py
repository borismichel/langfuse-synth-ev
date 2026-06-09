"""`synth` CLI (spec §11):

    synth plan        --config demo.yaml   # dry-run: volumes, golden-path dates, dataset summary
    synth seed        --config demo.yaml   # generate + ingest backdated; prompts; dataset; DEMO_SCRIPT.md
    synth verify      --config demo.yaml   # query back via v2 API, assert drift/linkage/dataset
    synth experiment  --config demo.yaml   # run the hosted dataset with prompt v2 (the live fix)
    synth script      --config demo.yaml   # (re)generate the demo runbook from current run state
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv

from .config import load_config
from .state import RunState

app = typer.Typer(add_completion=False, help="Langfuse demo-data synthesiser — EV-subsidy regression scenario.")

DEFAULT_CONFIG = "config/demo.yaml"


def _load(config: str):
    load_dotenv()  # pick up .env
    return load_config(config)


@app.command()
def plan(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c")):
    """Dry run: print volumes, golden-path dates, and the dataset summary. No network."""
    from .seed.run import run_seed

    cfg = _load(config)
    state = run_seed(cfg, dry_run=True, persist=False, log=lambda m: typer.echo(m))
    typer.echo("\n— PLAN SUMMARY —")
    typer.echo(json.dumps(state.summary, indent=2))


@app.command()
def seed(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
         dry_run: bool = typer.Option(False, "--dry-run", help="Build everything but send nothing.")):
    """Generate deterministic traces + templated v1 rejections, ingest backdated, register
    prompts, create the dataset, reserve live-add cases, and emit DEMO_SCRIPT.md."""
    from .script import render_script
    from .seed.run import run_seed

    cfg = _load(config)
    state = run_seed(cfg, dry_run=dry_run, log=lambda m: typer.echo(m))
    out = render_script(cfg, state)
    typer.echo(f"✓ DEMO_SCRIPT.md written -> {out}")


@app.command()
def verify(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c")):
    """Query the data back via the v2 API and assert the golden path."""
    from .verify import run_verify

    cfg = _load(config)
    if not RunState.exists():
        typer.echo("No .synth_state.json — run `synth seed` first.", err=True)
        raise typer.Exit(code=2)
    state = RunState.load()
    report = run_verify(cfg, state, log=lambda m: typer.echo(m))
    typer.echo(f"\n{'✓ ALL CHECKS PASSED' if report.ok else '✗ SOME CHECKS FAILED'}")
    raise typer.Exit(code=0 if report.ok else 1)


@app.command()
def experiment(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
               baseline: bool = typer.Option(False, "--baseline", help="Also run a v1 baseline for side-by-side."),
               gate: float = typer.Option(None, "--gate", help="CI mode: exit non-zero if offline PASS-rate < threshold.")):
    """Run the hosted dataset with prompt v2 (the live fix) via run_experiment."""
    cfg = _load(config)

    if gate is not None:
        from .experiment.run import pass_rate_offline

        if not RunState.exists():
            typer.echo("No .synth_state.json — run `synth seed` first.", err=True)
            raise typer.Exit(code=2)
        rate = pass_rate_offline(cfg, RunState.load())
        typer.echo(f"offline v2 PASS-rate = {rate:.1%} (gate {gate:.0%})")
        raise typer.Exit(code=0 if rate >= gate else 1)

    from .experiment.run import run_experiment as _run

    _run(cfg, baseline=baseline, log=lambda m: typer.echo(m))


@app.command()
def script(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c")):
    """(Re)generate DEMO_SCRIPT.md from the current run state."""
    from .script import render_script

    cfg = _load(config)
    if not RunState.exists():
        typer.echo("No .synth_state.json — run `synth seed` first.", err=True)
        raise typer.Exit(code=2)
    out = render_script(cfg, RunState.load())
    typer.echo(f"✓ DEMO_SCRIPT.md written -> {out}")


if __name__ == "__main__":
    app()
