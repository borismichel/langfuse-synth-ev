"""The decision-playground configurator (FastAPI + server-rendered HTML).

A single page: pick a prefab (auto-fills the fields) or enter a custom application against
an editable credit line, submit, and get the real production decision back — plus a deep
link to the agent-graph trace it just emitted. Launch with ``synth playground``.
"""
from __future__ import annotations

import html
import json

from ..config import Config
from ..models import Application, Vehicle
from .prefabs import PREFABS
from .submit import dispute, submit

_CSS = """
*{box-sizing:border-box} body{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
  margin:0;background:#0f1117;color:#e6e8ee} .wrap{max-width:620px;margin:40px auto;padding:0 20px}
h1{font-size:22px;margin:0 0 4px} .sub{color:#9aa3b2;margin:0 0 24px}
label{display:block;font-size:13px;color:#9aa3b2;margin:14px 0 4px}
select,input{width:100%;padding:10px;border:1px solid #2a2f3a;border-radius:8px;background:#171a22;color:#e6e8ee;font-size:15px}
.line input{border-color:#3b82f6} button{margin-top:20px;width:100%;padding:12px;border:0;border-radius:8px;
  background:#3b82f6;color:#fff;font-size:16px;font-weight:600;cursor:pointer} button:hover{background:#2f6fe0}
.note{font-size:12px;color:#6b7280;margin-top:6px}
.card{margin:24px 0;padding:20px;border-radius:12px;border:1px solid #2a2f3a;background:#171a22}
.verdict{font-size:28px;font-weight:700;letter-spacing:.5px} .approve{color:#22c55e} .reject{color:#ef4444}
.kv{display:flex;justify-content:space-between;padding:6px 0;border-top:1px solid #232834;font-size:14px}
.kv span:first-child{color:#9aa3b2} a{color:#60a5fa} .pill{display:inline-block;font-size:12px;padding:2px 8px;
  border-radius:999px;background:#232834;color:#9aa3b2;margin-left:8px}
textarea{width:100%;padding:10px;border:1px solid #2a2f3a;border-radius:8px;background:#171a22;color:#e6e8ee;font:inherit;resize:vertical}
.dispute button{background:#7c3aed} .dispute button:hover{background:#6d28d9}
.overlay{display:none;position:fixed;inset:0;background:rgba(15,17,23,.88);align-items:center;justify-content:center;flex-direction:column;z-index:50}
.spinner{width:44px;height:44px;border:4px solid #2a2f3a;border-top-color:#3b82f6;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}} .overlay p{color:#9aa3b2;margin-top:14px}
"""


def _form(prefabs_js: str, sel: dict | None = None) -> str:
    sel = sel or {"vehicle": "BEV", "price": 38000, "line": 32000}
    opts = "".join(
        f'<option value="{p.key}" data-v="{p.vehicle_type}" data-p="{p.list_price_eur}" '
        f'data-l="{p.approved_line_eur}">{html.escape(p.label)}</option>' for p in PREFABS)
    vopts = "".join(f'<option {"selected" if v==sel["vehicle"] else ""}>{v}</option>'
                    for v in ("BEV", "PHEV", "ICE"))
    return f"""
    <form method="post" action="/submit">
      <label>Scenario</label>
      <select id="prefab" onchange="fill()">{opts}<option value="custom">Custom…</option></select>
      <label>Vehicle type</label>
      <select name="vehicle" id="vehicle">{vopts}</select>
      <label>Vehicle list price (€)</label>
      <input name="price" id="price" type="number" value="{sel['price']}" min="1000" step="500">
      <div class="line"><label>Approved credit line (€) — editable</label>
      <input name="line" id="line" type="number" value="{sel['line']}" min="1000" step="500"></div>
      <div class="note">The €6,000 EV grant only helps BEVs ≤ €50,000. Nudge the line across the margin to see the flip.</div>
      <button type="submit">Submit application →</button>
    </form>
    <script>const P={prefabs_js};
      function fill(){{const k=document.getElementById('prefab').value;if(k==='custom')return;const p=P[k];
        document.getElementById('vehicle').value=p.v;document.getElementById('price').value=p.p;document.getElementById('line').value=p.l;}}
    </script>"""


def _page(body: str) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>EV Credit Decision Playground</title>"
            f"<style>{_CSS}</style></head><body><div class='wrap'>"
            f"<h1>EV Credit Decision Playground</h1>"
            f"<p class='sub'>Your application runs the <b>current production prompt</b>, live.</p>"
            f"{body}</div>"
            f"<div class='overlay' id='overlay'><div class='spinner'></div><p id='ovmsg'>Processing decision…</p></div>"
            f"<script>document.addEventListener('submit',function(e){{"
            f"document.getElementById('ovmsg').textContent=e.target.action.endsWith('/dispute')?'Logging dispute…':'Processing decision…';"
            f"document.getElementById('overlay').style.display='flex';}});</script>"
            f"</body></html>")


def create_app(cfg: Config):
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="EV Credit Decision Playground")
    prefabs_js = json.dumps({p.key: {"v": p.vehicle_type, "p": p.list_price_eur, "l": p.approved_line_eur}
                             for p in PREFABS})

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _page(_form(prefabs_js))

    @app.post("/submit", response_class=HTMLResponse)
    def do_submit(vehicle: str = Form("BEV"), price: int = Form(...), line: int = Form(...)) -> str:
        application = Application(applicant_id="playground_applicant", approved_line_eur=line,
                                  vehicle=Vehicle(type=vehicle, list_price_eur=price), application_date="")
        res = submit(cfg, application)
        d = res["decision"]
        cls = "approve" if d.decision == "approve" else "reject"
        card = f"""
        <div class="card">
          <div class="verdict {cls}">{d.decision.upper()}
            <span class="pill">production · prompt v{res['prompt_version']}</span></div>
          <div class="kv"><span>Applied grant</span><span>€{d.applied_grant_eur:,}</span></div>
          <div class="kv"><span>Financed principal</span><span>€{d.financed_principal_eur:,}</span></div>
          <div class="kv"><span>List price / line</span><span>€{price:,} / €{line:,}</span></div>
          <div class="kv"><span>Trace</span><span><a href="{res['trace_url']}" target="_blank">open in Langfuse →</a></span></div>
        </div>
        <form method="post" action="/dispute" class="dispute card">
          <input type="hidden" name="trace_id" value="{res['trace_id']}">
          <label>Disagree with this decision? Tell us why:</label>
          <textarea name="comment" rows="3" placeholder="e.g. the €6,000 EV grant should put me under my line"></textarea>
          <button type="submit">Dispute this decision</button>
        </form>
        <p><a href="/">← submit another</a></p>"""
        return _page(card)

    @app.post("/dispute", response_class=HTMLResponse)
    def do_dispute(trace_id: str = Form(...), comment: str = Form("")) -> str:
        res = dispute(cfg, trace_id, comment)
        body = f"""
        <div class="card">
          <h2 style="margin:0 0 8px">✓ Dispute recorded</h2>
          <p class="sub" style="margin:0 0 12px">A <b>user_disagreement</b> appeal was logged on this
            decision — it shows up in the dashboard's appeal rate.</p>
          <div class="kv"><span>Your comment</span><span>{html.escape(res['comment'])}</span></div>
          <div class="kv"><span>Trace</span><span><a href="{res['trace_url']}" target="_blank">open in Langfuse →</a></span></div>
        </div>
        <p><a href="/">← submit another</a></p>"""
        return _page(body)

    return app
