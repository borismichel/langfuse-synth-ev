# Current presenter screenshots — 19 October 2026

Fresh, unedited captures of the completed **v0.8.0 ordinary Depot deployment**, in Langfuse Cloud **v4.64.0**. Capture times, URLs and hashes are in [manifest.json](manifest.json). These are existing executed results viewed again for the documentation refresh, not new executions. All cases are fictional.

| Image | Evidence and interpretation |
|---|---|
| [Halo diagnosis](halo-diagnosis.png) | Neutral investigation identifies the missing policy binding and cites retrieval, affordability and compiled input. The answer records prompt labels at investigation time, before later promotion. |
| [Halo curation](halo-curation.png) | One reviewed item added to the existing eight-item cohort; nine items after readback. This capture proves item curation, not creation of a new dataset. |
| [Playground binding](playground-binding.png) | Identical system prompt; candidate adds only `policy_updates`. |
| [Playground results](playground-results.png) | €45,000 rejection versus €39,000 approval after €6,000 grant. Playground windows are editable copies; managed version evidence comes from the native experiments and live generation. |
| [Native comparison](native-comparison.png) | Baseline 4/9 (44%) versus candidate 9/9 (100%), all 18 policy scores read back. Read each false→true row: the UI's directional “regressed” badge is from the baseline perspective. |
| [Live policy score](live-policy-score.png) | Fresh promoted decision: €6,000 grant, €39,000 principal, approve; automatic true score on `credit_agent`, four-observation tree. |
| [Rejection control](live-rejection-control.png) | PHEV remains rejected at €45,000 with no grant; its separate trace has an automatic true policy score. |

The [delivery record](https://github.com/borismichel/langfuse-demo-depot/blob/b294cbe418eb03b5a66fbbbc6e6a8abe9d892aac/docs/release-evidence/ev-context-359/delivery/README.md) retains settings, exact object IDs, five valid Playground pairs, the two initial schema-setup failures, 18 native results, automatic live scores and immutable image provenance. Screenshots do not replace that readback. Production in this reference project now selects v2; do not roll it back to stage a new baseline.
