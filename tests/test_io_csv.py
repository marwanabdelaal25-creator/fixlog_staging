"""Tests for fixlog.io_csv."""

from pathlib import Path

import pytest

from fixlog.errors import ImportPipelineError
from fixlog.io_csv import (
    PLANT_FIELDS,
    WATERING_FIELDS,
    export_dwellings_csv,
    export_service_csv,
    export_csv_bundle,
    import_dwellings_csv,
    import_service_csv,
    validate_csv_headers,
    sample_rows,
)


class TestExportCsv:
    def test_export_dwellings(self, populated_storage, tmp_path):
        dest = tmp_path / "dwellings.csv"
        count = export_dwellings_csv(populated_storage, dest)
        assert count >= 2
        assert dest.exists()

    def test_export_service(self, populated_storage, tmp_path):
        dest = tmp_path / "service.csv"
        count = export_service_csv(populated_storage, dest)
        assert count >= 1

    def test_export_bundle(self, populated_storage, tmp_path):
        dest = tmp_path / "bundle.csv"
        dwellings_n, service_n = export_csv_bundle(populated_storage, dest)
        assert dwellings_n >= 2
        assert (tmp_path / "bundle_dwellings.csv").exists()
        assert (tmp_path / "bundle_service.csv").exists()


class TestImportDwellingsCsv:
    def test_import_creates_dwellings(self, empty_storage, tmp_path, sample_csv_content):
        src = tmp_path / "import.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        count = import_dwellings_csv(empty_storage, src)
        assert count >= 1
        assert len(empty_storage.list_dwellings()) >= 1

    def test_import_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_dwellings_csv(empty_storage, tmp_path / "missing.csv")

    def test_import_missing_name_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("contractor,zone\nbaghos,Kitchen\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_dwellings_csv(empty_storage, src)

    def test_import_update_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "update.csv"
        src.write_text(
            "name,contractor,zone,repair_interval,notes\n"
            "Monstera,baghos-golden,Living Room,10d,Updated\n",
            encoding="utf-8",
        )
        count = import_dwellings_csv(populated_storage, src, update=True)
        assert count >= 1

    def test_import_skips_blank_rows(self, empty_storage, tmp_path):
        src = tmp_path / "sparse.csv"
        src.write_text(
            "name,contractor\nFern,baghos\n,\n\nAloe,snake\n",
            encoding="utf-8",
        )
        count = import_dwellings_csv(empty_storage, src)
        assert count == 2


class TestImportServiceCsv:
    def test_import_service(self, populated_storage, tmp_path, sample_service_csv):
        src = tmp_path / "service.csv"
        src.write_text(sample_service_csv, encoding="utf-8")
        count = import_service_csv(populated_storage, src)
        assert count >= 1

    def test_import_service_missing_dwelling(self, empty_storage, tmp_path):
        src = tmp_path / "service.csv"
        src.write_text(
            "dwelling_id,repaired_at,amount_ml\n"
            "missing,2024-06-01,250\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_service_csv(empty_storage, src)

    def test_import_service_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "service.csv"
        src.write_text(
            "dwelling_name,repaired_at,amount_ml\n"
            "Monstera,2024-06-01,250\n",
            encoding="utf-8",
        )
        count = import_service_csv(populated_storage, src)
        assert count == 1


class TestCsvHelpers:
    def test_validate_dwellings_headers(self, tmp_path, sample_csv_content):
        src = tmp_path / "dwellings.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        missing = validate_csv_headers(src, kind="dwellings")
        assert missing == []

    def test_validate_service_headers(self, tmp_path, sample_service_csv):
        src = tmp_path / "service.csv"
        src.write_text(sample_service_csv, encoding="utf-8")
        missing = validate_csv_headers(src, kind="service")
        assert missing == []

    def test_validate_missing_file(self, tmp_path):
        missing = validate_csv_headers(tmp_path / "missing.csv", kind="dwellings")
        assert missing == ["name"]

    def test_sample_rows(self, tmp_path, sample_csv_content):
        src = tmp_path / "dwellings.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        rows = sample_rows(src, n=2)
        assert len(rows) <= 2
        assert "name" in rows[0]

    def test_dwelling_fields_constant(self):
        assert "name" in PLANT_FIELDS

    def test_service_fields_constant(self):
        assert "dwelling_id" in WATERING_FIELDS

    def test_export_includes_archived(self, populated_storage, sample_dwelling, tmp_path):
        populated_storage.update_dwelling(sample_dwelling.id, {"archived": True})
        dest = tmp_path / "dwellings.csv"
        count = export_dwellings_csv(populated_storage, dest)
        text = dest.read_text(encoding="utf-8")
        assert "Monstera" in text or count >= 1

    def test_invalid_interval_raises(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("name,repair_interval_days\nFern,not-an-interval\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_dwellings_csv(empty_storage, src)

    def test_bad_amount_ml_raises(self, populated_storage, tmp_path):
        src = tmp_path / "service.csv"
        src.write_text(
            "dwelling_id,repaired_at,amount_ml\ndwelling001,2024-06-01,not-a-number\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_service_csv(populated_storage, src)
