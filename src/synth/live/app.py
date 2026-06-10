"""Langfuse Bank — EV auto-loan application (the in-scene playground front-end).

A customer-facing loan application: choose a vehicle and your pre-approved credit line, get
an instant lending decision, and (if you disagree) request a review. Under the hood each
application runs the live production prompt and emits an agent-graph trace — but the UI stays
in character. Styled with the shared Langfuse tokens (``theme.py``). Launch with ``synth playground``.
"""
from __future__ import annotations

import html
import json

from ..config import Config
from ..models import Application, Vehicle
from .prefabs import PREFABS
from .submit import dispute, submit
from .theme import page

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
    <form method="post" action="/submit">
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


def create_app(cfg: Config):
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse

    app = FastAPI(title=TITLE)
    prefabs_js = json.dumps({p.key: {"v": p.vehicle_type, "p": p.list_price_eur, "l": p.approved_line_eur}
                             for p in PREFABS})

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return page(_HEADER + _form(prefabs_js), title=TITLE)

    @app.post("/submit", response_class=HTMLResponse)
    def do_submit(vehicle: str = Form("BEV"), price: int = Form(...), line: int = Form(...)) -> str:
        application = Application(applicant_id="playground_applicant", approved_line_eur=line,
                                  vehicle=Vehicle(type=vehicle, list_price_eur=price), application_date="")
        res = submit(cfg, application)
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
        <form method="post" action="/dispute" class="ghost card">
          <input type="hidden" name="trace_id" value="{res['trace_id']}">
          <label>Think this is wrong? Request a review</label>
          <textarea name="comment" rows="3" placeholder="e.g. the €6,000 EV grant should put me under my line"></textarea>
          <button type="submit">Request a review</button>
        </form>
        <a class="back" href="/">← new application</a>"""
        return page(body, title=TITLE)

    @app.post("/dispute", response_class=HTMLResponse)
    def do_dispute(trace_id: str = Form(...), comment: str = Form("")) -> str:
        res = dispute(cfg, trace_id, comment)
        body = f"""
        <div class="eyebrow">Langfuse Bank · appeal received</div>
        <div class="card active">
          <h2>Thanks — your appeal is in</h2>
          <p class="sub" style="margin:6px 0 14px">We've logged your appeal against this decision. A lending
            specialist will take another look at your application.</p>
          <div class="kv"><span>Your message</span><span>{html.escape(res['comment'])}</span></div>
          <div class="kv"><span>Decision record</span><span><a href="{res['trace_url']}" target="_blank">view →</a></span></div>
        </div>
        <a class="back" href="/">← new application</a>"""
        return page(body, title=TITLE)

    return app
