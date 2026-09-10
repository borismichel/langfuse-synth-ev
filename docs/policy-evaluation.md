# EV policy correctness — portal #235

The main scoring beat is the native Boolean `policy_correctness` code evaluator.
It checks the grant, financed principal and approve/reject decision against the
fictional deployment policy. A correct rejection with incorrect amounts fails.
The optional LLM judge uses the same rubric, but is not the arithmetic authority.

## Demo Package

`POLICY_EVALUATOR.py` is standalone source for the Python code editor, with the
deployment's amount, cap and effective date embedded. `POLICY_EVALUATION.json`
contains the policy, reviewed editor examples, bounded historical observation IDs
and optional judge definition. `POLICY_EVALUATION.md` is this setup guide.
`POLICY_COVERAGE.py` runs offline using only Python standard libraries.
Creating these files does not create rules, evaluate history, or call a model.
Do not reuse an evaluator from a deployment with different policy constants.

## Editor and bounded history

1. Open **Evaluators → New evaluator → Code evaluator → Python**. Paste the
   generated source. Code evaluators read `ctx` directly, without variable mapping.
2. In the editor's sample picker, select a historical `credit_agent` observation
   from the manifest. Check that its own input is the application and its own
   output is the Decision. Test a disputed rejection and an ineligible rejection.
   Inspect the returned Boolean, explanation and `status` metadata.
3. Test the manifest's still-above-line contrast: both outputs say reject; only
   the output with the qualifying grant and net principal passes. Test the date,
   cap and credit-line boundaries, plus malformed output. An invalid policy or
   input raises an execution error; it is not a policy failure.
4. Save the evaluator **without a production rule**. In Observations select the
   manifest's bounded historical IDs, name `credit_agent`, and the matching
   deployment's time range. Confirm exactly one row per application; reject
   duplicates from re-seeding. Include both disputed and rejection controls.
   Do not select every row matching a broad production filter.
5. Use the table's batch evaluation action, select this evaluator and inspect
   the final selection count before starting. Record selected observation IDs,
   evaluator version, resulting scores and execution errors. The selection is
   intentional; saving an evaluator alone must never launch history evaluation.

Never combine trace input with a sibling `decision` generation's output. Scores
belong to the selected `credit_agent` observation. Do not use a generic root filter
as a substitute for the observation name: logical roots can have physical parents.

## Native experiment scoring

Follow the native prompt experiment guide to freeze the cohort and model settings.
In **Start Experiment → Prompt Experiment**, explicitly select `policy_correctness`
for BOTH baseline and candidate. A production observation rule does not configure
experiments. For already-completed experiments use the available experiment
re-evaluation control, or rerun both prompts with the evaluator explicitly selected.

Before the full comparison, inspect real item context in the evaluator editor.
Input normalization supports the bare application and the dataset's `application`
JSON string wrapper. Native chat input must have exactly one user message carrying
that application JSON. Output can be a Decision object, JSON text (optionally one
JSON code fence), or a single assistant message carrying that text. Unsupported or
ambiguous shapes must be surfaced, never guessed from sibling spans or expected
output. Expected output is a reviewed calibration reference, not a substitute for
model output or policy constants.

Compare the `policy_correctness` score column and individual generated outputs.
Show an eligible false negative, a still-above-line BEV, an over-cap BEV and a
non-BEV rejection. Show grant and principal alongside the decision. The candidate
should fix eligible errors while preserving policy-correct rejections; do not
promise an all-green result before inspecting actual model outputs.

## Optional LLM-as-a-Judge

Create a separate Boolean score `policy_correctness_judge` with the generated
prompt and an explicitly selected project LLM Connection/model. Keep its scores
separate from the deterministic metric. For historical evaluation map `input` to
**the selected credit_agent observation's Input**, and `output` to **that same
observation's Output**, both at the root (`$`). For experiments explicitly map
`input` and `output` to the experiment observation's Input and Output; the prompt
normalizes the native wrapper/chat forms. Policy constants are embedded in the
prompt, so no trace-level or sibling lookup is needed. No expected-output variable
is required by this rubric.

Test the judge against ALL reviewed examples in the manifest, including the wrong
amounts/correct-reject pair and boundary controls. Record expected vs actual
Boolean, explanation, model/settings, missing results and execution failures.
Any disagreement needs review; the judge does not overrule the arithmetic.
Only then select the judge explicitly in an experiment or an intentional bounded
historical batch. Creating a definition must not start historical model calls.

## Coverage and errors

Freeze expected observation IDs for history and expected item IDs for EACH run.
Run `python POLICY_COVERAGE.py expected-ids.json records.json` offline. The first
file is a JSON array of IDs; the second is an array of normalized records, for example:

```json
[
  {"item_id":"item-a","name":"policy_correctness","status":"completed","value":1,"metadata":{"status":"pass"}},
  {"item_id":"item-b","name":"policy_correctness","status":"completed","value":0,"metadata":{"status":"policy_error"}},
  {"item_id":"item-c","name":"policy_correctness","status":"error"}
]
```

Export records for the exact evaluator version and selected batch/run. Translate
API/UI field names into this explicit offline format; it is not a raw API response
adapter. Include failed/pending executions even when they have no score. Scores
alone cannot tell you which missing results are execution errors. The manifest
provides demo item IDs **before curation**: add any reserved item IDs and freeze
both runs' final expected lists. Exit status 1 means incomplete/ambiguous coverage;
policy failures with complete coverage still exit 0, so inspect the policy counts.

Use the reporter with exported scores and execution records; each row
must identify the corresponding observation/item as `item_id`, the exact score
name, status and value. Count expected items, scored items, passing/failing policy
scores, malformed outputs, missing scores, pending executions, execution errors,
duplicate results and unexpected IDs separately. Missing results are not zeros;
an empty run cannot pass. Missing-score IDs include failed/pending executions
without scores; their separate status lists explain the gap and must not be summed. Inspect execution traces in `langfuse-code-eval` when
errors occur. Repeat a read after ingestion settles before calling a score missing.

The Companion red/green card reports **decision agreement** with dataset expectations.
It does not check amounts and is never the native policy evaluator's result.

## Verification evidence

Local fixture checks alone are not Cloud verification. Before closing #235 record:
project and evaluator URLs/version; two contrasting editor test results; bounded
history count and observation IDs; baseline/candidate experiment URLs and fixed
settings; real item input/output context shapes; score and execution coverage;
individual rejection controls; and optional judge calibration if demonstrated.
If any UI control or native payload cannot be inspected, record that gap explicitly.

Sources (checked 10 September 2026):
- [Code evaluator contract and runtime](https://langfuse.com/docs/evaluation/evaluation-methods/code-evaluators)
- [Evaluation definitions and rules](https://langfuse.com/docs/evaluation/core-concepts)
- [LLM judge mappings](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [Native experiments](https://langfuse.com/docs/evaluation/experiments/experiments-via-ui)
