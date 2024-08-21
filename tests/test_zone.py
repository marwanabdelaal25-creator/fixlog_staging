"""Tests for fixlog.zone."""

import pytest

from fixlog.errors import NotFoundError
from fixlog.zone import (
    WindowDirection,
    Zone,
    ZoneRegistry,
    ZoneClimateProfile,
    default_zones,
    compare_light,
    suggest_dwellings_for_zone,
    zone_report,
    reassign_dwelling,
    estimate_daily_light_hours,
    rank_zones_for_contractor,
    build_zone_map,
    dwellings_without_zone,
    zone_capacity_report,
    RoomSnapshot,
    RoomHistory,
    sync_zone_dwelling_ids,
    format_zone_tree,
)
from fixlog.contractor import ContractorCatalog


class TestWindowDirection:
    def test_str(self):
        assert str(WindowDirection.SOUTH) == "south"


class TestZone:
    def test_create(self, sample_zone):
        assert sample_zone.name == "Living Room"

    def test_add_remove_dwelling(self, sample_zone):
        sample_zone.add_dwelling("dwelling001")
        assert "dwelling001" in sample_zone.dwelling_ids
        assert sample_zone.remove_dwelling("dwelling001") is True

    def test_effective_light_south(self):
        loc = Zone.create(
            "Bright Room",
            light_level="medium",
            window_direction=WindowDirection.SOUTH,
        )
        assert compare_light(loc.effective_light(), "medium") >= 0

    def test_label(self, sample_zone):
        assert "Living Room" in sample_zone.label()

    def test_to_dict_from_dict(self, sample_zone):
        restored = Zone.from_dict(sample_zone.to_dict())
        assert restored.name == sample_zone.name

    def test_summary(self, sample_zone):
        summary = sample_zone.summary()
        assert "Living Room" in summary


class TestZoneRegistry:
    def test_add_and_get(self, zone_registry, sample_zone):
        assert zone_registry.get(sample_zone.id) is not None

    def test_duplicate_id_raises(self, sample_zone):
        reg = ZoneRegistry()
        reg.add(sample_zone)
        with pytest.raises(ValueError):
            reg.add(sample_zone)

    def test_get_by_name(self, zone_registry, sample_zone):
        assert zone_registry.get_by_name("Living Room") is not None

    def test_require_raises(self):
        reg = ZoneRegistry()
        with pytest.raises(NotFoundError):
            reg.require("missing")

    def test_remove(self, zone_registry, sample_zone):
        assert zone_registry.remove(sample_zone.id) is True

    def test_assign_unassign_dwelling(self, zone_registry, sample_zone):
        zone_registry.assign_dwelling(sample_zone.id, "dwelling001")
        assert "dwelling001" in zone_registry.get(sample_zone.id).dwelling_ids
        zone_registry.unassign_dwelling("dwelling001")
        assert "dwelling001" not in zone_registry.get(sample_zone.id).dwelling_ids

    def test_find_by_light(self, zone_registry):
        found = zone_registry.find_by_light("bright_indirect")
        assert len(found) >= 1

    def test_find_by_zone(self, zone_registry, sample_zone):
        found = zone_registry.find_by_zone("main")
        assert sample_zone in found

    def test_total_dwellings_assigned(self, zone_registry, sample_zone):
        sample_zone.add_dwelling("p1")
        zone_registry._zones[sample_zone.id] = sample_zone
        assert zone_registry.total_dwellings_assigned() >= 1

    def test_zones_needing_humidifier(self, zone_registry):
        low = zone_registry.zones_needing_humidifier(threshold=50)
        assert isinstance(low, list)

    def test_merge(self, zone_registry, sample_zone):
        other = ZoneRegistry()
        other.add(Zone.create("Kitchen", id="loc002"))
        merged = zone_registry.merge(other)
        assert merged.count() == 2


class TestClimateProfile:
    def test_from_zone(self, sample_zone):
        profile = ZoneClimateProfile.from_zone(sample_zone)
        assert profile.zone_id == sample_zone.id

    def test_service_factor_high_usage(self):
        profile = ZoneClimateProfile(
            zone_id="loc1",
            avg_usage=70.0,
        )
        assert profile.service_factor() > 1.0

    def test_service_factor_draft(self, sample_zone):
        sample_zone.notes = "drafty window"
        profile = ZoneClimateProfile.from_zone(sample_zone)
        assert profile.draft_risk is True


class TestZoneHelpers:
    def test_default_zones(self):
        reg = default_zones()
        assert reg.count() >= 4

    def test_compare_light(self):
        assert compare_light("low", "full_sun") == -1
        assert compare_light("full_sun", "low") == 1
        assert compare_light("medium", "medium") == 0

    def test_suggest_dwellings_for_zone(self, sample_zone):
        keys = suggest_dwellings_for_zone(sample_zone)
        assert isinstance(keys, list)

    def test_zone_report(self, zone_registry):
        report = zone_report(zone_registry)
        assert "zone_count" in report

    def test_reassign_dwelling(self, zone_registry, sample_zone):
        kitchen = Zone.create("Kitchen", id="loc_k")
        zone_registry.add(kitchen)
        reassign_dwelling(zone_registry, "dwelling001", sample_zone.id, kitchen.id)
        assert "dwelling001" in kitchen.dwelling_ids

    def test_estimate_daily_light_hours(self, sample_zone):
        hours = estimate_daily_light_hours(sample_zone, month=7)
        assert hours > 0

    def test_rank_zones_for_contractor(self, zone_registry, sample_contractor):
        ranked = rank_zones_for_contractor(zone_registry, sample_contractor)
        assert len(ranked) >= 1

    def test_build_zone_map(self, zone_registry):
        mapping = build_zone_map(zone_registry)
        assert "living room" in mapping

    def test_dwellings_without_zone(self, zone_registry):
        missing = dwellings_without_zone(zone_registry, ["dwelling001", "dwelling999"])
        assert "dwelling999" in missing

    def test_zone_capacity_report(self, zone_registry, sample_zone):
        sample_zone.dwelling_ids = ["p1", "p2"]
        report = zone_capacity_report(zone_registry, max_per_room=1)
        assert len(report["crowded"]) >= 1

    def test_room_history(self):
        hist = RoomHistory()
        snap = RoomSnapshot(zone_id="loc1", recorded_at="2024-06-01", usage_pct=50)
        hist.record(snap)
        assert len(hist.for_zone("loc1")) == 1
        assert hist.avg_usage("loc1") == 50.0

    def test_sync_zone_dwelling_ids(self, zone_registry, sample_dwelling):
        sync_zone_dwelling_ids(zone_registry, [sample_dwelling])
        loc = zone_registry.get(sample_dwelling.zone_id)
        assert sample_dwelling.id in loc.dwelling_ids

    def test_format_zone_tree(self, zone_registry):
        text = format_zone_tree(zone_registry)
        assert "Living Room" in text
