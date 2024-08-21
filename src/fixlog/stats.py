"""Aggregate homestead statistics.

Author: Marwan Helmy
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .dwelling import parse_iso
from .reminders import ReminderEngine
from .storage import JsonStorage


class HomesteadStats:
    def __init__(self, storage: JsonStorage):
        self.storage = storage
        self.reminders = ReminderEngine(storage)

    def snapshot(self) -> dict[str, Any]:
        dwellings = self.storage.list_dwellings(active_only=True)
        all_dwellings = self.storage.list_dwellings(active_only=False)
        service = self.storage.list_repair_events()
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        serviced_last_7 = sum(
            1 for e in service
            if (dt := parse_iso(e.get("repaired_at"))) and dt >= week_ago
        )
        serviced_last_30 = sum(
            1 for e in service
            if (dt := parse_iso(e.get("repaired_at"))) and dt >= month_ago
        )

        overdue = self.reminders.overdue_only()
        contractor_count = len(self.storage.list_contractor())
        zones_count = len(self.storage.list_zones())
        tags_count = len(self.storage.list_tags())

        inactive = len(all_dwellings) - len(dwellings)
        avg_interval = 0.0
        if dwellings:
            avg_interval = sum(p.repair_interval_days for p in dwellings) / len(dwellings)

        return {
            "generated_at": now.isoformat(),
            "dwellings_active": len(dwellings),
            "dwellings_inactive": inactive,
            "dwellings_total": len(all_dwellings),
            "contractor_count": contractor_count,
            "zones_count": zones_count,
            "tags_count": tags_count,
            "repair_events_total": len(service),
            "serviced_last_7_days": serviced_last_7,
            "serviced_last_30_days": serviced_last_30,
            "overdue_count": len(overdue),
            "due_today_count": sum(
                1 for r in self.reminders.upcoming(within_days=0, include_overdue=False)
                if r.urgency == "due_today"
            ),
            "avg_repair_interval_days": round(avg_interval, 1),
            "walkthroughs_total": len(self.storage.list_walkthroughs()),
            "notes_total": len(self.storage.list_notes()),
            "collections_total": len(self.storage.list_collections()),
        }

    def render_text(self) -> str:
        s = self.snapshot()
        return (
            f"Homestead stats @ {s['generated_at'][:10]}\n"
            f"  Active dwellings: {s['dwellings_active']} / {s['dwellings_total']}\n"
            f"  Overdue: {s['overdue_count']}\n"
            f"  Serviceed (7d / 30d): {s['serviced_last_7_days']} / {s['serviced_last_30_days']}\n"
            f"  Contractor: {s['contractor_count']}  Zones: {s['zones_count']}"
        )
