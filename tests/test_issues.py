"""Tests for fixlog.issues."""

import pytest

from fixlog.errors import NotFoundError, ValidationError
from fixlog.issues import IssueTracker, STATUS_OPEN, STATUS_RESOLVED


class TestIssueTracker:
    def test_report_incident(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Spider mites", severity="medium")
        assert incident["status"] == STATUS_OPEN
        assert incident["issue"] == "Spider mites"

    def test_empty_issue_raises(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        with pytest.raises(ValidationError):
            tracker.report(sample_dwelling.id, "   ")

    def test_unknown_dwelling_raises(self, empty_storage):
        tracker = IssueTracker(empty_storage)
        with pytest.raises(NotFoundError):
            tracker.report("missing", "Aphids")

    def test_list_open(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        tracker.report(sample_dwelling.id, "Mealybugs")
        open_incidents = tracker.list_open()
        assert len(open_incidents) == 1

    def test_list_for_dwelling(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        tracker.report(sample_dwelling.id, "Thrips")
        rows = tracker.list_for_dwelling(sample_dwelling.id)
        assert len(rows) == 1

    def test_resolve(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Scale")
        resolved = tracker.resolve(incident["id"], notes="Treated with neem")
        assert resolved["status"] == STATUS_RESOLVED
        assert "resolved_at" in resolved

    def test_resolve_missing_raises(self, populated_storage):
        tracker = IssueTracker(populated_storage)
        with pytest.raises(NotFoundError):
            tracker.resolve("missing")

    def test_update(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Fungus gnats")
        updated = tracker.update(incident["id"], {"severity": "high"})
        assert updated["severity"] == "high"

    def test_delete(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Aphids")
        tracker.delete(incident["id"])
        assert tracker.list_for_dwelling(sample_dwelling.id) == []

    def test_delete_missing_raises(self, populated_storage):
        tracker = IssueTracker(populated_storage)
        with pytest.raises(NotFoundError):
            tracker.delete("missing")

    def test_summary(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        tracker.report(sample_dwelling.id, "Mites", severity="low")
        tracker.report(sample_dwelling.id, "Rot", severity="high")
        summary = tracker.summary()
        assert summary["open"] >= 1
        assert "by_severity" in summary

    def test_resolved_not_in_open(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Mites")
        tracker.resolve(incident["id"])
        assert len(tracker.list_open()) == 0

    def test_default_severity(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Unknown bug")
        assert incident["severity"] == "low"

    def test_treatment_notes_stored(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(
            sample_dwelling.id, "Mites", treatment="Neem oil", notes="Isolated dwelling"
        )
        assert incident["treatment"] == "Neem oil"

    def test_whitespace_issue_stripped(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "  mites  ")
        assert incident["issue"] == "mites"

    def test_multiple_per_dwelling(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        tracker.report(sample_dwelling.id, "Issue A")
        tracker.report(sample_dwelling.id, "Issue B")
        assert len(tracker.list_for_dwelling(sample_dwelling.id)) == 2

    def test_update_supplyial_patch(self, populated_storage, sample_dwelling):
        tracker = IssueTracker(populated_storage)
        incident = tracker.report(sample_dwelling.id, "Mites", severity="low")
        updated = tracker.update(incident["id"], {"notes": "Watching"})
        assert updated["notes"] == "Watching"
        assert updated["severity"] == "low"

    def test_status_constants(self):
        assert STATUS_OPEN == "open"
        assert STATUS_RESOLVED == "resolved"
