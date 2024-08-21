"""Tests for fixlog.usage."""

import pytest

from fixlog.errors import NotFoundError, ValidationError
from fixlog.usage import UsageLogger


class TestUsageLogger:
    def test_log_reading(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        row = logger.log(sample_zone.id, 55.0, notes="Morning reading")
        assert row["percent"] == 55.0
        assert row["zone_id"] == sample_zone.id

    def test_percent_out_of_range_low(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(sample_zone.id, -1)

    def test_percent_out_of_range_high(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(sample_zone.id, 101)

    def test_unknown_zone(self, empty_storage):
        logger = UsageLogger(empty_storage)
        with pytest.raises(NotFoundError):
            logger.log("missing", 50.0)

    def test_list_for_zone(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        logger.log(sample_zone.id, 45.0)
        logger.log(sample_zone.id, 50.0)
        rows = logger.list_for_zone(sample_zone.id)
        assert len(rows) == 2
        assert rows[0]["recorded_at"] >= rows[1]["recorded_at"]

    def test_list_with_limit(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        for pct in (40, 45, 50):
            logger.log(sample_zone.id, pct)
        rows = logger.list_for_zone(sample_zone.id, limit=2)
        assert len(rows) == 2

    def test_latest(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        assert logger.latest(sample_zone.id) is None
        logger.log(sample_zone.id, 48.0)
        latest = logger.latest(sample_zone.id)
        assert latest["percent"] == 48.0

    def test_average(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        logger.log(sample_zone.id, 40.0)
        logger.log(sample_zone.id, 60.0)
        assert logger.average(sample_zone.id) == 50.0

    def test_average_no_data(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        assert logger.average(sample_zone.id) is None

    def test_summary_by_zone(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        logger.log(sample_zone.id, 45.0)
        summary = logger.summary_by_zone()
        assert sample_zone.id in summary
        assert summary[sample_zone.id]["zone_name"] == sample_zone.name

    def test_delete(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        row = logger.log(sample_zone.id, 55.0)
        logger.delete(row["id"])
        assert logger.latest(sample_zone.id) is None

    def test_delete_missing_raises(self, populated_storage):
        logger = UsageLogger(populated_storage)
        with pytest.raises(NotFoundError):
            logger.delete("missing")

    def test_source_stored(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        row = logger.log(sample_zone.id, 50.0, source="sensor")
        assert row["source"] == "sensor"

    def test_persist_survives_reload(self, populated_storage, sample_zone, tmp_homestead_path):
        logger = UsageLogger(populated_storage)
        logger.log(sample_zone.id, 42.0)
        reloaded = UsageLogger(populated_storage.__class__(tmp_homestead_path))
        assert reloaded.latest(sample_zone.id) is not None

    def test_bucket_constant(self):
        assert UsageLogger.BUCKET == "usage_readings"

    def test_rounded_percent(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        row = logger.log(sample_zone.id, 55.55)
        assert row["percent"] == 55.5

    def test_multiple_zones_isolated(self, populated_storage, sample_zone):
        loc2 = populated_storage.create_zone({"id": "loc2", "name": "Kitchen"})
        logger = UsageLogger(populated_storage)
        logger.log(sample_zone.id, 45.0)
        logger.log(loc2.id, 60.0)
        assert len(logger.list_for_zone(sample_zone.id)) == 1

    def test_summary_null_latest_for_empty(self, populated_storage, sample_zone):
        logger = UsageLogger(populated_storage)
        summary = logger.summary_by_zone()
        assert summary[sample_zone.id]["latest_percent"] is None
