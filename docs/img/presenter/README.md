# Presenter screenshots

Original Langfuse Cloud UI captures from the synthetic `new-ev-demo` rehearsal
project on 10 September 2026. These illustrate navigation, not the current
deployment's state. Captures contain no credentials or real customer records.

| File | What it shows |
| --- | --- |
| `observations-filter.png` | Tracing query for production AGENT / credit_agent and Boolean user_disagreement. |
| `customer-feedback.png` | Reserved trace's Scores tab and customer disagreement comment. |
| `curated-item.png` | Existing reserved item, application string and reviewed structured expectation. |
| `decision-playground.png` | Decision generation, stale output, managed prompt v1 and Playground menu. |
| `experiment-configure.png` | Unsaved candidate configuration; structured output enabled but schema still needs adding. |
| `experiment-dataset.png` | Dataset version selector and application coverage; latest default is not a frozen version. |
| `experiment-evaluator.png` | Available code evaluator in the attachment picker; not yet attached in this draft. |
| `evaluator-editor.png` | Saved Python evaluator editor and live-scope sample filters; not historical-batch filters or proof of a passing test. |

The screenshot session inspected existing records and an unsaved experiment
wizard. It did not submit experiments, change evaluators, add dataset items or
promote prompts. Ongoing live-verification work belongs to portal issue #236.

The generated runbook uses absolute raw.githubusercontent.com image URLs pinned
to the asset commit so the portal's ordinary Markdown reader can display them.
Each image has descriptive alt text, a caption and a full-size link. On refresh,
commit the captures first, update the template's pinned asset revision, regenerate
the portal fixture and inspect both Talk track and Demo Package views.
