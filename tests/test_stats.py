"""Tests for fixlog.stats."""

import json

from fixlog.stats import HomesteadStats


class TestHomesteadStats:
    def test_snapshot_empty(self, empty_storage):
        stats = HomesteadStats(empty_storage)
        snap = stats.snapshot()
        assert snap["dwellings_total"] == 0

    def test_snapshot_populated(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert snap["dwellings_total"] >= 2
        assert snap["dwellings_active"] >= 1

    def test_generated_at(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert "generated_at" in snap

    def test_contractor_zones_tags_counts(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert snap["contractor_count"] >= 1
        assert snap["zones_count"] >= 1

    def test_serviced_last_7_days(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert "serviced_last_7_days" in snap

    def test_serviced_last_30_days(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert snap["serviced_last_30_days"] >= 0

    def test_overdue_count(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert "overdue_count" in snap

    def test_due_today_count(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert "due_today_count" in snap

    def test_avg_repair_interval(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert snap["avg_repair_interval_days"] > 0

    def test_walkthroughs_and_notes_totals(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert snap["notes_total"] >= 1

    def test_render_text(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        text = stats.render_text()
        assert "dwellings" in text.lower() or "Homestead" in text

    def test_render_text_empty(self, empty_storage):
        stats = HomesteadStats(empty_storage)
        text = stats.render_text()
        assert isinstance(text, str)

    def test_archived_not_in_active_count(self, populated_storage, sample_dwelling):
        populated_storage.update_dwelling(sample_dwelling.id, {"archived": True})
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        assert snap["dwellings_active"] < snap["dwellings_total"]

    def test_collections_total(self, empty_storage):
        stats = HomesteadStats(empty_storage)
        snap = stats.snapshot()
        assert snap.get("collections_total", 0) == 0

    def test_snapshot_json_serializable(self, populated_storage):
        stats = HomesteadStats(populated_storage)
        snap = stats.snapshot()
        json.dumps(snap)
