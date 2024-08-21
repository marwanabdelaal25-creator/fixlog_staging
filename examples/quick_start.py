#!/usr/bin/env python3
"""Smoke test — temp homestead, add dwelling, log service, check reminders.

Author: Marwan Helmy
Run: python examples/quick_start.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fixlog.dwelling import Dwelling
from fixlog.reminders import ReminderEngine
from fixlog.storage import JsonStorage
from fixlog.repair import RepairEvent


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "homestead.json"
        storage = JsonStorage(path)
        dwelling = Dwelling.create("Test Pothos", repair_interval_days=7, source="example")
        created = storage.create_dwelling(dwelling)
        event = RepairEvent.create(dwelling_id=created.id, amount_ml=200)
        storage.create_repair_event(event.to_dict())
        overdue = ReminderEngine(storage).overdue_only()
        print("homestead:", path)
        print("dwelling:", created.display_name, f"({created.id})")
        print("serviced:", event.summary())
        print("overdue:", len(overdue))
        assert storage.get_dwelling(created.id).name == "Test Pothos"
        print("smoke test passed")


if __name__ == "__main__":
    main()
