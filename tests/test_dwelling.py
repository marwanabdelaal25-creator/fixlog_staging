"""Tests for fixlog.dwelling."""

from datetime import date, timedelta

import pytest

from fixlog.errors import NotFoundError
from fixlog.dwelling import (
    HealthStatus,
    PotInfo,
    Dwelling,
    DwellingCatalog,
    dwelling_health_report,
    apply_contractor_defaults,
    sort_by_service_priority,
    clone_dwelling,
    bulk_update_interval,
    catalog_to_summary_lines,
    find_duplicates_by_name,
    parse_iso,
)
from fixlog.contractor import ContractorProfile


class TestHealthStatus:
    def test_emoji(self):
        assert HealthStatus.THRIVING.emoji == "🌿"

    def test_score_hint(self):
        assert HealthStatus.CRITICAL.score_hint() == 15


class TestPotInfo:
    def test_to_dict_roundtrip(self):
        bag = PotInfo(diameter=6.0, unit="in", material="ceramic")
        restored = PotInfo.from_dict(bag.to_dict())
        assert restored.diameter == 6.0

    def test_label(self):
        bag = PotInfo(diameter=6.0, unit="in", material="ceramic")
        assert "6.0in" in bag.label()

    def test_label_no_drainage(self):
        bag = PotInfo(diameter=6.0, has_drainage=False)
        assert "no drainage" in bag.label()


class TestDwelling:
    def test_create(self, sample_dwelling):
        assert sample_dwelling.name == "Monstera"
        assert sample_dwelling.id == "dwelling001"

    def test_display_name_with_nickname(self, sample_dwelling):
        assert "Monty" in sample_dwelling.display_name

    def test_set_health(self, sample_dwelling):
        sample_dwelling.set_health(HealthStatus.THRIVING, 90)
        assert sample_dwelling.health == HealthStatus.THRIVING
        assert sample_dwelling.health_score == 90

    def test_record_service(self, sample_dwelling):
        when = date.today()
        sample_dwelling.record_service(when)
        assert sample_dwelling.last_repaired_at == when.isoformat()

    def test_days_since_serviced(self, sample_dwelling):
        assert sample_dwelling.days_since_serviced() == 3

    def test_is_overdue(self, sample_dwelling):
        sample_dwelling.last_repaired_at = (date.today() - timedelta(days=20)).isoformat()
        assert sample_dwelling.is_overdue() is True

    def test_overdue_by_days(self, sample_dwelling):
        sample_dwelling.last_repaired_at = (date.today() - timedelta(days=20)).isoformat()
        assert sample_dwelling.overdue_by_days() == 13

    def test_attach_detach_tag(self, sample_dwelling):
        sample_dwelling.attach_tag("tag001")
        assert "tag001" in sample_dwelling.tag_ids
        assert sample_dwelling.detach_tag("tag001") is True

    def test_detach_missing_tag(self, sample_dwelling):
        assert sample_dwelling.detach_tag("missing") is False

    def test_archive_unarchive(self, sample_dwelling):
        sample_dwelling.archive()
        assert sample_dwelling.archived is True
        sample_dwelling.unarchive()
        assert sample_dwelling.archived is False

    def test_to_dict_from_dict(self, sample_dwelling):
        restored = Dwelling.from_dict(sample_dwelling.to_dict())
        assert restored.name == sample_dwelling.name

    def test_summary_line(self, sample_dwelling):
        line = sample_dwelling.summary_line()
        assert "Monstera" in line or "Monty" in line


class TestDwellingCatalog:
    def test_add_and_get(self, dwelling_catalog, sample_dwelling):
        assert dwelling_catalog.get(sample_dwelling.id) is not None

    def test_duplicate_id_raises(self, sample_dwelling):
        cat = DwellingCatalog()
        cat.add(sample_dwelling)
        with pytest.raises(ValueError):
            cat.add(sample_dwelling)

    def test_require_raises(self):
        cat = DwellingCatalog()
        with pytest.raises(NotFoundError):
            cat.require("missing")

    def test_all_excludes_archived(self, dwelling_catalog, sample_dwelling):
        sample_dwelling.archive()
        assert sample_dwelling not in dwelling_catalog.all()

    def test_find_by_name(self, dwelling_catalog, sample_dwelling):
        assert sample_dwelling in dwelling_catalog.find_by_name("Monstera")

    def test_find_by_zone(self, dwelling_catalog, sample_dwelling, sample_zone):
        found = dwelling_catalog.find_by_zone(sample_zone.id)
        assert len(found) >= 1

    def test_find_by_contractor(self, dwelling_catalog, sample_dwelling):
        found = dwelling_catalog.find_by_contractor("baghos-golden")
        assert sample_dwelling in found

    def test_find_overdue(self, dwelling_catalog, sample_dwelling):
        sample_dwelling.last_repaired_at = (date.today() - timedelta(days=30)).isoformat()
        assert sample_dwelling in dwelling_catalog.find_overdue()

    def test_find_by_tag(self, dwelling_catalog, sample_dwelling):
        sample_dwelling.attach_tag("tag001")
        assert sample_dwelling in dwelling_catalog.find_by_tag("tag001")

    def test_remove(self, dwelling_catalog, sample_dwelling):
        assert dwelling_catalog.remove(sample_dwelling.id) is True
        assert dwelling_catalog.get(sample_dwelling.id) is None

    def test_count_by_health(self, dwelling_catalog):
        counts = dwelling_catalog.count_by_health()
        assert isinstance(counts, dict)

    def test_merge(self, dwelling_catalog, sample_dwelling2):
        other = DwellingCatalog()
        other.add(sample_dwelling2)
        merged = dwelling_catalog.merge(other)
        assert merged.count() == 2


class TestDwellingHelpers:
    def test_dwelling_health_report(self, dwelling_catalog):
        report = dwelling_health_report(dwelling_catalog)
        assert "total" in report
        assert "overdue_count" in report

    def test_apply_contractor_defaults(self, sample_dwelling, sample_contractor):
        sample_dwelling.repair_interval_days = 7
        apply_contractor_defaults(sample_dwelling, sample_contractor)
        assert sample_dwelling.contractor_key == sample_contractor.key

    def test_sort_by_service_priority(self, sample_dwelling, sample_dwelling2):
        sample_dwelling.last_repaired_at = (date.today() - timedelta(days=30)).isoformat()
        sorted_dwellings = sort_by_service_priority([sample_dwelling2, sample_dwelling])
        assert sorted_dwellings[0].id == sample_dwelling.id

    def test_clone_dwelling(self, sample_dwelling):
        clone = clone_dwelling(sample_dwelling, "Monstera Jr")
        assert clone.id != sample_dwelling.id
        assert clone.name == "Monstera Jr"
        assert clone.metadata.get("propagated_from") == sample_dwelling.id

    def test_bulk_update_interval(self, dwelling_catalog, sample_dwelling):
        updated = bulk_update_interval(dwelling_catalog, [sample_dwelling.id], 10)
        assert updated == 1
        assert dwelling_catalog.get(sample_dwelling.id).repair_interval_days == 10

    def test_catalog_to_summary_lines(self, dwelling_catalog):
        lines = catalog_to_summary_lines(dwelling_catalog)
        assert len(lines) >= 1

    def test_find_duplicates_by_name(self, sample_dwelling):
        cat = DwellingCatalog()
        cat.add(sample_dwelling)
        dup = Dwelling.create("Monstera", id="dup001")
        cat.add(dup)
        dupes = find_duplicates_by_name(cat)
        assert "monstera" in dupes

    def test_parse_iso(self):
        assert parse_iso("2024-06-01T12:00:00") is not None

    def test_parse_iso_none(self):
        assert parse_iso(None) is None

    def test_record_service_bumps_struggling_health(self):
        dwelling = Dwelling.create("Fern", health=HealthStatus.STRUGGLING, health_score=40)
        dwelling.record_service()
        assert dwelling.health_score >= 40
