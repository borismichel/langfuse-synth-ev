"""The decision-playground configurator (FastAPI + server-rendered HTML).

A single page: pick a prefab (auto-fills the fields) or enter a custom application against
an editable credit line, submit, and get the real production decision back — plus a deep
link to the agent-graph trace it just emitted. Styled with the shared Langfuse tokens
(``theme.py``). Launch with ``synth playground``.
"""
from __future__ import annotations

import html
import json

from ..config import Config
from ..models import Application, Vehicle
from .prefabs import PREFABS
from .submit import dispute, submit
from .theme import page

_HEADER = ("<div class='eyebrow'>● Decision playground</div>"
           "<h1>Run the <span class='mark'>production</span> prompt, live</h1>"
           "<p class='sub'>Pick a scenario or enter your own against an editable credit line — "
           "you get the real decision back, emitted as a trace.</p>")


def _form(prefabs_js: str) -> str:
    opts = "".join(
        f'<option value="{p.key}" data-v="{p.vehicle_type}" data-p="{p.list_price_eur}" '
        f'data-l="{p.approved_line_eur}">{html.escape(p.label)}</option>' for p in PREFABS)
    vopts = "".join(f'<option {"selected" if v=="BEV" else ""}>{v}</option>' for v in ("BEV", "PHEV", "ICE"))
    return f"""
    <form method="post" action="/submit">
      <label>Scenario</label>
      <select id="prefab" onchange="fill()">{opts}<option value="custom">Custom…</option></select>
      <label>Vehicle type</label>
      <select name="vehicle" id="vehicle">{vopts}</select>
      <label>Vehicle list price (€)</label>
      <input name="price" id="price" type="number" value="38000" min="1000" step="500">
      <div class="line"><label>Approved credit line (€) — editable</label>
      <input name="line" id="line" type="number" value="32000" min="1000" step="500"></div>
      <div class="note">The €6,000 EV grant only helps BEVs ≤ €50,000. Nudge the line across the margin to see the flip.</div>
      <button type="submit">Submit application →</button>
    </form>
    <script>const P={prefabs_js};
      function fill(){{const k=document.getElementById('prefab').value;if(k==='custom')return;const p=P[k];
        document.getElementById('vehicle').value=p.v;document.getElementById('price').value=p.p;document.getElementById('line').value=p.l;}}
    </script>"""


def create_app(cfg: Config):
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="EV Credit Decision Playground")
    prefabs_js = json.dumps({p.key: {"v": p.vehicle_type, "p": p.list_price_eur, "l": p.approved_line_eur}
                             for p in PREFABS})
    title = "EV Credit Decision Playground"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return page(_HEADER + _form(prefabs_js), title=title)

    @app.post("/submit", response_class=HTMLResponse)
    def do_submit(vehicle: str = Form("BEV"), price: int = Form(...), line: int = Form(...)) -> str:
        application = Application(applicant_id="playground_applicant", approved_line_eur=line,
                                  vehicle=Vehicle(type=vehicle, list_price_eur=price), application_date="")
        res = submit(cfg, application)
        d = res["decision"]
        cls = "approve" if d.decision == "approve" else "reject"
        body = f"""
        <div class="eyebrow">● Decision</div>
        <div class="card active">
          <div class="verdict {cls}">{d.decision.upper()}<span class="pill">production · v{res['prompt_version']}</span></div>
          <div class="kv"><span>Applied grant</span><span>€{d.applied_grant_eur:,}</span></div>
          <div class="kv"><span>Financed principal</span><span>€{d.financed_principal_eur:,}</span></div>
          <div class="kv"><span>List price / line</span><span>€{price:,} / €{line:,}</span></div>
          <div class="kv"><span>Trace</span><span><a href="{res['trace_url']}" target="_blank">open in Langfuse →</a></span></div>
        </div>
        <form method="post" action="/dispute" class="ghost card">
          <input type="hidden" name="trace_id" value="{res['trace_id']}">
          <label>Disagree with this decision? Tell us why</label>
          <textarea name="comment" rows="3" placeholder="e.g. the €6,000 EV grant should put me under my line"></textarea>
          <button type="submit">Dispute this decision</button>
        </form>
        <a class="back" href="/">← submit another</a>"""
        return page(body, title=title)

    @app.post("/dispute", response_class=HTMLResponse)
    def do_dispute(trace_id: str = Form(...), comment: str = Form("")) -> str:
        res = dispute(cfg, trace_id, comment)
        body = f"""
        <div class="eyebrow">● Dispute logged</div>
        <div class="card active">
          <h2>Appeal recorded</h2>
          <p class="sub" style="margin:0 0 12px">A <b>user_disagreement</b> appeal was logged on this decision —
            it shows up in the dashboard's appeal rate.</p>
          <div class="kv"><span>Your comment</span><span>{html.escape(res['comment'])}</span></div>
          <div class="kv"><span>Trace</span><span><a href="{res['trace_url']}" target="_blank">open in Langfuse →</a></span></div>
        </div>
        <a class="back" href="/">← submit another</a>"""
        return page(body, title=title)

    return app
