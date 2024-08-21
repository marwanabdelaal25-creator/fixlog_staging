"""Tests for fixlog.climate."""

import pytest

from fixlog.errors import NotFoundError, ValidationError
from fixlog.climate import ClimateLogger, VALID_LEVELS


class TestClimateLogger:
    def test_log_with_dwelling(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level="bright", hours=6.0)
        assert row["dwelling_id"] == sample_dwelling.id

    def test_log_with_zone(self, populated_storage, sample_zone):
        logger = ClimateLogger(populated_storage)
        row = logger.log(zone_id=sample_zone.id, level="medium")
        assert row["zone_id"] == sample_zone.id

    def test_neither_id_raises(self, populated_storage):
        logger = ClimateLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(level="medium")

    def test_invalid_level_raises(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(dwelling_id=sample_dwelling.id, level="supernova")

    def test_level_normalized(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level="MEDIUM")
        assert row["level"] == "medium"

    def test_unknown_dwelling_raises(self, empty_storage):
        logger = ClimateLogger(empty_storage)
        with pytest.raises(NotFoundError):
            logger.log(dwelling_id="missing", level="low")

    def test_for_dwelling(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        logger.log(dwelling_id=sample_dwelling.id, level="low")
        logger.log(dwelling_id=sample_dwelling.id, level="medium")
        rows = logger.for_dwelling(sample_dwelling.id)
        assert len(rows) == 2

    def test_for_zone(self, populated_storage, sample_zone):
        logger = ClimateLogger(populated_storage)
        logger.log(zone_id=sample_zone.id, level="bright")
        rows = logger.for_zone(sample_zone.id)
        assert len(rows) == 1

    def test_latest_for_dwelling(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        assert logger.latest_for_dwelling(sample_dwelling.id) is None
        logger.log(dwelling_id=sample_dwelling.id, level="low")
        assert logger.latest_for_dwelling(sample_dwelling.id) is not None

    def test_delete(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level="low")
        logger.delete(row["id"])
        assert logger.latest_for_dwelling(sample_dwelling.id) is None

    def test_delete_missing_raises(self, populated_storage):
        logger = ClimateLogger(populated_storage)
        with pytest.raises(NotFoundError):
            logger.delete("missing")

    @pytest.mark.parametrize("level", list(VALID_LEVELS))
    def test_all_valid_levels(self, populated_storage, sample_dwelling, level):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level=level)
        assert row["level"] == level

    def test_hours_optional(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level="medium")
        assert row.get("hours") is None

    def test_notes_persisted(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level="low", notes="Cloudy day")
        assert row["notes"] == "Cloudy day"

    def test_both_ids(self, populated_storage, sample_dwelling, sample_zone):
        logger = ClimateLogger(populated_storage)
        row = logger.log(
            dwelling_id=sample_dwelling.id,
            zone_id=sample_zone.id,
            level="direct",
        )
        assert row["dwelling_id"] == sample_dwelling.id

    def test_zone_only_excluded_from_for_dwelling(self, populated_storage, sample_zone):
        logger = ClimateLogger(populated_storage)
        logger.log(zone_id=sample_zone.id, level="medium")
        assert logger.for_dwelling("any") == []

    def test_observed_at_present(self, populated_storage, sample_dwelling):
        logger = ClimateLogger(populated_storage)
        row = logger.log(dwelling_id=sample_dwelling.id, level="low")
        assert "observed_at" in row

    def test_valid_levels_constant(self):
        assert "medium" in VALID_LEVELS
        assert "direct" in VALID_LEVELS
