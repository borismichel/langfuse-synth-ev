"""Langfuse Bank — EV auto-loan application (the in-scene playground front-end).

A customer-facing loan application: choose a vehicle and your pre-approved credit line, get
an instant lending decision, and (if you disagree) request a review. Under the hood each
application runs the live production prompt and emits an agent-graph trace — but the UI stays
in character. Styled with the shared Langfuse tokens (``theme.py``). Launch with ``synth playground``.

A second, staff-facing route ``/analytics`` (``dashboard.py``) is the internal lending-analytics
report — appeals climbing, CSAT breaking down, AI monitors green — that Lending Analytics sends
AI Engineering to start the investigation. It's the demo's opening beat.

A third, ``POST /eval``, is the presenter's own control rather than part of the fiction: it
runs the demo's central red/green evaluator beat from the page, so a depot-delivered
presenter reaches it without a shell (#180). Its trigger is tucked away at the bottom of the
index (``evalpanel.py``); its result is full-size, because that result IS the demo moment.
"""
from __future__ import annotations

import html
import json

from ..config import Config
from ..models import Application, Vehicle
from ..state import RunState
from langfuse_synth_core.live.paths import local
from .evalpanel import CHOICES, result_card, trigger_panel
from .prefabs import PREFABS
from .submit import dispute, submit
from langfuse_synth_core.live.theme import page

TITLE = "Langfuse Bank — EV Auto Loans"
_VNAME = {"BEV": "Battery-electric", "PHEV": "Plug-in hybrid", "ICE": "Petrol / diesel"}

_HEADER = ("<div class='eyebrow'>Langfuse Bank · EV financing</div>"
           "<h1>Finance your <span class='mark'>electric vehicle</span></h1>"
           "<p class='sub'>Tell us about the vehicle and your pre-approved credit line, and we'll give "
           "you an instant lending decision.</p>")


def _form(prefabs_js: str) -> str:
    opts = "".join(
        f'<option value="{p.key}" data-v="{p.vehicle_type}" data-p="{p.list_price_eur}" data-l="{p.approved_line_eur}">'
        f'{_VNAME[p.vehicle_type]} · €{p.list_price_eur:,}</option>' for p in PREFABS)
    vopts = "".join(f'<option value="{k}" {"selected" if k=="BEV" else ""}>{html.escape(v)}</option>'
                    for k, v in _VNAME.items())
    return f"""
    <form method="post" action="{local('/submit')}">
      <label>Try an example</label>
      <select id="prefab" onchange="fill()">{opts}<option value="custom">— or enter your own —</option></select>
      <label>Vehicle</label>
      <select name="vehicle" id="vehicle">{vopts}</select>
      <label>Vehicle price (€)</label>
      <input name="price" id="price" type="number" value="38000" min="1000" step="500">
      <div class="line"><label>Your pre-approved credit line (€)</label>
      <input name="line" id="line" type="number" value="32000" min="1000" step="500"></div>
      <div class="note">Battery-electric vehicles under €50,000 qualify for the €6,000 EV purchase grant,
        applied at point of sale.</div>
      <button type="submit">Get my decision →</button>
    </form>
    <script>const P={prefabs_js};
      function fill(){{const k=document.getElementById('prefab').value;if(k==='custom')return;const p=P[k];
        document.getElementById('vehicle').value=p.v;document.getElementById('price').value=p.p;document.getElementById('line').value=p.l;}}
    </script>"""


def _dataset_item_count() -> int | None:
    """How many items the seeded dataset holds, for the muted line next to the eval buttons.

    Read off the run state ``synth seed`` wrote (the spool volume is mounted into the live
    container, same as the dashboard's own read) rather than queried from Langfuse — the
    index must render without a network round-trip. None when there is no state to read, in
    which case the panel simply omits the count."""
    try:
        return int(RunState.load().dataset_items) if RunState.exists() else None
    except Exception:  # noqa: BLE001 — a cosmetic count must never break the page
        return None


def _error_card(headline: str, exc: Exception) -> str:
    """In-scene failure card (model API hiccup, unparseable reply, Langfuse down) — the
    show must go on: no raw 500s mid-presentation, and a one-line technical note so the
    presenter can tell a transient blip from a broken setup."""
    tech = f"{type(exc).__name__}: {exc}"
    return f"""
    <div class="eyebrow">Langfuse Bank · service notice</div>
    <div class="card">
      <h2>{headline}</h2>
      <p class="sub" style="margin:6px 0 14px">Our decision service had a momentary problem and
        nothing was recorded. Please try again — your details are one click back.</p>
      <div class="kv"><span>Technical detail</span><span>{html.escape(tech[:160])}</span></div>
    </div>
    <a class="back" href="{local('/')}">← try again</a>"""


def create_app(cfg: Config, adapter=None):
    """Build the live playground FastAPI app.

    ``adapter`` is the Companion Adapter (Spec G · G4, #142). When present, the submit/dispute
    routes take their ready Langfuse + LLM + ingestion clients from it (the adapter owns secret
    intake); when absent — e.g. the render-only golden/base-path tests — the clients are built
    off the env, so pure rendering (index / analytics) is unaffected either way."""
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse

    app = FastAPI(title=TITLE)
    prefabs_js = json.dumps({p.key: {"v": p.vehicle_type, "p": p.list_price_eur, "l": p.approved_line_eur}
                             for p in PREFABS})

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        staff = f"<a class='back' href='{local('/analytics')}'>staff · lending analytics →</a>"
        panel = trigger_panel(cfg.golden_path.dataset.name, _dataset_item_count())
        return page(_HEADER + _form(prefabs_js) + staff + panel, title=TITLE)

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics() -> str:
        from .dashboard import render_analytics
        try:
            return render_analytics(cfg)
        except Exception as exc:  # noqa: BLE001 — render in-scene, never a raw 500
            return page(_error_card("Analytics is temporarily unavailable", exc), title=TITLE)

    @app.post("/submit", response_class=HTMLResponse)
    def do_submit(vehicle: str = Form("BEV"), price: int = Form(...), line: int = Form(...)) -> str:
        try:
            application = Application(applicant_id="playground_applicant", approved_line_eur=line,
                                      vehicle=Vehicle(type=vehicle, list_price_eur=price), application_date="")
            res = submit(cfg, application, adapter=adapter)
        except Exception as exc:  # noqa: BLE001 — render in-scene, never a raw 500
            return page(_error_card("We couldn't process your application", exc), title=TITLE)
        d = res["decision"]
        approved = d.decision == "approve"
        verdict = "APPROVED" if approved else "DECLINED"
        line_txt = ("Good news — we can finance this vehicle within your pre-approved credit line."
                    if approved else
                    "Unfortunately the amount to finance exceeds your pre-approved credit line.")
        body = f"""
        <div class="eyebrow">Langfuse Bank · lending decision</div>
        <div class="card active">
          <div class="verdict {'approve' if approved else 'reject'}">{verdict}<span class="pill">ref {res['trace_id'][:6].upper()}</span></div>
          <p class="sub" style="margin:6px 0 14px">{line_txt}</p>
          <div class="kv"><span>EV purchase grant applied</span><span>€{d.applied_grant_eur:,}</span></div>
          <div class="kv"><span>Amount financed</span><span>€{d.financed_principal_eur:,}</span></div>
          <div class="kv"><span>Vehicle price / your line</span><span>€{price:,} / €{line:,}</span></div>
          <div class="kv"><span>Decision record</span><span><a href="{res['trace_url']}" target="_blank">view →</a></span></div>
        </div>
        <form method="post" action="{local('/dispute')}" class="ghost card">
          <input type="hidden" name="trace_id" value="{res['trace_id']}">
          <label>Think this is wrong? Request a review</label>
          <textarea name="comment" rows="3" placeholder="e.g. the €6,000 EV grant should put me under my line"></textarea>
          <button type="submit">Request a review</button>
        </form>
        <a class="back" href="{local('/')}">← new application</a>"""
        return page(body, title=TITLE)

    @app.post("/eval", response_class=HTMLResponse)
    def do_eval(label: str = Form("production")) -> str:
        """The presenter's red/green beat, triggered from the page instead of a shell (#180).

        Runs synchronously: the SDK fans the dataset's items out concurrently, so at demo
        scale one run costs roughly one model call of wall-clock and stays inside the proxy's
        timeout budget — no job system for a demo control. Live model calls go through the
        adapter's resolved client, so the spend rides the deployment's capped shared key and
        the Surface never touches a raw key. Outside a deployment (no keys, no dataset) this
        lands in the in-scene error card like every other route — never a raw 500."""
        from ..experiment.run import run_experiment

        if label not in {name for name, _expected in CHOICES}:
            return page(_error_card("That evaluator run isn't available",
                                    ValueError(f"unknown prompt label {label!r}")), title=TITLE)
        try:
            res = run_experiment(cfg, label=label, adapter=adapter)
        except Exception as exc:  # noqa: BLE001 — render in-scene, never a raw 500
            return page(_error_card("We couldn't run the evaluation", exc), title=TITLE)
        return page(result_card(res["label"], res["version"], res["outcome"],
                                dataset_name=res["dataset_name"], run_name=res["run_name"],
                                run_url=res["run_url"]), title=TITLE)

    @app.post("/dispute", response_class=HTMLResponse)
    def do_dispute(trace_id: str = Form(...), comment: str = Form("")) -> str:
        try:
            res = dispute(cfg, trace_id, comment, adapter=adapter)
        except Exception as exc:  # noqa: BLE001 — render in-scene, never a raw 500
            return page(_error_card("We couldn't log your appeal", exc), title=TITLE)
        body = f"""
        <div class="eyebrow">Langfuse Bank · appeal received</div>
        <div class="card active">
          <h2>Thanks — your appeal is in</h2>
          <p class="sub" style="margin:6px 0 14px">We've logged your appeal against this decision. A lending
            specialist will take another look at your application.</p>
          <div class="kv"><span>Your message</span><span>{html.escape(res['comment'])}</span></div>
          <div class="kv"><span>Decision record</span><span><a href="{res['trace_url']}" target="_blank">view →</a></span></div>
        </div>
        <a class="back" href="{local('/')}">← new application</a>"""
        return page(body, title=TITLE)

    return app
