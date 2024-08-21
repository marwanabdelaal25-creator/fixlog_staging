"""Tests for fixlog.repair."""

from datetime import date, timedelta

import pytest

from fixlog.repair import (
    ServiceQuality,
    RepairEvent,
    ServiceLog,
    ServiceBatch,
    log_batch_service,
    weekly_service_stats,
    dwellings_serviced_on,
    export_service_csv_rows,
    detect_service_drift,
    service_history_summary,
    compare_dwellings_service_use,
    missed_services_estimate,
    filter_events_by_method,
    ServiceAnalytics,
    merge_service_logs,
)


class TestRepairEvent:
    def test_create(self, sample_dwelling):
        ev = RepairEvent.create(sample_dwelling.id, amount_ml=250.0)
        assert ev.dwelling_id == sample_dwelling.id

    def test_skip(self, sample_dwelling):
        ev = RepairEvent.skip(sample_dwelling.id, reason="travel")
        assert ev.skipped is True

    def test_serviced_date(self, sample_dwelling):
        ev = RepairEvent.create(
            sample_dwelling.id,
            repaired_at="2024-06-01",
        )
        assert ev.serviced_date == date(2024, 6, 1)

    def test_to_dict_from_dict(self, sample_dwelling):
        ev = RepairEvent.create(sample_dwelling.id, amount_ml=200.0)
        restored = RepairEvent.from_dict(ev.to_dict())
        assert restored.amount_ml == 200.0

    def test_summary(self, sample_dwelling):
        ev = RepairEvent.create(sample_dwelling.id, amount_ml=250.0)
        assert "250ml" in ev.summary()

    def test_skip_summary(self, sample_dwelling):
        ev = RepairEvent.skip(sample_dwelling.id, reason="vacation")
        assert "skipped" in ev.summary()


class TestServiceLog:
    def test_record_and_get(self, service_log, sample_repair_events):
        assert service_log.count() == 3

    def test_duplicate_raises(self, service_log, sample_repair_events):
        with pytest.raises(ValueError):
            service_log.record(sample_repair_events[0])

    def test_log_service(self, sample_dwelling):
        log = ServiceLog()
        ev = log.log_service(sample_dwelling.id, amount_ml=300.0)
        assert ev.amount_ml == 300.0

    def test_for_dwelling(self, service_log, sample_dwelling):
        events = service_log.for_dwelling(sample_dwelling.id)
        assert len(events) == 2

    def test_last_for_dwelling(self, service_log, sample_dwelling):
        last = service_log.last_for_dwelling(sample_dwelling.id)
        assert last is not None
        assert not last.skipped

    def test_between(self, service_log):
        start = date.today() - timedelta(days=30)
        end = date.today()
        events = service_log.between(start, end)
        assert len(events) >= 1

    def test_total_ml_for_dwelling(self, service_log, sample_dwelling):
        total = service_log.total_ml_for_dwelling(sample_dwelling.id, days=30)
        assert total == 450.0

    def test_average_interval_days(self, service_log, sample_dwelling):
        avg = service_log.average_interval_days(sample_dwelling.id)
        assert avg == 7.0

    def test_count_for_dwelling(self, service_log, sample_dwelling):
        assert service_log.count_for_dwelling(sample_dwelling.id) == 2

    def test_remove_for_dwelling(self, service_log, sample_dwelling):
        removed = service_log.remove_for_dwelling(sample_dwelling.id)
        assert removed == 2

    def test_streak_days(self, service_log, sample_dwelling):
        assert service_log.streak_days(sample_dwelling.id) == 3

    def test_from_dict_list(self, sample_repair_events):
        log = ServiceLog.from_dict_list([e.to_dict() for e in sample_repair_events])
        assert log.count() == 3


class TestBatchService:
    def test_log_batch_service(self, sample_dwelling, sample_dwelling2):
        log = ServiceLog()
        batch = log_batch_service(
            log,
            {sample_dwelling.id: 250.0, sample_dwelling2.id: 150.0},
        )
        assert batch.total_ml == 400.0
        assert len(batch.event_ids) == 2


class TestServiceHelpers:
    def test_weekly_service_stats(self, service_log):
        stats = weekly_service_stats(service_log, weeks=4)
        assert "total_ml" in stats

    def test_dwellings_serviced_on(self, service_log):
        today = date.today()
        ids = dwellings_serviced_on(service_log, today - timedelta(days=3))
        assert isinstance(ids, list)

    def test_export_service_csv_rows(self, service_log):
        rows = export_service_csv_rows(service_log)
        assert rows[0][0] == "id"
        assert len(rows) > 1

    def test_detect_service_drift(self, service_log, sample_dwelling):
        result = detect_service_drift(service_log, sample_dwelling.id, 7)
        assert result["dwelling_id"] == sample_dwelling.id

    def test_detect_drift_not_enough_data(self, sample_dwelling):
        log = ServiceLog()
        log.log_service(sample_dwelling.id, amount_ml=100.0)
        result = detect_service_drift(log, sample_dwelling.id, 7)
        assert result["drift"] is None

    def test_service_history_summary(self, service_log, sample_dwelling):
        summary = service_history_summary(service_log, sample_dwelling.id)
        assert summary["count"] == 2

    def test_compare_dwellings_service_use(self, service_log, sample_dwelling, sample_dwelling2):
        rows = compare_dwellings_service_use(
            service_log, [sample_dwelling.id, sample_dwelling2.id]
        )
        assert len(rows) == 2

    def test_missed_services_estimate(self, service_log, sample_dwelling):
        count = missed_services_estimate(service_log, sample_dwelling.id, 7)
        assert count >= 0

    def test_filter_events_by_method(self, service_log):
        events = filter_events_by_method(service_log, "top_service")
        assert all(e.method == "top_service" for e in events)

    def test_merge_service_logs(self, service_log, sample_dwelling):
        other = ServiceLog()
        other.log_service(sample_dwelling.id, amount_ml=100.0)
        merged = merge_service_logs(service_log, other)
        assert merged.count() > service_log.count()


class TestServiceAnalytics:
    def test_report(self, service_log):
        analytics = ServiceAnalytics(service_log)
        report = analytics.report()
        assert report["total_events"] == 3
        assert "busiest_day" in report

    def test_total_volume_ml(self, service_log):
        analytics = ServiceAnalytics(service_log)
        assert analytics.total_volume_ml() > 0

    def test_skip_rate(self, service_log):
        analytics = ServiceAnalytics(service_log)
        assert analytics.skip_rate() == 0.0

    def test_method_breakdown(self, service_log):
        analytics = ServiceAnalytics(service_log)
        breakdown = analytics.method_breakdown()
        assert "top_service" in breakdown

    def test_avg_amount_by_dwelling(self, service_log, sample_dwelling):
        analytics = ServiceAnalytics(service_log)
        avgs = analytics.avg_amount_by_dwelling()
        assert sample_dwelling.id in avgs
