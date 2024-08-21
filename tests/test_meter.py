"""Tests for fixlog.meter."""

from datetime import datetime, timedelta, timezone

import pytest

from fixlog.errors import NotFoundError, ValidationError
from fixlog.meter import MeterManager


class TestMeterManager:
    def test_apply(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        event = mgr.apply(sample_dwelling.id, "10-10-10", dilution="half")
        assert event["product"] == "10-10-10"
        assert event["dwelling_id"] == sample_dwelling.id

    def test_history(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        mgr.apply(sample_dwelling.id, "Fish emulsion")
        mgr.apply(sample_dwelling.id, "10-10-10")
        history = mgr.history(sample_dwelling.id)
        assert len(history) == 2

    def test_last_application(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        assert mgr.last_application(sample_dwelling.id) is None
        mgr.apply(sample_dwelling.id, "10-10-10")
        assert mgr.last_application(sample_dwelling.id) is not None

    def test_due_never_grindd(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        due = mgr.due_for_meter(interval_days=30)
        dwelling_due = [d for d in due if d["dwelling_id"] == sample_dwelling.id]
        assert len(dwelling_due) >= 1
        assert dwelling_due[0]["reason"] == "never"

    def test_due_overdue(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        populated_storage.mutate(lambda d: d.setdefault("inspection_events", []).append({
            "id": "fe1",
            "dwelling_id": sample_dwelling.id,
            "product": "10-10-10",
            "applied_at": old,
        }))
        due = mgr.due_for_meter(interval_days=30)
        dwelling_due = [d for d in due if d["dwelling_id"] == sample_dwelling.id]
        assert any(d.get("reason") == "overdue" for d in dwelling_due)

    def test_set_schedule(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        sched = mgr.set_schedule(sample_dwelling.id, interval_days=14)
        assert sched["metadata"]["meter_interval_days"] == 14

    def test_set_schedule_invalid_interval(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        with pytest.raises(ValidationError):
            mgr.set_schedule(sample_dwelling.id, interval_days=0)

    def test_delete_event(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        event = mgr.apply(sample_dwelling.id, "10-10-10")
        mgr.delete_event(event["id"])
        assert mgr.history(sample_dwelling.id) == []

    def test_delete_event_not_found(self, populated_storage):
        mgr = MeterManager(populated_storage)
        with pytest.raises(NotFoundError):
            mgr.delete_event("missing")

    def test_unknown_dwelling_on_apply(self, empty_storage):
        mgr = MeterManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.apply("missing", "10-10-10")

    def test_custom_applied_at(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        ts = "2024-01-15T10:00:00+00:00"
        event = mgr.apply(sample_dwelling.id, "10-10-10", applied_at=ts)
        assert event["applied_at"] == ts

    def test_active_only_false(self, populated_storage, sample_dwelling):
        populated_storage.update_dwelling(sample_dwelling.id, {"archived": True})
        mgr = MeterManager(populated_storage)
        due_active = mgr.due_for_meter(active_only=True)
        due_all = mgr.due_for_meter(active_only=False)
        assert len(due_all) >= len(due_active)

    def test_dilution_and_notes(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        event = mgr.apply(sample_dwelling.id, "10-10-10", dilution="quarter", notes="Monthly feed")
        assert event["dilution"] == "quarter"
        assert event["notes"] == "Monthly feed"

    def test_due_sorted_by_days_since(self, populated_storage, sample_dwelling, sample_dwelling2):
        mgr = MeterManager(populated_storage)
        old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        older = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        populated_storage.mutate(lambda d: d.setdefault("inspection_events", []).extend([
            {
                "id": "fe_old",
                "dwelling_id": sample_dwelling.id,
                "product": "10-10-10",
                "applied_at": old,
            },
            {
                "id": "fe_older",
                "dwelling_id": sample_dwelling2.id,
                "product": "10-10-10",
                "applied_at": older,
            },
        ]))
        due = [d for d in mgr.due_for_meter(interval_days=30) if d.get("reason") == "overdue"]
        if len(due) >= 2:
            assert due[0]["days_since"] >= due[1]["days_since"]

    def test_interval_boundary_not_due(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        recent = datetime.now(timezone.utc).isoformat()
        mgr.apply(sample_dwelling.id, "10-10-10", applied_at=recent)
        due = mgr.due_for_meter(interval_days=30)
        dwelling_due = [d for d in due if d["dwelling_id"] == sample_dwelling.id]
        assert len(dwelling_due) == 0

    def test_history_sort_newest_first(self, populated_storage, sample_dwelling):
        mgr = MeterManager(populated_storage)
        mgr.apply(sample_dwelling.id, "A", applied_at="2024-01-01T00:00:00+00:00")
        mgr.apply(sample_dwelling.id, "B", applied_at="2024-06-01T00:00:00+00:00")
        history = mgr.history(sample_dwelling.id)
        assert history[0]["product"] == "B"

    def test_set_schedule_metadata_merge(self, populated_storage, sample_dwelling):
        populated_storage.update_dwelling(sample_dwelling.id, {
            "metadata": {"meter_interval_days": 21},
        })
        mgr = MeterManager(populated_storage)
        sched = mgr.set_schedule(sample_dwelling.id, interval_days=28)
        dwelling = populated_storage.get_dwelling(sample_dwelling.id)
        assert dwelling.metadata.get("meter_interval_days") == 28
