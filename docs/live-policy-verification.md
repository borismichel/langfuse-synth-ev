# Fresh decisions after promotion — portal #236

This is a standalone live rehearsal, independent of the full Presenter Runbook.
Use the native `policy_correctness` evaluator from `POLICY_EVALUATOR.py`. It checks
grant, principal and decision; a correct rejection can pass. Project access and
successful hosted execution are prerequisites for claiming Cloud completion.

## Prepare the deployment and rule

1. Use a designated demo project and the Companion running this kit revision.
   Record project URL, kit revision, deployment policy and prompt name. Complete
   the native experiment comparison from #235 and record the tested numeric
   candidate version, cohort, settings, policy scores and rejection controls.
   Stop if candidate acceptance or hosted evaluator execution is still pending.
2. Download the Demo Package. `POLICY_EVALUATION.json.production_rule` is a UI
   recipe, not a request body. Its scope identifies this prompt name and the exact
   deployment policy. Reuse the tested evaluator with those constants. Do not
   create a second evaluator or rule with overlapping coverage.
3. Before enabling a rule, submit an eligible application once through the
   Companion with the current production prompt. Do not dispute it. Open its
   fresh trace and select **credit_agent**, type **AGENT**. Its own input contains
   `application` and `policy`; its own output contains the complete Decision.
   The evaluator checks that supplied policy against its embedded constants;
   a mismatch is an execution error, not a failed policy decision. Historical
   and native experiment inputs retain their existing normalization.
4. On the evaluator's observation sample picker, apply ALL recipe conditions:
   name exactly `credit_agent`, type `AGENT`, environment exactly `production`,
   and metadata key `evaluation_scope` equal to the recipe's value. Inspect the
   actual matched rows before activation: exactly one agent per submitted trace,
   including the undisputed case. Check the excluded sibling `decision`, root,
   tools and simulated generations. Staging, native/SDK experiments and evaluator
   executions must not match. The unique marker is only attached to the live
   agent; do not broaden the rule to names alone or a logical-root shortcut.
5. Test that selected observation in the hosted evaluator. Create one incoming
   observation rule using the reviewed filters, attach `policy_correctness`, and
   select 100% sampling for this small demo. Record rule ID/URL, evaluator
   version, selected filters, matched count and activation time. No tag or score
   filter may require `disputed` or `user_disagreement`. No expected-output
   dataset or mapping is needed. Saving package files never enables this rule,
   launches a historical batch, or creates a notification destination.

The initial scope-review submission predates activation and is an editor sample,
not evidence of automatic scoring. Submit again after activation to prove the
incoming rule fires without manual batch evaluation or customer feedback.

## Promote once and verify new submissions

1. With the rule active and production still on the baseline, submit the same
   eligible application. Record its new trace and `credit_agent` observation ID,
   input, policy, output, prompt version and eventual native policy score. Do
   not click Dispute or start a manual evaluation. Confirm one completed score
   for that observation and the selected evaluator. A stale grant decision
   should produce `false`, with incorrect amounts identified in its explanation.
2. In Langfuse Prompt Management, move the `production` label **once** to the
   tested numeric candidate. Record previous/new versions and promotion time.
   If production already points at the candidate, report the existing state;
   do not reset it just to manufacture a before/after demonstration.
3. Resubmit the identical application in the Companion. Keep vehicle and credit
   line unchanged; live submission stamps today's UTC application date, so run
   both submissions on the same UTC date and check that date against the policy.
   The Companion reads `production` with cache TTL zero on every request. Record
   the fresh trace and `credit_agent` ID. On its sibling `decision` generation,
   inspect the **native managed prompt link** and numeric version. Agent metadata
   also records that version for convenience; it is not a substitute for the
   native generation link. Evaluator input/output come only from the agent.
4. Wait for the new observation's native `policy_correctness` score. Verify the
   grant, financed principal and decision individually, then confirm `true` and
   its explanation. The same trace must have no `user_disagreement` score. The
   score must be observation-linked and originate from the active rule, not
   from local checks, manual API scores or an experiment.
5. Submit the `grant_still_above_line` rejection control from the package's
   reviewed editor examples, through the Companion using today's date. It must
   still reject, with the qualifying grant and net principal correct, and receive
   `true`. If the current date precedes the policy, choose/review an applicable
   ineligible control instead and record the reason. Never promise the candidate
   passes until the real model output and score have arrived.

Promotion affects subsequent decisions. Old traces and their prompt links remain
historical evidence; historical appeal rates and cached Companion analytics are
not rewritten. A re-seed reasserts prompt labels and appends observations, so do
not re-seed during this verification.

## Distinguish scores from execution state

| Visible state | Meaning and next action |
|---|---|
| No score, execution pending | Wait for ingestion/evaluation and inspect the rule's execution status. Do not substitute zero. |
| Execution failed, no score | Inspect the evaluator execution/error details (including `langfuse-code-eval`). Fix context/runtime/configuration; this is not evidence of a policy error. |
| Boolean false, `policy_error` | Execution succeeded and grant, principal or decision violates policy. Read the explanation. |
| Boolean false, `malformed_output` | Output could not be scored as a Decision; distinguish this from arithmetic failure. |
| Boolean true, `pass` | All three policy checks passed, including correct rejects. |

Use `POLICY_COVERAGE.py` with the exact expected live agent observation IDs and
normalized score/execution exports described in `POLICY_EVALUATION.md`. Record
expected, scored, policy failures, malformed, missing, pending, execution errors,
duplicates and unexpected IDs separately. After ingestion settles, missing scores
with no execution are **unaccounted for**, not presumed pending. The Companion's
decision-agreement card does not display the native policy score; inspect Langfuse.

## Optional alert walkthrough

In the project's **Alerts → New Alert**, choose **Scores (boolean)** and the
average value of `policy_correctness`. Filter to the same production scope and
evaluator; inspect the matched rows and exclude editor tests and experiment scores.
Do not filter Boolean value to true or false: that would destroy the denominator.
The average is the share of completed checks that pass, not an approval rate:
9 passes out of 10 scores = 0.9; a correct rejection counts as a pass. Missing and
failed executions are absent from that denominator, so show coverage alongside it.

For a small rehearsal, demonstrate a **1 hour** lookback with alert condition
**average < 0.95**. Explain the chosen window and sample count; sparse demo traffic
can make a single failure dominate. Explicitly select **Show severity NO_DATA**
instead of the default zero substitution: an empty window is neither a policy
failure nor proof of health. UNKNOWN means the alert has not evaluated yet.

Leave the Automations/notification selection empty for a visual walkthrough.
Saving an alert makes it active immediately; it does not require a destination.
Only attach Slack, webhook or GitHub Actions after the presenter explicitly
chooses the destination and authorizes notifications. Discuss breach/recovery,
renotification (leave Off unless chosen), and any sustained-NO_DATA notification
delay explicitly. No setup code creates alerts or notification destinations.

## Evidence to retain

Record project and Companion URLs, kit revision, policy constants, baseline and
candidate experiment references, evaluator ID/version, rule URL/filters/sampling
and activation time, inspected inclusion/exclusion examples, and promotion time.
For each baseline/candidate/control submission retain the application and policy,
new trace/agent IDs, native generation prompt link/version, output, score
ID/value/explanation, execution state and absence of customer feedback. Export
the expected IDs and coverage report. Record the optional alert configuration
and notification choice only if demonstrated.

Local mocks or exported outputs evaluated locally do not prove hosted automatic
scoring. If access, code execution, rule activation or the tested candidate is
unavailable, mark Cloud acceptance pending and name the missing evidence.

Sources checked 10 September 2026:
- [Production observation rules](https://langfuse.com/docs/evaluation/get-started/online)
- [Code evaluator context and runtime](https://langfuse.com/docs/evaluation/evaluation-methods/code-evaluators)
- [Boolean alert rates, windows and no-data behavior](https://langfuse.com/docs/observability/features/alerts)
