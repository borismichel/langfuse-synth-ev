"""Live decision playground (spec §18): the audience submits an application and gets a
real decision back, emitted as a native-looking agent-graph trace at *now*.

The prompt is pulled from Langfuse by the ``production`` label at runtime, so promoting a
new prompt to production is reflected on the very next submission.
"""
