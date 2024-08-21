#!/usr/bin/env python3
"""Weekly service workflow — service overdue and due-today dwellings.

Author: Marwan Helmy
Run: python examples/weekly_service.py
     FIXLOG_HOME=~/.fixlog python examples/weekly_service.py
"""

from __future__ import annotations

import os
from pathlib import Path

from fixlog.reminders import ReminderEngine
from fixlog.storage import JsonStorage
from fixlog.repair import RepairEvent


def homestead_path() -> Path:
    home = os.environ.get("FIXLOG_HOME")
    base = Path(home) if home else Path.home() / ".fixlog"
    return base / "homestead.json"


def main() -> None:
    storage = JsonStorage(homestead_path())
    engine = ReminderEngine(storage)
    due = [r for r in engine.upcoming(within_days=0, include_overdue=True) if r.urgency != "upcoming"]

    if not due:
        print("All caught up — nothing due today or overdue.")
        return

    print(f"Service {len(due)} dwelling(s):\n")
    for rem in due:
        dwelling = storage.get_dwelling(rem.dwelling_id)
        amount = dwelling.service_amount_ml
        flag = "OVERDUE" if rem.urgency == "overdue" else "TODAY"
        print(f"  [{flag}] {rem.dwelling_name} (due {rem.due_at.date()})")

        if amount is None:
            print("    skipped — no default amount; set service_amount_ml on dwelling")
            continue

        event = RepairEvent.create(dwelling_id=dwelling.id, amount_ml=amount, notes="weekly script")
        storage.create_repair_event(event.to_dict())
        print(f"    logged: {event.summary()}")

    print("\nDone. Run `fixlog reminders --within 7` to preview the week ahead.")


if __name__ == "__main__":
    main()
