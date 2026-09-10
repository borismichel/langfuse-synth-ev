# Presenter Runbook delivery verification — 10 September 2026

Scope: portal issue #237, kit base `2a9e40e`, portal base `f6f9e73`.
Implementation is complete for review. End-to-end Cloud acceptance remains dependent
on #235's hosted policy evaluation and #236's fresh production verification.

## Delivery and local checks

- EV full suite: **143 passed**, including deterministic Spool and Companion UI
  goldens. No Spool approval/change was needed. One existing Starlette deprecation warning.
- Portal web full suite: **451 passed**; TypeScript typecheck passed.
- Changed presenter/state/dataset modules and new tests: pyright **0 errors**.
  Checking `seed/run.py` also reports its two existing diagnostics at `get_langfuse`
  (Config protocol) and optional `lf.flush()`; neither expression changed.
- Manifest conformance passes its blocking checks. Existing health-path and
  companion-factory migration advisories remain.
- Artifact integration generates every declared file with `SYNTH_OUT_DIR` and
  `SYNTH_STATE_DIR` set, without model calls. `DEMO_SCRIPT.md` remains the first
  Markdown artifact and is titled Presenter Runbook. The native setup guide is
  also delivered, alongside the existing evaluator and curation assets.
- Tests verify overridden amount/cap/date, custom dataset name/count, non-default
  numeric prompt versions, reserved source/payload consistency, changed runtime
  configuration, disabled golden path, older saved state and dry-run guidance.
  Skipped imports suppress trace links while uploaded dataset links remain usable.
- The portal fixture is an exact template render from its accompanying recorded
  seed-state JSON. Its README describes provenance and regeneration. No EV-specific
  portal runtime implementation was introduced.

## Reader inspection

Used a temporary local Next harness importing the portal's unchanged `NarrativeTabs`,
`ArtifactTabs`, `MarkdownView` and styles. Verified the rendered headings, talk-track
quotes, lists, curation JSON, code fences, project/dataset/prompt/trace hrefs and
missing-resource guidance. Switched Story/Talk track and artifact tabs; a missing
artifact body showed the normal download fallback. A second render with unavailable
resources displayed setup instructions rather than fabricated links.

This checks the actual reusable reader components and manifest/collection path,
not a newly deployed production portal or authenticated Cloud navigation. The
local harness is not part of either repository's runtime changes.

## Review

Standards axis: no findings. Spec axis found that `--no-import` lacked a trace-import
anchor; fixed with saved status, withheld trace links and explicit setup guidance,
then re-reviewed with no remaining implementation findings.

## Remaining acceptance / release prerequisites

Do not close #237 as fully rehearsed or claim a passing live policy score from
these local checks. #235 must establish native evaluator editor/history coverage
and complete scored baseline/candidate comparisons. #236 must establish the scoped
incoming rule, undisputed live score and native promoted-version link, including
its rejection control. The runbook names `LIVE_POLICY_VERIFICATION.md` and the
production-rule recipe supplied by that prerequisite; if absent, it directs the
presenter to the release containing them before presenting the ending.

Merge/release the prerequisite and runbook kit changes together before registering
the new kit image in the depot. Existing registered releases are not modified by
these branches. Bookmark real evaluation/comparison/rule resources at rehearsal;
seed neither invents their IDs nor launches evaluations or notification setup.
