"""Time distribution (spec §5): diurnal + weekly weighting so time-series views look real.

We build an hourly weight curve across the window (business-hours peaks, overnight
troughs, weekend dip), then sample each trace's timestamp proportionally and jitter
within its hour. ``run_date`` is the anchor; all "relative to now" offsets snap to it
(spec §9), keeping the grant date and drift window recent on every run.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from .rng import Rng

# Diurnal shape: relative weight per local hour (0-23). Peaks mid-morning & mid-afternoon.
_DIURNAL = [
    0.05, 0.03, 0.02, 0.02, 0.03, 0.06,  # 00-05 overnight trough
    0.15, 0.35, 0.70, 0.95, 1.00, 0.95,  # 06-11 morning ramp -> peak
    0.80, 0.85, 0.95, 0.90, 0.75, 0.55,  # 12-17 afternoon
    0.40, 0.30, 0.22, 0.16, 0.10, 0.07,  # 18-23 evening wind-down
]
# Weekly shape: Mon..Sun. Weekend dip.
_WEEKLY = [1.0, 1.0, 1.05, 1.0, 0.9, 0.45, 0.35]


def hour_weight(dt: datetime) -> float:
    return _DIURNAL[dt.hour] * _WEEKLY[dt.weekday()]


def window_start(run_date: datetime, window_days: int) -> datetime:
    """Midnight UTC, ``window_days`` before the run date."""
    start = run_date - timedelta(days=window_days)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def sample_timestamps(rng: Rng, run_date: datetime, window_days: int, n: int) -> list[datetime]:
    """Return ``n`` timestamps over the window, diurnally/weekly weighted, sorted ascending."""
    start = window_start(run_date, window_days)
    total_hours = window_days * 24
    hours = [start + timedelta(hours=h) for h in range(total_hours)]
    weights = [hour_weight(h) for h in hours]

    rsub = rng.sub("timegen")
    chosen_hours = rsub.choices(hours, weights, k=n)
    out: list[datetime] = []
    for h in chosen_hours:
        jitter = rsub.uniform(0, 3600)  # seconds within the hour
        out.append(h + timedelta(seconds=jitter))
    out.sort()
    return out


def sample_in_range(rng: Rng, start: datetime, end: datetime, n: int, label: str = "range") -> list[datetime]:
    """Sample ``n`` diurnally/weekly-weighted timestamps within an arbitrary [start, end)."""
    start = start.replace(minute=0, second=0, microsecond=0)
    total_hours = max(1, int((end - start).total_seconds() // 3600))
    hours = [start + timedelta(hours=h) for h in range(total_hours)]
    weights = [hour_weight(h) for h in hours] or [1.0]
    rsub = rng.sub("timegen", label)
    out = []
    for h in rsub.choices(hours, weights, k=n):
        out.append(h + timedelta(seconds=rsub.uniform(0, 3600)))
    out.sort()
    return out


def in_window(ts: datetime, start: datetime, end: datetime) -> bool:
    return start <= ts < end


def day_anchor(run_date: datetime, day_offset: int) -> datetime:
    """A timestamp ``day_offset`` days from the run date (offset is typically negative)."""
    return (run_date + timedelta(days=day_offset)).replace(microsecond=0)


def now_utc() -> datetime:
    """The single wall-clock read in the whole program — the run anchor (spec §9).

    Captured once at the start of a command and threaded through as ``run_date`` so the
    rest of the seed path stays deterministic.
    """
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    """ISO-8601 with milliseconds and a trailing Z, as the ingestion API expects."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")
