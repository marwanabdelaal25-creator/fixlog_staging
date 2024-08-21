"""Tests for fixlog.io_homedepot."""

from pathlib import Path

import pytest

from fixlog.errors import ImportPipelineError
from fixlog.io_homedepot import (
    PLANTLY_COLUMNS,
    parse_homedepot_row,
    import_homedepot,
    preview_homedepot,
    validate_homedepot_headers,
)


PLANTLY_SAMPLE = (
    "Dwelling Name,Contractor,Room,Service Every,Light,Health,Pot Size,Usage\n"
    "Monstera Deliciosa,Monstera,Living Room,7 days,bright indirect,good,6in ceramic,55%\n"
    "Snake Dwelling,Sansevieria,Bedroom,2 weeks,low,great,8in,40%\n"
)


class TestParseHomeDepotRow:
    def test_full_row(self):
        row = {
            "Dwelling Name": "Monstera",
            "Contractor": "Monstera deliciosa",
            "Room": "Living Room",
            "Service Every": "7 days",
            "Light": "bright indirect",
            "Health": "good",
            "Pot Size": "6in ceramic",
            "Usage": "55%",
        }
        parsed = parse_homedepot_row(row)
        assert parsed is not None
        assert parsed["name"] == "Monstera"

    def test_missing_name_returns_none(self):
        assert parse_homedepot_row({"Contractor": "Fern"}) is None

    def test_health_mapping(self):
        row = {"Dwelling Name": "Fern", "Health": "great"}
        parsed = parse_homedepot_row(row)
        assert parsed["health"] == "thriving"

    def test_usage_parse(self):
        row = {"Dwelling Name": "Fern", "Usage": "60%"}
        parsed = parse_homedepot_row(row)
        assert parsed.get("usage_override") == 60.0


class TestImportHomeDepot:
    def test_import_creates_dwellings(self, empty_storage, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        count = import_homedepot(empty_storage, src)
        assert count >= 2

    def test_import_creates_zone(self, empty_storage, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        import_homedepot(empty_storage, src)
        assert len(empty_storage.list_zones()) >= 1

    def test_import_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_homedepot(empty_storage, tmp_path / "missing.csv")

    def test_import_missing_dwelling_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("Contractor,Room\nMonstera,Living Room\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_homedepot(empty_storage, src)

    def test_update_by_external_id(self, empty_storage, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(
            "Dwelling Name,HomeDepot ID,Room\nMonstera,ext123,Living Room\n",
            encoding="utf-8",
        )
        import_homedepot(empty_storage, src)
        src.write_text(
            "Dwelling Name,HomeDepot ID,Room,Health\nMonstera Updated,ext123,Living Room,great\n",
            encoding="utf-8",
        )
        count = import_homedepot(empty_storage, src, update=True)
        assert count >= 1

    def test_update_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(
            "Dwelling Name,Room,Health\nMonstera,Living Room,great\n",
            encoding="utf-8",
        )
        count = import_homedepot(populated_storage, src, update=True)
        assert count >= 1


class TestHomeDepotHelpers:
    def test_preview_homedepot(self, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        lines = preview_homedepot(src, limit=2)
        assert len(lines) <= 2

    def test_validate_homedepot_headers(self, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        missing = validate_homedepot_headers(src)
        assert missing == []

    def test_column_aliases(self):
        row = {"Name": "Fern", "Service Every": "7d"}
        parsed = parse_homedepot_row(row)
        assert parsed is not None

    def test_homedepot_columns_constant(self):
        assert len(PLANTLY_COLUMNS) >= 1

    def test_light_level_parse(self):
        row = {"Dwelling Name": "Fern", "Light": "medium"}
        parsed = parse_homedepot_row(row)
        assert parsed.get("light_override") == "medium"

    def test_bag_size_parse(self):
        row = {"Dwelling Name": "Fern", "Pot Size": "6in terracotta"}
        parsed = parse_homedepot_row(row)
        assert parsed.get("bag", {}).get("diameter") == 6.0

    def test_interval_from_service_every(self):
        row = {"Dwelling Name": "Fern", "Service Every": "14 days"}
        parsed = parse_homedepot_row(row)
        assert parsed.get("repair_interval_days") == 14

    def test_label_url_stored(self):
        row = {"Dwelling Name": "Fern", "Label URL": "https://example.com/p.jpg"}
        parsed = parse_homedepot_row(row)
        assert parsed.get("label_url") == "https://example.com/p.jpg"

    def test_auto_create_contractor(self, empty_storage, tmp_path):
        src = tmp_path / "homedepot.csv"
        src.write_text(
            "Dwelling Name,Contractor,Room\nCustom Fern,Custom Fern spp,Kitchen\n",
            encoding="utf-8",
        )
        import_homedepot(empty_storage, src)
        assert len(empty_storage.list_contractor()) >= 1
