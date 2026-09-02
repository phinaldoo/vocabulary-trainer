from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class SchedulerState:
    phase: str = "learning"
    ease: float = 2.5
    interval_days: float = 0
    repetitions: int = 0
    lapses: int = 0


@dataclass(frozen=True)
class ScheduledReview(SchedulerState):
    due_at: datetime = datetime.min.replace(tzinfo=UTC)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def schedule_review(
    previous: SchedulerState | None,
    rating: int,
    now: datetime | None = None,
) -> ScheduledReview:
    if rating not in {0, 1, 2, 3}:
        raise ValueError("rating must be between 0 and 3")

    now = now or datetime.now(UTC)
    state = previous or SchedulerState()

    if previous is None or state.repetitions == 0:
        intervals = [
            timedelta(minutes=10),
            timedelta(hours=6),
            timedelta(days=1),
            timedelta(days=4),
        ]
        interval = intervals[rating]
        return ScheduledReview(
            phase="learning" if rating <= 1 else "review",
            ease=_clamp(state.ease + (-0.2, -0.15, 0, 0.15)[rating], 1.3, 3.0),
            interval_days=interval.total_seconds() / 86_400,
            repetitions=0 if rating == 0 else 1,
            lapses=state.lapses,
            due_at=now + interval,
        )

    if rating == 0:
        return ScheduledReview(
            phase="relearning",
            ease=_clamp(state.ease - 0.2, 1.3, 3.0),
            interval_days=timedelta(minutes=10).total_seconds() / 86_400,
            repetitions=0,
            lapses=state.lapses + 1,
            due_at=now + timedelta(minutes=10),
        )

    multiplier = 1.2 if rating == 1 else state.ease if rating == 2 else state.ease * 1.3
    interval_days = _clamp(state.interval_days * multiplier, 1, 730)
    return ScheduledReview(
        phase="review",
        ease=_clamp(state.ease + (-0.15 if rating == 1 else 0.15 if rating == 3 else 0), 1.3, 3.0),
        interval_days=interval_days,
        repetitions=state.repetitions + 1,
        lapses=state.lapses,
        due_at=now + timedelta(days=interval_days),
    )


def mastery_label(interval_days: float, repetitions: int) -> str:
    if repetitions == 0:
        return "new"
    if interval_days >= 21:
        return "mastered"
    if interval_days >= 3:
        return "familiar"
    return "learning"
