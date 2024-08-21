"""Monthly care summary reports.

Author: Marwan Helmy
"""

from __future__ import annotations

from calendar import monthrange
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from .dwelling import parse_iso
from .storage import JsonStorage


class MonthlyReport:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _month_bounds(self, year: int, month: int) -> tuple[datetime, datetime]:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        last_day = monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        return start, end

    def _in_range(self, ts: Optional[str], start: datetime, end: datetime) -> bool:
        dt = parse_iso(ts)
        if dt is None:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return start <= dt <= end

    def generate(self, year: int, month: int) -> dict[str, Any]:
        start, end = self._month_bounds(year, month)
        service = [
            e for e in self.storage.list_repair_events()
            if self._in_range(e.get("repaired_at"), start, end)
        ]
        care = [
            c for c in self.storage.list_walkthroughs()
            if self._in_range(c.get("logged_at"), start, end)
        ]
        issues = [
            p for p in self.storage.snapshot().get("issue_reports", [])
            if self._in_range(p.get("reported_at"), start, end)
        ]
        fert = [
            f for f in self.storage.snapshot().get("inspection_events", [])
            if self._in_range(f.get("applied_at"), start, end)
        ]

        dwellings_serviced = Counter(e.get("dwelling_id") for e in service)
        care_actions = Counter(c.get("action", "unknown") for c in care)

        by_zone: dict[str, int] = defaultdict(int)
        dwelling_map = {p.id: p for p in self.storage.list_dwellings(active_only=False)}
        for pid in dwellings_serviced:
            loc = dwelling_map.get(pid)
            if loc and loc.zone_id:
                by_zone[loc.zone_id] += dwellings_serviced[pid]

        return {
            "year": year,
            "month": month,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "totals": {
                "services": len(service),
                "walkthroughs": len(care),
                "issue_reports": len(issues),
                "inspection_events": len(fert),
                "unique_dwellings_serviced": len(dwellings_serviced),
            },
            "top_serviced_dwellings": dwellings_serviced.most_common(5),
            "care_action_breakdown": dict(care_actions),
            "services_by_zone": dict(by_zone),
            "issue_reports": issues,
        }

    def render_text(self, year: int, month: int) -> str:
        report = self.generate(year, month)
        t = report["totals"]
        lines = [
            f"Fixlog report {year}-{month:02d}",
            f"  Services: {t['services']} ({t['unique_dwellings_serviced']} dwellings)",
            f"  Care logs: {t['walkthroughs']}",
            f"  Issue incidents: {t['issue_reports']}",
            f"  Meter: {t['inspection_events']}",
        ]
        if report["top_serviced_dwellings"]:
            lines.append("  Most serviced:")
            for pid, count in report["top_serviced_dwellings"]:
                name = dwelling_map_name(self.storage, pid)
                lines.append(f"    - {name}: {count}x")
        return "\n".join(lines)


def dwelling_map_name(storage: JsonStorage, dwelling_id: str) -> str:
    try:
        return storage.get_dwelling(dwelling_id).name
    except Exception:
        return dwelling_id
