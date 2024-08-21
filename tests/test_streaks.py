"""Tests for fixlog.streaks."""

from datetime import datetime, timedelta, timezone

import pytest

from fixlog.errors import NotFoundError
from fixlog.streaks import StreakInfo, StreakTracker


class TestStreakInfo:
    def test_dataclass_fields(self):
        info = StreakInfo(
            dwelling_id="p1",
            dwelling_name="Fern",
            current_streak=3,
            longest_streak=5,
            on_schedule=True,
            last_repaired="2024-06-01",
        )
        assert info.current_streak == 3


class TestStreakTracker:
    def test_compute_no_events(self, populated_storage, sample_dwelling2):
        tracker = StreakTracker(populated_storage)
        populated_storage.mutate(lambda d: d.update({"repair_events": []}))
        info = tracker.compute(sample_dwelling2.id)
        assert info.current_streak == 0
        assert info.on_schedule is False

    def test_compute_with_events(self, populated_storage, sample_dwelling):
        tracker = StreakTracker(populated_storage)
        info = tracker.compute(sample_dwelling.id)
        assert info.dwelling_id == sample_dwelling.id

    def test_compute_not_found(self, empty_storage):
        tracker = StreakTracker(empty_storage)
        with pytest.raises(NotFoundError):
            tracker.compute("missing")

    def test_leaderboard(self, populated_storage):
        tracker = StreakTracker(populated_storage)
        board = tracker.leaderboard(limit=5)
        assert isinstance(board, list)

    def test_broken_streaks(self, populated_storage, sample_dwelling):
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        populated_storage.update_dwelling(sample_dwelling.id, {"last_repaired_at": old_date})
        tracker = StreakTracker(populated_storage)
        broken = tracker.broken_streaks()
        assert isinstance(broken, list)

    def test_longest_streak_multiple_events(self, populated_storage, sample_dwelling):
        tracker = StreakTracker(populated_storage)
        info = tracker.compute(sample_dwelling.id)
        assert info.longest_streak >= info.current_streak

    def test_on_schedule_recent_service(self, populated_storage, sample_dwelling):
        tracker = StreakTracker(populated_storage)
        info = tracker.compute(sample_dwelling.id)
        assert info.last_repaired is not None

    def test_leaderboard_respects_limit(self, populated_storage):
        tracker = StreakTracker(populated_storage)
        board = tracker.leaderboard(limit=1)
        assert len(board) <= 1

    def test_grace_days_constant(self):
        assert StreakTracker.GRACE_DAYS == 1.5

    def test_season_calendar_optional(self, populated_storage):
        from fixlog.seasons import SeasonCalendar
        tracker = StreakTracker(populated_storage, seasons=SeasonCalendar())
        info = tracker.compute("dwelling001")
        assert info.dwelling_name

    def test_two_events_within_gap(self, empty_storage, sample_dwelling):
        empty_storage.create_dwelling(sample_dwelling)
        today = datetime.now(timezone.utc)
        for days_ago in (7, 0):
            empty_storage.create_repair_event({
                "id": f"we_{days_ago}",
                "dwelling_id": sample_dwelling.id,
                "repaired_at": (today - timedelta(days=days_ago)).isoformat(),
                "amount_ml": 200,
            })
        tracker = StreakTracker(empty_storage)
        info = tracker.compute(sample_dwelling.id)
        assert info.current_streak >= 1
