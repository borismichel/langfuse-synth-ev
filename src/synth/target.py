"""Single source of truth for **target-specific behaviour** (Cloud vs self-hosted).

The kit is cloned per scenario and pointed at a different Langfuse (Cloud, or a
self-hosted instance) via ``LANGFUSE_BASE_URL``. One fact about the target changes how
the seeder/verifier behave, so keep the decision HERE rather than scattering
``"cloud.langfuse.com" in url`` checks:

**Is it Langfuse Cloud?** (URL-derived.) Cloud rate-limits the one-at-a-time REST
reads/writes (the paginated ``/v2/scores`` reads ``synth verify`` fires, the per-trace
GETs, the prompt-label PATCH). Self-hosted has no such limit. So on Cloud we (a) space
those calls out a little and (b) lean on the Retry-After-aware backoff in ``http`` — see
``langfuse_synth_core.http.request_retry``. This is purely a function of the host, so it lives on
``TargetProfile``. The batch ingestion endpoint is unaffected (it already retries and is
not one-request-per-event), so the seed itself needs no throttle.
"""
from __future__ import annotations

from dataclasses import dataclass

# Both EU (cloud.langfuse.com) and US (us.cloud.langfuse.com) contain this substring.
CLOUD_HOST_MARKER = "cloud.langfuse.com"

# Per-request spacing on the one-at-a-time REST reads/writes, Cloud only.
CLOUD_POST_THROTTLE_S = 0.35


@dataclass(frozen=True)
class TargetProfile:
    """URL-derived target facts. Build once with :meth:`detect` and pass it around."""

    base_url: str
    is_cloud: bool
    post_throttle_s: float

    @classmethod
    def detect(cls, base_url: str) -> "TargetProfile":
        url = (base_url or "").rstrip("/")
        is_cloud = CLOUD_HOST_MARKER in url
        return cls(base_url=url, is_cloud=is_cloud,
                   post_throttle_s=CLOUD_POST_THROTTLE_S if is_cloud else 0.0)

    @property
    def label(self) -> str:
        return "Langfuse Cloud" if self.is_cloud else "self-hosted Langfuse"


def post_throttle_seconds(base_url: str) -> float:
    """Convenience: per-object REST call spacing for this target (0 off-Cloud)."""
    return TargetProfile.detect(base_url).post_throttle_s
