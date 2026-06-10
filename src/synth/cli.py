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
         dry_run: bool = typer.Option(False, "--dry-run", help="Build everything but send nothing."),
         spool: str = typer.Option(None, "--spool", help="NDJSON spool path (default .synth_spool/events.ndjson)."),
         no_import: bool = typer.Option(False, "--no-import",
                                        help="Write the spool to disk but skip the upload (resume with `synth import-spool`).")):
    """Generate deterministic traces + templated v1 rejections, spool them to disk, batch-import
    backdated, register prompts, create the dataset, reserve live-add cases, and emit DEMO_SCRIPT.md."""
    from .script import render_script
    from .seed.run import run_seed

    cfg = _load(config)
    state = run_seed(cfg, dry_run=dry_run, spool_path=spool, do_import=not no_import,
                     log=lambda m: typer.echo(m))
    out = render_script(cfg, state)
    typer.echo(f"✓ DEMO_SCRIPT.md written -> {out}")


@app.command(name="import-spool")
def import_spool(spool: str = typer.Argument(None, help="Spool file to import (default .synth_spool/events.ndjson)."),
                 config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c")):
    """Resume an interrupted upload: batch-import an existing NDJSON spool without regenerating."""
    from .seed.run import import_spool_file

    cfg = _load(config)
    import_spool_file(cfg, spool, log=lambda m: typer.echo(m))


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
               label: str = typer.Option("production", "--label",
                   help="Prompt label to run: 'production' (v1, red) or 'development' (v2, green)."),
               gate: float = typer.Option(None, "--gate", help="CI mode: exit non-zero if offline PASS-rate < threshold.")):
    """Run the prompt carrying --label against the hosted dataset. `production` (==v1) is red;
    `development` (==v2) is green — validate the fix before promoting v2 to production."""
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

    _run(cfg, label=label, log=lambda m: typer.echo(m))


@app.command()
def submit(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
           prefab: str = typer.Option(None, "--prefab", help="One of: eligible, overcap, phev, approvable, rejected."),
           vehicle: str = typer.Option("BEV", "--vehicle", help="Custom: BEV | PHEV | ICE."),
           price: int = typer.Option(None, "--price", help="Custom: vehicle list price (EUR)."),
           line: int = typer.Option(None, "--line", help="Approved credit line (EUR); overrides the prefab default.")):
    """Submit one application through the live production prompt and emit its trace."""
    from .live.prefabs import PREFABS, PREFABS_BY_KEY
    from .live.submit import submit as _submit
    from .models import Application, Vehicle

    cfg = _load(config)
    if prefab:
        p = PREFABS_BY_KEY.get(prefab)
        if not p:
            typer.echo(f"unknown prefab {prefab!r}; choose from: {', '.join(k for k in PREFABS_BY_KEY)}", err=True)
            raise typer.Exit(code=2)
        app_in = p.application(approved_line_eur=line)
    else:
        if price is None or line is None:
            typer.echo("custom submission needs --price and --line (or use --prefab)", err=True)
            raise typer.Exit(code=2)
        app_in = Application(applicant_id="playground_applicant", approved_line_eur=line,
                             vehicle=Vehicle(type=vehicle, list_price_eur=price), application_date="")

    res = _submit(cfg, app_in, log=lambda m: typer.echo(m))
    d, e = res["decision"], res["expected"]
    typer.echo(f"\n— DECISION (production prompt v{res['prompt_version']}) —")
    typer.echo(f"  {d.decision.upper()}  ·  grant €{d.applied_grant_eur:,}  ·  financed €{d.financed_principal_eur:,}")
    typer.echo(f"  expected under v2: {e.decision.upper()}  ·  financed €{e.financed_principal_eur:,}")
    typer.echo(f"  trace → {res['trace_url']}")


@app.command()
def playground(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
               host: str = typer.Option("127.0.0.1", "--host"),
               port: int = typer.Option(8000, "--port")):
    """Serve the live decision configurator UI (needs the `playground` extra: pip install -e '.[playground]')."""
    cfg = _load(config)
    try:
        import uvicorn
        from .live.app import create_app
    except ImportError:
        typer.echo("playground deps missing — run: pip install -e '.[playground]'", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"→ playground on http://{host}:{port}  (production prompt is pulled live per submission)")
    uvicorn.run(create_app(cfg), host=host, port=port, log_level="warning")


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
