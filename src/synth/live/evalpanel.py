"""The presenter's eval triggers and their in-scene result card (#180).

The demo's central beat — ``production`` (v1, stale grant window) goes RED, ``development``
(v2, the fix) goes GREEN — used to need a shell. A depot-delivered presenter has no shell,
so the kit's best moment was unreachable in the cartridge delivery. These two buttons put it
on the playground page.

**They are presenter tools, not part of the demo fiction.** A prospect looking at the loan
application should not register them, so the trigger lives behind a quiet collapsed
disclosure at the very bottom of the page: muted tokens only (``--text-disabled`` /
``--line-structure``), no accent colour, no headline weight — footer utility, not CTA. The
runbook tells the presenter where it is; the audience never wonders what it is.

The *result*, by contrast, is full-size: once a run is triggered it IS the demo moment, so
it renders in the playground's ordinary card idiom (verdict, pass/fail counts, a Langfuse
deep link into the runs comparison view).

Rendering only — no clients, no network, no config beyond the dataset name — so every string
here is unit-testable offline and the route in ``app.py`` stays thin.
"""
from __future__ import annotations

import html

from langfuse_synth_core.live.paths import local

from ..experiment.outcome import ExperimentOutcome

#: The two labels the buttons run, in page order, with their expected demo outcome.
CHOICES = (("production", "red"), ("development", "green"))

# Scoped to `.pnl` so nothing here can bleed into the in-scene surface. The shared theme
# (`langfuse_synth_core.live.theme`) styles `button` as the full-width lime CTA; the panel
# deliberately overrides that back down to a muted outline — the whole point is recessiveness.
_CSS = """
.pnl{margin-top:40px;border-top:1px dashed var(--line-divider-dash);padding-top:12px}
.pnl>summary{list-style:none;cursor:pointer;font-family:var(--font-mono);font-size:11px;
  letter-spacing:.1em;text-transform:uppercase;color:var(--text-disabled)}
.pnl>summary::-webkit-details-marker{display:none}
.pnl>summary:hover{color:var(--text-tertiary)}
.pnl .row{display:flex;gap:10px;margin-top:12px}
.pnl form{flex:1;margin:0}
.pnl button{margin-top:0;background:transparent;border-color:var(--line-structure);
  color:var(--text-tertiary);font:500 12.5px var(--font-mono);padding:9px 10px}
.pnl button:hover{background:#403d391a;filter:none}
.pnl .note{margin-top:10px;color:var(--text-disabled);font-size:11.5px}
"""

# The shared theme's own submit handler is registered *after* this one (it is emitted below
# the page body), so it would overwrite whatever we set. Deferring by a tick lets our text
# land last without the theme having to know this route exists.
_JS = ("document.addEventListener('submit',function(e){"
       "if(((e.target.getAttribute('action')||'').endsWith('/eval')))"
       "setTimeout(function(){document.getElementById('ovmsg').textContent='Running evaluation';},0);});")


def _dataset_note(dataset_name: str, item_count: int | None) -> str:
    """One muted line telling the presenter the size of what they are about to run — the
    count comes from the seed's run state, and is simply omitted when it is unreadable."""
    size = f" · {item_count} items" if item_count is not None else ""
    return (f"Runs the hosted dataset <code>{html.escape(dataset_name)}</code>{size} through the "
            f"labelled prompt. <b>production</b> is the stale v1 → red; <b>development</b> is "
            f"the fix → green.")


def trigger_panel(dataset_name: str, item_count: int | None) -> str:
    """The collapsed, muted disclosure at the very bottom of the playground index."""
    buttons = "".join(
        f'<form method="post" action="{local("/eval")}">'
        f'<input type="hidden" name="label" value="{label}">'
        f'<button type="submit">Run eval · {label}</button></form>'
        for label, _expected in CHOICES)
    return (f"<style>{_CSS}</style>"
            f'<details class="pnl"><summary>presenter tools</summary>'
            f'<div class="row">{buttons}</div>'
            f'<div class="note">{_dataset_note(dataset_name, item_count)}</div>'
            f"</details><script>{_JS}</script>")


def result_card(label: str, version, outcome: ExperimentOutcome, *, dataset_name: str,
                run_name: str, run_url: str | None) -> str:
    """The full-size in-scene card for a finished run: verdict, counts, and the deep link
    into Langfuse's dataset-runs comparison view."""
    green = outcome.green
    detail = (f"Every item matched its expected decision — the {html.escape(label)} prompt "
              f"decides this dataset correctly."
              if green else
              f"{outcome.failed} of {outcome.total} items disagreed with the expected decision "
              f"— the {html.escape(label)} prompt is not applying the grant.")
    errored = (f'<div class="kv"><span>No usable decision</span><span>{outcome.errored}</span></div>'
               if outcome.errored else "")
    link = (f'<div class="kv"><span>Compare in Langfuse</span>'
            f'<span><a href="{html.escape(run_url, quote=True)}" target="_blank">dataset runs →</a></span></div>'
            if run_url else "")
    return f"""
    <div class="eyebrow">Langfuse Bank · evaluator run</div>
    <div class="card active">
      <div class="verdict {'approve' if green else 'reject'}">{outcome.verdict}<span class="pill">{html.escape(label)} v{html.escape(str(version))}</span></div>
      <p class="sub" style="margin:6px 0 14px">{detail}</p>
      <div class="kv"><span>Dataset</span><span>{html.escape(dataset_name)}</span></div>
      <div class="kv"><span>Matched expected decision</span><span>{outcome.passed} / {outcome.total}</span></div>
      {errored}
      <div class="kv"><span>Dataset run</span><span>{html.escape(run_name)}</span></div>
      {link}
    </div>
    <a class="back" href="{local('/')}">← back to the application</a>"""
