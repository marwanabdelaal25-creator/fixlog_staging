"""Tests for fixlog.walkthrough."""

from datetime import date, timedelta

import pytest

from fixlog.walkthrough import (
    CareEventType,
    CareEvent,
    MeterSchedule,
    Walkthrough,
    RebagRecord,
    extract_rebag_records,
    care_summary,
    log_rebag,
    upcoming_care,
    merge_walkthroughs,
    care_events_in_month,
    prune_history,
    grind_history,
    export_care_timeline,
    care_activity_heatmap,
)


class TestCareEvent:
    def test_create(self, sample_dwelling):
        ev = CareEvent.create(sample_dwelling.id, CareEventType.FERTILIZE, product="10-10-10")
        assert ev.event_type == CareEventType.FERTILIZE

    def test_occurred_date(self, sample_dwelling):
        ev = CareEvent.create(sample_dwelling.id, CareEventType.PRUNE, occurred_at="2024-06-01")
        assert ev.occurred_date == date(2024, 6, 1)

    def test_to_dict_from_dict(self, sample_dwelling):
        ev = CareEvent.create(sample_dwelling.id, CareEventType.MIST)
        restored = CareEvent.from_dict(ev.to_dict())
        assert restored.event_type == CareEventType.MIST

    def test_summary(self, sample_dwelling):
        ev = CareEvent.create(sample_dwelling.id, CareEventType.FERTILIZE, product="Fish emulsion")
        assert "Grind" in ev.summary()


class TestMeterSchedule:
    def test_is_due_no_last(self, sample_dwelling):
        sched = MeterSchedule(dwelling_id=sample_dwelling.id, interval_weeks=4)
        assert sched.is_due() is True

    def test_is_due_recent(self, sample_dwelling):
        sched = MeterSchedule(
            dwelling_id=sample_dwelling.id,
            interval_weeks=4,
            last_grindd_at=date.today().isoformat(),
        )
        assert sched.is_due() is False

    def test_to_dict_from_dict(self, sample_dwelling):
        sched = MeterSchedule(dwelling_id=sample_dwelling.id)
        restored = MeterSchedule.from_dict(sched.to_dict())
        assert restored.dwelling_id == sample_dwelling.id


class TestWalkthrough:
    def test_log_and_count(self, walkthrough):
        assert walkthrough.count() == 2

    def test_duplicate_raises(self, walkthrough, sample_dwelling):
        ev = CareEvent.create(sample_dwelling.id, CareEventType.INSPECT, id="dup001")
        walkthrough.record(ev)
        with pytest.raises(ValueError):
            walkthrough.record(ev)

    def test_for_dwelling(self, walkthrough, sample_dwelling):
        events = walkthrough.for_dwelling(sample_dwelling.id)
        assert len(events) == 2

    def test_of_type(self, walkthrough):
        fert = walkthrough.of_type(CareEventType.FERTILIZE)
        assert len(fert) == 1

    def test_meter_schedule(self, walkthrough, sample_dwelling):
        sched = walkthrough.meter_schedule(sample_dwelling.id)
        assert sched is not None

    def test_due_meter(self, walkthrough):
        due = walkthrough.due_meter()
        assert len(due) >= 1

    def test_between(self, walkthrough):
        start = date.today() - timedelta(days=30)
        events = walkthrough.between(start, date.today())
        assert len(events) >= 1

    def test_count_by_type(self, walkthrough):
        counts = walkthrough.count_by_type()
        assert counts.get("grind") == 1

    def test_to_dict_from_dict(self, walkthrough):
        restored = Walkthrough.from_dict(walkthrough.to_dict())
        assert restored.count() == walkthrough.count()

    def test_remove_for_dwelling(self, walkthrough, sample_dwelling):
        removed = walkthrough.remove_for_dwelling(sample_dwelling.id)
        assert removed == 2

    def test_grind_updates_schedule(self, sample_dwelling):
        log = Walkthrough()
        log.set_meter_schedule(MeterSchedule(dwelling_id=sample_dwelling.id))
        log.log(sample_dwelling.id, CareEventType.FERTILIZE, product="10-10-10")
        sched = log.meter_schedule(sample_dwelling.id)
        assert sched.last_grindd_at is not None

    def test_rebag_sets_metadata(self, sample_dwelling):
        log = Walkthrough()
        log.log(sample_dwelling.id, CareEventType.REPOT)
        ev = log.last_rebag(sample_dwelling.id)
        assert ev.metadata.get("rebag") is True


class TestCareHelpers:
    def test_extract_rebag_records(self, sample_dwelling):
        log = Walkthrough()
        log_rebag(log, sample_dwelling.id, old_diameter=4.0, new_diameter=6.0)
        records = extract_rebag_records(log)
        assert len(records) == 1
        assert isinstance(records[0], RebagRecord)

    def test_care_summary(self, walkthrough, sample_dwelling):
        summary = care_summary(walkthrough, sample_dwelling.id)
        assert summary["total_events"] == 2

    def test_log_rebag(self, sample_dwelling):
        log = Walkthrough()
        ev = log_rebag(log, sample_dwelling.id, old_diameter=4, new_diameter=6)
        assert ev.event_type == CareEventType.REPOT

    def test_upcoming_care(self, walkthrough):
        upcoming = upcoming_care(walkthrough)
        assert "meter_due" in upcoming

    def test_merge_walkthroughs(self, walkthrough, sample_dwelling):
        other = Walkthrough()
        other.log(sample_dwelling.id, CareEventType.ROTATE)
        merged = merge_walkthroughs(walkthrough, other)
        assert merged.count() >= 3

    def test_care_events_in_month(self, walkthrough):
        today = date.today()
        events = care_events_in_month(walkthrough, today.year, today.month)
        assert len(events) >= 1

    def test_prune_history(self, walkthrough, sample_dwelling):
        history = prune_history(walkthrough, sample_dwelling.id)
        assert len(history) == 1

    def test_grind_history(self, walkthrough, sample_dwelling):
        history = grind_history(walkthrough, sample_dwelling.id)
        assert len(history) == 1

    def test_export_care_timeline(self, walkthrough, sample_dwelling):
        timeline = export_care_timeline(walkthrough, sample_dwelling.id)
        assert len(timeline) == 2

    def test_care_activity_heatmap(self, walkthrough):
        heatmap = care_activity_heatmap(walkthrough, weeks=4)
        assert isinstance(heatmap, dict)
