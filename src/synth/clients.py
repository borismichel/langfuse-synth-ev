"""One place that answers "adapter, or the env?" for every client the kit needs.

Two surfaces need Langfuse / LLM / ingestion clients, and each has two callers:

* a **live** caller — the playground's routes (submit, dispute, the presenter eval
  triggers), which run inside a portal deployment and are handed a **Companion Adapter**.
  The adapter owns secret intake and provider resolution (Spec G · D4/D6) and hands back
  ready clients, so the Surface never sees a raw key and the spend rides the deployment's
  capped shared key;
* a **headless** caller — ``synth submit`` / ``synth experiment`` on a developer's shell,
  where there is no adapter and the clients are built directly off the core resolution
  module + the env.

Keeping that fork in one module means the two paths cannot drift apart: whatever a route
gets in a deployment, the equivalent CLI command gets from the env, resolved the same way.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import Config

if TYPE_CHECKING:
    from langfuse_synth_core.companion import CompanionAdapter


def langfuse_client(cfg: Config, adapter: "CompanionAdapter | None") -> Any:
    """The Langfuse SDK client (prompts, datasets, experiments)."""
    if adapter is not None:
        return adapter.langfuse()
    from langfuse_synth_core.lfclient import get_langfuse

    return get_langfuse(cfg)


def llm_client(cfg: Config, adapter: "CompanionAdapter | None") -> Any:
    """The ready LLM client for the kit's task model. The adapter is constructed with this
    same model as its ``llm_model_default`` (``cli.py``), so both branches resolve the same
    model — a deployment-pinned ``LLM_MODEL`` still outranks it either way."""
    if adapter is not None:
        return adapter.llm(cfg.golden_path.task_model)
    from langfuse_synth_core.companion.llm import get_llm

    return get_llm(cfg.golden_path.task_model)


def ingestor(cfg: Config, adapter: "CompanionAdapter | None") -> Any:
    """The backdated-batch **write** client used to emit live traces and scores."""
    if adapter is not None:
        return adapter.ingestor()
    from langfuse_synth_core.seed.ingest import Ingestor

    return Ingestor.from_env(cfg.target.base_url)
