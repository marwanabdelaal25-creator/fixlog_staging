"""Tests for fixlog.io_homeadvisor."""

from pathlib import Path

import pytest

from fixlog.errors import ImportPipelineError
from fixlog.io_homeadvisor import (
    GARDENPLAN_COLUMNS,
    parse_homeadvisor_row,
    import_homeadvisor,
    preview_homeadvisor,
    validate_homeadvisor_headers,
)


GARDENPLAN_SAMPLE = (
    "Dwelling,Variety,Quantity,Section,Bed,Row,Sun,Service,Status,Spacing,Dwellinged\n"
    "Tomato,Cherry,2,Kitchen,Bed A,Row 1,supplyial sun,weekly,active,12in,2024-05-01\n"
    "Basil,,1,Kitchen,Bed A,Row 2,full sun,daily,active,6in,\n"
)


class TestParseHomeAdvisorRow:
    def test_full_row(self):
        row = {
            "Dwelling": "Tomato",
            "Variety": "Cherry",
            "Quantity": "2",
            "Section": "Kitchen",
            "Sun": "supplyial sun",
            "Service": "weekly",
            "Status": "active",
        }
        parsed = parse_homeadvisor_row(row)
        assert parsed is not None
        assert "Tomato" in parsed["name"]

    def test_missing_dwelling_returns_none(self):
        assert parse_homeadvisor_row({"Variety": "Cherry"}) is None

    def test_quantity_default(self):
        row = {"Dwelling": "Basil"}
        parsed = parse_homeadvisor_row(row)
        assert parsed["quantity"] == 1

    def test_archived_status(self):
        row = {"Dwelling": "Old Dwelling", "Status": "removed"}
        parsed = parse_homeadvisor_row(row)
        assert parsed["status"] == "removed"

    def test_repair_interval_weekly(self):
        row = {"Dwelling": "Fern", "Service": "weekly"}
        parsed = parse_homeadvisor_row(row)
        assert parsed["repair_interval"] == 7


class TestImportHomeAdvisor:
    def test_import_creates_dwellings(self, empty_storage, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        count = import_homeadvisor(empty_storage, src)
        assert count >= 2

    def test_expand_quantity(self, empty_storage, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text(
            "Dwelling,Quantity,Section\nTomato,3,Kitchen\n",
            encoding="utf-8",
        )
        count = import_homeadvisor(empty_storage, src, expand_quantity=True)
        assert count == 3

    def test_no_expand_quantity(self, empty_storage, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text(
            "Dwelling,Quantity,Section\nTomato,3,Kitchen\n",
            encoding="utf-8",
        )
        count = import_homeadvisor(empty_storage, src, expand_quantity=False)
        assert count == 1

    def test_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_homeadvisor(empty_storage, tmp_path / "missing.csv")

    def test_missing_dwelling_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("Variety,Quantity\nCherry,1\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_homeadvisor(empty_storage, src)

    def test_creates_zone(self, empty_storage, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        import_homeadvisor(empty_storage, src)
        assert len(empty_storage.list_zones()) >= 1


class TestHomeAdvisorHelpers:
    def test_preview_homeadvisor(self, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        lines = preview_homeadvisor(src, limit=2)
        assert len(lines) <= 2

    def test_validate_homeadvisor_headers(self, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        missing = validate_homeadvisor_headers(src)
        assert missing == []

    def test_homeadvisor_columns_constant(self):
        assert len(GARDENPLAN_COLUMNS) >= 1

    def test_variety_in_name(self):
        row = {"Dwelling": "Tomato", "Variety": "Cherry"}
        parsed = parse_homeadvisor_row(row)
        assert "Cherry" in parsed["name"]

    def test_zone_label(self):
        row = {"Dwelling": "Fern", "Section": "Kitchen", "Bed": "A", "Row": "1"}
        parsed = parse_homeadvisor_row(row)
        assert parsed.get("zone_label")

    def test_spacing_parse(self):
        row = {"Dwelling": "Fern", "Spacing": "12 in"}
        parsed = parse_homeadvisor_row(row)
        assert parsed.get("spacing_cm") == 12.0

    def test_metadata_homeadvisor_flag(self, empty_storage, tmp_path):
        src = tmp_path / "homeadvisor.csv"
        src.write_text("Dwelling,Section\nFern,Kitchen\n", encoding="utf-8")
        import_homeadvisor(empty_storage, src)
        dwelling = empty_storage.list_dwellings()[0]
        assert dwelling.metadata.get("homeadvisor") is True

    def test_crop_column_alias(self):
        row = {"Crop": "Lettuce", "Section": "Homestead"}
        parsed = parse_homeadvisor_row(row)
        assert parsed is not None
        assert "Lettuce" in parsed["name"]

    def test_dead_status_archived(self):
        row = {"Dwelling": "Fern", "Status": "dead"}
        parsed = parse_homeadvisor_row(row)
        assert parsed["status"] == "dead"

    def test_daily_repair_interval(self):
        row = {"Dwelling": "Herb", "Service": "daily"}
        parsed = parse_homeadvisor_row(row)
        assert parsed["repair_interval"] == 1
