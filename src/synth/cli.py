"""`synth` CLI (spec §11):

    synth probe       --config demo.yaml   # assert backdated ingestion survives on this host (Cloud pre-check)
    synth plan        --config demo.yaml   # dry-run: volumes, golden-path dates, dataset summary
    synth seed        --config demo.yaml   # generate + ingest backdated; prompts; dataset; DEMO_SCRIPT.md
    synth verify      --config demo.yaml   # query back via v2 API, assert drift/linkage/dataset
    synth experiment  --config demo.yaml   # run the hosted dataset with prompt v2 (the live fix)
    synth script      --config demo.yaml   # (re)generate the demo runbook from current run state

The pipeline commands (probe/plan/seed/verify) accept repeatable ``--set dotted.key=value``
overrides applied to the config before validation, so the portal can scale the single shipped
config per environment (e.g. ``--set generation.target_traces=800`` — the canonical operator
volume knob, mapped to EV's internal ``total_traces`` by the direct-count derivation hook).
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

# Repeatable `--set dotted.key=value` override, shared by the pipeline commands.
SET_OPTION = typer.Option(
    None, "--set", metavar="KEY=VALUE",
    help="Override a config value before validation, e.g. --set generation.target_traces=800. "
         "Repeatable; the value is coerced like yaml (800→int, true→bool, 1.5→float).",
)


def _load(config: str, overrides: list[str] | None = None):
    load_dotenv()  # pick up .env
    return load_config(config, overrides)


@app.command()
def probe(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
          set_: list[str] = SET_OPTION):
    """Verify EARLY that backdated ingestion behaves on this host (PLAN.md §1): ingest ONE
    trace with a historical timestamp, query it back, and FAIL LOUDLY if the timestamp was
    dropped or normalised. Run before any bulk seed on Cloud."""
    from .probe import run_probe

    cfg = _load(config, set_)
    ok = run_probe(cfg, log=lambda m: typer.echo(m))
    raise typer.Exit(code=0 if ok else 1)


@app.command()
def plan(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
         set_: list[str] = SET_OPTION):
    """Dry run: print volumes, golden-path dates, and the dataset summary. No network."""
    from .seed.run import run_seed

    cfg = _load(config, set_)
    state = run_seed(cfg, dry_run=True, persist=False, log=lambda m: typer.echo(m))
    typer.echo("\n— PLAN SUMMARY —")
    typer.echo(json.dumps(state.summary, indent=2))


@app.command()
def seed(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
         set_: list[str] = SET_OPTION,
         dry_run: bool = typer.Option(False, "--dry-run", help="Build everything but send nothing."),
         spool: str = typer.Option(None, "--spool", help="NDJSON spool path (default .synth_spool/events.ndjson)."),
         no_import: bool = typer.Option(False, "--no-import",
                                        help="Write the spool to disk but skip the upload (resume with `synth import-spool`).")):
    """Generate deterministic traces + templated v1 rejections, spool them to disk, batch-import
    backdated, register prompts, create the dataset, reserve live-add cases, and emit DEMO_SCRIPT.md."""
    from .script import render_script
    from .seed.run import run_seed

    cfg = _load(config, set_)
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


@app.command(name="count-spool")
def count_spool(spool: str = typer.Argument(None, help="Spool file to count (default .synth_spool/events.ndjson).")):
    """Print the measured billable set — {traces, observations, scores} — of a materialized
    Spool as JSON. The read-side counterpart to `import-spool`: an offline count of exactly
    what Langfuse meters (experiment runs and dataset items excluded), read straight off the
    NDJSON spool the seed step wrote. This is the measured count the deploy pipeline reads."""
    from .seed.run import count_spool_file

    typer.echo(json.dumps(count_spool_file(spool)))


@app.command()
def verify(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
           set_: list[str] = SET_OPTION):
    """Query the data back via the v2 API and assert the golden path."""
    from .verify import run_verify

    cfg = _load(config, set_)
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


# The live secrets the portal injects for this component (usecase.yaml
# live_components[0].requires_secrets). The Companion Adapter reads them from the env and
# hands the Surface ready clients only — it never sees a raw key (D4).
LIVE_SECRETS = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LLM_API_KEY"]


@app.command()
def playground(config: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
               host: str = typer.Option("127.0.0.1", "--host"),
               port: int = typer.Option(8000, "--port")):
    """Serve the live decision configurator UI (needs the `playground` extra: pip install -e '.[playground]').

    Spec G · G4 (#142): the shell is the Companion Adapter. The fixed ``--config/--host/--port``
    invocation is the adapter's ``Invocation`` shape (the portal templates only ``{config}``);
    the adapter binds ``host:port``, mounts its readiness health route, and serves the Surface
    with graceful shutdown, handing the routes ready Langfuse/LLM clients. Scenario code — the
    routes, dashboard, decision logic, trace shapes — is untouched."""
    cfg = _load(config)
    try:
        from langfuse_synth_core.companion import CompanionAdapter

        from .live.app import create_app
    except ImportError:
        typer.echo("playground deps missing — run: pip install -e '.[playground]'", err=True)
        raise typer.Exit(code=1)
    adapter = CompanionAdapter(cfg, requires_secrets=LIVE_SECRETS,
                               llm_model_default=cfg.golden_path.task_model)
    typer.echo(f"→ playground on http://{host}:{port}  (production prompt is pulled live per submission)")
    # The adapter runs the full inherit path: build the Surface with the adapter (for its ready
    # clients), bind host:port (the portal passes --host 0.0.0.0), mount the readiness route
    # (its default /healthz — the manifest keeps the in-scene index `/` as the portal's cheap
    # liveness poll), then serve.
    adapter.run(lambda ad: create_app(cfg, ad), host=host, port=port)


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
