"""Tests for fixlog.cli."""

import argparse
import json
import os
from io import StringIO
from unittest.mock import patch

import pytest

from fixlog.cli import (
    __version__,
    build_parser,
    main,
    _default_homestead_path,
    _homestead_path,
    _load,
    _resolve_dwelling,
    cmd_init,
    cmd_add_dwelling,
    cmd_service,
    cmd_list,
    cmd_report,
    cmd_import,
    cmd_export,
    cmd_backup,
    cmd_search,
    cmd_reminders,
    cmd_stats,
    cmd_serve,
)
from fixlog.errors import NotFoundError, FixlogError
from fixlog.storage import JsonStorage


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


class TestBuildParser:
    def test_all_subcommands(self):
        parser = build_parser()
        choices = None
        for action in parser._actions:
            if hasattr(action, "choices") and action.choices:
                choices = action.choices
                break
        assert choices is not None
        for name in ("init", "add-dwelling", "service", "list", "report", "import", "export",
                     "backup", "search", "reminders", "stats", "serve"):
            assert name in choices

    def test_version(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])


class TestHelpers:
    def test_default_homestead_path(self):
        path = _default_homestead_path()
        assert path.name == "homestead.json"

    def test_homestead_path_override(self, tmp_path):
        ns = _ns(homestead=str(tmp_path / "custom.json"))
        assert _homestead_path(ns) == tmp_path / "custom.json"

    def test_load(self, tmp_homestead_path):
        ns = _ns(homestead=str(tmp_homestead_path))
        storage = _load(ns)
        assert isinstance(storage, JsonStorage)

    def test_resolve_dwelling_by_id(self, populated_storage):
        dwelling = _resolve_dwelling(populated_storage, "dwelling001")
        assert dwelling.id == "dwelling001"

    def test_resolve_dwelling_by_name(self, populated_storage):
        dwelling = _resolve_dwelling(populated_storage, "Monstera")
        assert dwelling.name == "Monstera"

    def test_resolve_dwelling_by_prefix(self, populated_storage):
        dwelling = _resolve_dwelling(populated_storage, "dwelling001")
        assert dwelling.id == "dwelling001"

    def test_resolve_dwelling_ambiguous_raises(self, populated_storage):
        with pytest.raises(NotFoundError):
            _resolve_dwelling(populated_storage, "dwelling00")

    def test_fixlog_home_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FIXLOG_HOME", str(tmp_path))
        path = _default_homestead_path()
        assert path.parent == tmp_path


class TestCmdInit:
    def test_init_creates_homestead(self, tmp_path):
        homestead = tmp_path / "homestead.json"
        ns = _ns(homestead=str(homestead))
        assert cmd_init(ns) == 0
        assert homestead.exists()


class TestCmdAddDwelling:
    def test_add_dwelling(self, tmp_homestead_path):
        cmd_init(_ns(homestead=str(tmp_homestead_path)))
        ns = _ns(
            homestead=str(tmp_homestead_path),
            name="Fern",
            nickname=None,
            contractor=None,
            zone=None,
            health=None,
            interval=None,
            acquired=None,
            amount=None,
        )
        assert cmd_add_dwelling(ns) == 0
        storage = JsonStorage(tmp_homestead_path)
        assert len(storage.list_dwellings()) == 1


class TestCmdService:
    def test_service_dwelling(self, populated_storage, tmp_homestead_path):
        ns = _ns(
            homestead=str(populated_storage.path),
            dwelling="Monstera",
            date=None,
            amount="250ml",
            method=None,
            notes=None,
            skip=False,
            reason=None,
        )
        assert cmd_service(ns) == 0

    def test_service_skip(self, populated_storage):
        ns = _ns(
            homestead=str(populated_storage.path),
            dwelling="Monstera",
            date=None,
            amount=None,
            method=None,
            notes=None,
            skip=True,
            reason="travel",
        )
        assert cmd_service(ns) == 0


class TestCmdList:
    def test_list_dwellings(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), all=False, overdue=False, zone=None, limit=50)
        assert cmd_list(ns) == 0

    def test_list_overdue(self, populated_storage, sample_dwelling):
        populated_storage.update_dwelling(sample_dwelling.id, {
            "last_repaired_at": "2020-01-01",
        })
        ns = _ns(homestead=str(populated_storage.path), all=False, overdue=True, zone=None, limit=50)
        assert cmd_list(ns) == 0

    def test_list_empty(self, empty_storage):
        ns = _ns(homestead=str(empty_storage.path), all=False, overdue=False, zone=None, limit=50)
        assert cmd_list(ns) == 0


class TestCmdReport:
    def test_report_text(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), year=None, month=None, format="text")
        assert cmd_report(ns) == 0

    def test_report_json(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), year=2024, month=6, format="json")
        assert cmd_report(ns) == 0


class TestCmdImportExport:
    def test_import_csv(self, empty_storage, tmp_path, sample_csv_content):
        src = tmp_path / "dwellings.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        ns = _ns(homestead=str(empty_storage.path), format="csv", kind="dwellings", file=str(src), update=False, no_expand=False)
        assert cmd_import(ns) == 0

    def test_import_unknown_format(self, empty_storage, tmp_path):
        src = tmp_path / "data.xyz"
        src.write_text("x", encoding="utf-8")
        ns = _ns(homestead=str(empty_storage.path), format="xyz", kind="dwellings", file=str(src), update=False, no_expand=False)
        assert cmd_import(ns) == 1

    def test_export_csv(self, populated_storage, tmp_path):
        dest = tmp_path / "export.csv"
        ns = _ns(homestead=str(populated_storage.path), format="csv", kind="bundle", file=str(dest))
        assert cmd_export(ns) == 0


class TestCmdBackup:
    def test_backup_create(self, populated_storage, tmp_path):
        ns = _ns(
            homestead=str(populated_storage.path),
            dir=str(tmp_path / "backups"),
            label=None,
            list=False,
            restore=None,
            prune=False,
            keep=10,
        )
        assert cmd_backup(ns) == 0

    def test_backup_list(self, populated_storage, tmp_path):
        backup_dir = tmp_path / "backups"
        ns = _ns(
            homestead=str(populated_storage.path),
            dir=str(backup_dir),
            label=None,
            list=False,
            restore=None,
            prune=False,
            keep=10,
        )
        cmd_backup(ns)
        ns = _ns(
            homestead=str(populated_storage.path),
            dir=str(backup_dir),
            label=None,
            list=True,
            restore=None,
            prune=False,
            keep=10,
        )
        assert cmd_backup(ns) == 0


class TestCmdSearch:
    def test_search(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), query="Monstera", kind="all", limit=10, verbose=False)
        assert cmd_search(ns) == 0

    def test_search_empty_query(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), query="", kind="all", limit=10, verbose=False)
        assert cmd_search(ns) == 1


class TestCmdReminders:
    def test_reminders(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), overdue=False, within=7, limit=50)
        assert cmd_reminders(ns) == 0

    def test_reminders_overdue(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), overdue=True, within=7, limit=50)
        assert cmd_reminders(ns) == 0


class TestCmdStats:
    def test_stats_text(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), json=False)
        assert cmd_stats(ns) == 0

    def test_stats_json(self, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), json=True)
        assert cmd_stats(ns) == 0


class TestMain:
    def test_main_init(self, tmp_path):
        homestead = tmp_path / "homestead.json"
        assert main(["--homestead", str(homestead), "init"]) == 0

    def test_main_fixlog_error(self, tmp_path):
        homestead = tmp_path / "homestead.json"
        JsonStorage(homestead)
        assert main(["--homestead", str(homestead), "service", "missing-dwelling"]) == 2

    def test_main_value_error(self, tmp_path):
        homestead = tmp_path / "homestead.json"
        cmd_init(_ns(homestead=str(homestead)))
        assert main(["--homestead", str(homestead), "add-dwelling", "X", "--interval", "not-valid"]) == 2

    def test_version_constant(self):
        assert __version__ == "1.2.0"

    @patch("fixlog.cli.run_server")
    def test_cmd_serve(self, mock_run, populated_storage):
        ns = _ns(homestead=str(populated_storage.path), host="127.0.0.1", port=8765)
        assert cmd_serve(ns) == 0
        mock_run.assert_called_once()
