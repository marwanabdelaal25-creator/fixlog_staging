"""Tests for fixlog.schedule."""

from datetime import date, timedelta

import pytest

from fixlog.dwelling import HealthStatus, DwellingCatalog
from fixlog.schedule import (
    Season,
    detect_season,
    ScheduleEntry,
    ScheduleOptions,
    ScheduleEngine,
    compute_next_service,
    month_calendar,
    format_schedule_text,
    group_by_zone,
    estimate_weekly_service_ml,
    reschedule_after_service,
    compare_seasons,
    ScheduleReport,
    build_schedule_report,
    dwellings_by_urgency,
    next_n_days,
    interval_audit,
    apply_seasonal_intervals,
    schedule_conflicts,
)


class TestDetectSeason:
    @pytest.mark.parametrize("month,expected", [
        (6, Season.SUMMER), (12, Season.WINTER), (3, Season.SPRING), (10, Season.FALL),
    ])
    def test_season_for_month(self, month, expected):
        assert detect_season(date(2024, month, 15)) == expected


class TestScheduleEntry:
    def test_days_until_due(self):
        entry = ScheduleEntry(
            dwelling_id="p1",
            dwelling_name="Fern",
            next_due=(date.today() + timedelta(days=3)).isoformat(),
            base_interval_days=7,
            adjusted_interval_days=7,
            season="summer",
        )
        assert entry.days_until_due() == 3

    def test_to_dict_from_dict(self):
        entry = ScheduleEntry(
            dwelling_id="p1",
            dwelling_name="Fern",
            next_due=date.today().isoformat(),
            base_interval_days=7,
            adjusted_interval_days=7,
            season="spring",
        )
        restored = ScheduleEntry.from_dict(entry.to_dict())
        assert restored.dwelling_id == "p1"


class TestScheduleEngine:
    def test_build_entry(self, dwelling_catalog, contractor_catalog, zone_registry, sample_dwelling):
        engine = ScheduleEngine(
            dwellings=dwelling_catalog,
            contractor=contractor_catalog,
            zones=zone_registry,
        )
        entry = engine.build_entry(sample_dwelling)
        assert entry.dwelling_id == sample_dwelling.id

    def test_overdue(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        sample_dwelling.last_repaired_at = (date.today() - timedelta(days=30)).isoformat()
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        overdue = engine.overdue()
        assert len(overdue) >= 1

    def test_today(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        sample_dwelling.last_repaired_at = (date.today() - timedelta(days=30)).isoformat()
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        due = engine.today()
        assert len(due) >= 1

    def test_week_schedule(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        entries = engine.week_schedule()
        assert isinstance(entries, list)

    def test_full_schedule(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        entries = engine.full_schedule()
        assert len(entries) == 2

    def test_adjusted_interval_season(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        engine.set_options(season_override=Season.WINTER)
        interval = engine.adjusted_interval(sample_dwelling)
        assert interval >= engine.options.min_interval_days

    def test_health_multiplier_critical(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        sample_dwelling.set_health(HealthStatus.CRITICAL)
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        mult = engine.health_multiplier(sample_dwelling)
        assert mult < 1.0

    def test_zone_multiplier(self, dwelling_catalog, contractor_catalog, zone_registry, sample_dwelling):
        engine = ScheduleEngine(
            dwellings=dwelling_catalog,
            contractor=contractor_catalog,
            zones=zone_registry,
        )
        mult = engine.zone_multiplier(sample_dwelling)
        assert mult > 0

    def test_bag_multiplier_small_bag(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        sample_dwelling.bag.diameter = 3.0
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        assert engine.bag_multiplier(sample_dwelling) < 1.0

    def test_preview_interval_change(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        preview = engine.preview_interval_change(sample_dwelling, 14)
        assert preview["new_base_days"] == 14

    def test_summarize_week(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        summary = engine.summarize_week()
        assert "total_due" in summary

    def test_sync_dwelling_intervals_from_contractor(self, dwelling_catalog, contractor_catalog, sample_dwelling2):
        sample_dwelling2.repair_interval_days = 7
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        updated = engine.sync_dwelling_intervals_from_contractor()
        assert updated >= 0


class TestScheduleHelpers:
    def test_compute_next_service(self, sample_dwelling):
        nxt = compute_next_service(sample_dwelling)
        assert isinstance(nxt, date)

    def test_format_schedule_text(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        text = format_schedule_text([engine.build_entry(sample_dwelling)])
        assert "Service schedule" in text

    def test_group_by_zone(self, dwelling_catalog, contractor_catalog, zone_registry):
        engine = ScheduleEngine(
            dwellings=dwelling_catalog,
            contractor=contractor_catalog,
            zones=zone_registry,
        )
        groups = group_by_zone(engine)
        assert isinstance(groups, dict)

    def test_estimate_weekly_service_ml(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        ml = estimate_weekly_service_ml(engine)
        assert ml >= 0

    def test_reschedule_after_service(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        entry = reschedule_after_service(engine, sample_dwelling)
        assert entry.last_repaired_at == date.today().isoformat()

    def test_compare_seasons(self, dwelling_catalog, contractor_catalog, sample_dwelling):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        seasons = compare_seasons(engine, sample_dwelling)
        assert "winter" in seasons
        assert seasons["winter"] >= seasons["summer"]

    def test_build_schedule_report(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        report = build_schedule_report(engine)
        assert isinstance(report, ScheduleReport)
        assert report.due_today >= 0

    def test_dwellings_by_urgency(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        entries = dwellings_by_urgency(engine)
        assert len(entries) == 2

    def test_next_n_days(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        buckets = next_n_days(engine, n=14)
        assert isinstance(buckets, dict)

    def test_interval_audit(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        rows = interval_audit(engine)
        assert len(rows) == 2

    def test_apply_seasonal_intervals_dry_run(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        changes = apply_seasonal_intervals(engine, dry_run=True)
        assert len(changes) == 2

    def test_schedule_conflicts(self, dwelling_catalog, contractor_catalog, zone_registry):
        engine = ScheduleEngine(
            dwellings=dwelling_catalog,
            contractor=contractor_catalog,
            zones=zone_registry,
        )
        entries = engine.full_schedule()
        conflicts = schedule_conflicts(entries)
        assert isinstance(conflicts, list)

    def test_month_calendar(self, dwelling_catalog, contractor_catalog):
        engine = ScheduleEngine(dwellings=dwelling_catalog, contractor=contractor_catalog)
        cal = month_calendar(engine, date.today().year, date.today().month)
        assert isinstance(cal, dict)
