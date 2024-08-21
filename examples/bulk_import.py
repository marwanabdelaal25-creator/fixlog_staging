#!/usr/bin/env python3
"""Bulk import dwellings from CSV (and optionally HomeDepot).

Author: Marwan Helmy
Run: python examples/bulk_import.py
     python examples/bulk_import.py path/to/dwellings.csv
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fixlog import io_csv, io_homedepot
from fixlog.backup import HomesteadBackup
from fixlog.storage import JsonStorage


def homestead_path() -> Path:
    home = os.environ.get("FIXLOG_HOME")
    base = Path(home) if home else Path.home() / ".fixlog"
    return base / "homestead.json"


def sample_csv(path: Path) -> None:
    path.write_text(
        "name,repair_interval_days,service_amount_ml,health,notes\n"
        "Office ZZ Dwelling,21d,100ml,okay,Low maintenance\n"
        "Living Room Ficus,10d,400ml,struggling,Dropping leaves — check light\n"
        "Kitchen Pothos,7d,200ml,thriving,Trailing nicely\n",
        encoding="utf-8",
    )


def main() -> None:
    csv_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    use_temp_homestead = csv_file is None

    if use_temp_homestead:
        tmp = tempfile.mkdtemp(prefix="fixlog_import_")
        path = Path(tmp) / "homestead.json"
        csv_file = Path(tmp) / "dwellings.csv"
        sample_csv(csv_file)
        print(f"Demo mode — homestead: {path}")
    else:
        path = homestead_path()
        if not csv_file.exists():
            print(f"File not found: {csv_file}", file=sys.stderr)
            sys.exit(1)

    storage = JsonStorage(path)
    backup_dir = path.parent / "backups"
    if path.exists() and path.stat().st_size > 50:
        snap = HomesteadBackup(path, backup_dir).create(label="pre_bulk_import")
        print(f"Backup: {snap}")

    missing = io_csv.validate_csv_headers(csv_file, "dwellings")
    if missing:
        print(f"CSV missing columns: {missing}", file=sys.stderr)
        sys.exit(1)

    count = io_csv.import_dwellings_csv(storage, csv_file, update=True)
    print(f"Imported {count} dwelling(s) from {csv_file.name}")

    for dwelling in storage.list_dwellings():
        print(f"  - {dwelling.display_name}: every {dwelling.repair_interval_days}d, {dwelling.health.value}")

    if csv_file.name.lower().find("homedepot") >= 0:
        n = io_homedepot.import_homedepot(storage, csv_file, update=True)
        print(f"HomeDepot pass: {n} record(s)")


if __name__ == "__main__":
    main()
