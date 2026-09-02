from datetime import UTC, datetime, timedelta

import pytest

from app.services.scheduler import (
    SchedulerState,
    mastery_label,
    schedule_review,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("rating", "delay"),
    [
        (0, timedelta(minutes=10)),
        (1, timedelta(hours=6)),
        (2, timedelta(days=1)),
        (3, timedelta(days=4)),
    ],
)
def test_initial_intervals(rating: int, delay: timedelta) -> None:
    result = schedule_review(None, rating, NOW)
    assert result.due_at == NOW + delay


def test_lapse_enters_relearning() -> None:
    state = SchedulerState(phase="review", ease=2.5, interval_days=20, repetitions=5, lapses=1)
    result = schedule_review(state, 0, NOW)
    assert result.phase == "relearning"
    assert result.lapses == 2
    assert result.repetitions == 0
    assert result.due_at == NOW + timedelta(minutes=10)


def test_interval_and_ease_are_bounded() -> None:
    state = SchedulerState(phase="review", ease=3.0, interval_days=700, repetitions=20, lapses=0)
    result = schedule_review(state, 3, NOW)
    assert result.interval_days == 730
    assert result.ease == 3.0


def test_mastery_labels() -> None:
    assert mastery_label(0, 0) == "new"
    assert mastery_label(1, 1) == "learning"
    assert mastery_label(3, 1) == "familiar"
    assert mastery_label(21, 2) == "mastered"
