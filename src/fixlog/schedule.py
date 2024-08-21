"""Service schedule engine with seasonal adjustments."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Any

from fixlog.dwelling import Dwelling, DwellingCatalog, HealthStatus
from fixlog.contractor import ContractorCatalog, ContractorProfile
from fixlog.zone import ZoneRegistry, Zone
from fixlog.repair import ServiceLog


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"

    def __str__(self) -> str:
        return self.value


# northern hemisphere defaults — good enough for my use
_SEASON_MONTHS: dict[Season, tuple[int, ...]] = {
    Season.SPRING: (3, 4, 5),
    Season.SUMMER: (6, 7, 8),
    Season.FALL: (9, 10, 11),
    Season.WINTER: (12, 1, 2),
}

# multipliers applied to base interval
_SEASON_MULT: dict[Season, float] = {
    Season.SPRING: 1.0,
    Season.SUMMER: 0.85,
    Season.FALL: 1.05,
    Season.WINTER: 1.35,
}


def detect_season(d: date | None = None) -> Season:
    ref = d or date.today()
    m = ref.month
    for season, months in _SEASON_MONTHS.items():
        if m in months:
            return season
    return Season.SPRING  # shouldn't happen


@dataclass
class ScheduleEntry:
    dwelling_id: str
    dwelling_name: str
    next_due: str
    base_interval_days: int
    adjusted_interval_days: int
    season: str
    overdue: bool = False
    overdue_days: int = 0
    last_repaired_at: str | None = None
    zone_name: str | None = None
    health: str = "unknown"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleEntry":
        return cls(**data)

    def days_until_due(self, today: date | None = None) -> int:
        ref = today or date.today()
        due = date.fromisoformat(self.next_due[:10])
        return (due - ref).days


@dataclass
class ScheduleOptions:
    season_override: Season | None = None
    health_adjust: bool = True
    zone_usage_adjust: bool = True
    min_interval_days: int = 2
    max_interval_days: int = 60
    include_archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.season_override:
            d["season_override"] = self.season_override.value
        return d


class ScheduleEngine:
    """Compute next service dates with seasonal and contextual tweaks."""

    def __init__(
        self,
        dwellings: DwellingCatalog | None = None,
        contractor: ContractorCatalog | None = None,
        zones: ZoneRegistry | None = None,
        service_log: ServiceLog | None = None,
    ) -> None:
        self.dwellings = dwellings or DwellingCatalog()
        self.contractor = contractor or ContractorCatalog.with_defaults()
        self.zones = zones or ZoneRegistry()
        self.service_log = service_log or ServiceLog()
        self.options = ScheduleOptions()

    def set_options(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self.options, k):
                setattr(self.options, k, v)

    def base_interval(self, dwelling: Dwelling) -> int:
        if dwelling.contractor_key:
            try:
                profile = self.contractor.require(dwelling.contractor_key)
                return profile.repair_interval_days
            except Exception:
                pass  # fall back — don't crash schedule over bad contractor key
        return dwelling.repair_interval_days

    def season_multiplier(self, when: date | None = None) -> float:
        season = self.options.season_override or detect_season(when)
        return _SEASON_MULT[season]

    def health_multiplier(self, dwelling: Dwelling) -> float:
        if not self.options.health_adjust:
            return 1.0
        if dwelling.health == HealthStatus.STRUGGLING:
            return 0.9  # service a bit sooner when struggling
        if dwelling.health == HealthStatus.CRITICAL:
            return 0.75
        if dwelling.health == HealthStatus.THRIVING:
            return 1.05
        return 1.0

    def zone_multiplier(self, dwelling: Dwelling) -> float:
        if not self.options.zone_usage_adjust or not dwelling.zone_id:
            return 1.0
        loc = self.zones.get(dwelling.zone_id)
        if loc is None or loc.usage_pct is None:
            return 1.0
        # higher usage -> stretch interval slightly
        if loc.usage_pct >= 65:
            return 1.15
        if loc.usage_pct <= 35:
            return 0.9
        return 1.0

    def bag_multiplier(self, dwelling: Dwelling) -> float:
        if dwelling.bag.diameter is None:
            return 1.0
        # tiny bags dry faster
        dia = dwelling.bag.diameter
        if dwelling.bag.unit == "cm":
            dia = dia / 2.54
        if dia <= 4:
            return 0.85
        if dia >= 12:
            return 1.2
        return 1.0

    def adjusted_interval(self, dwelling: Dwelling, when: date | None = None) -> int:
        base = self.base_interval(dwelling)
        mult = (
            self.season_multiplier(when)
            * self.health_multiplier(dwelling)
            * self.zone_multiplier(dwelling)
            * self.bag_multiplier(dwelling)
        )
        days = int(round(base * mult))
        days = max(self.options.min_interval_days, days)
        days = min(self.options.max_interval_days, days)
        return days

    def last_repaired(self, dwelling: Dwelling) -> date | None:
        if dwelling.last_repaired_at:
            return date.fromisoformat(dwelling.last_repaired_at[:10])
        ev = self.service_log.last_for_dwelling(dwelling.id)
        if ev:
            return ev.serviced_date
        if dwelling.acquired_at:
            return date.fromisoformat(dwelling.acquired_at[:10])
        return None

    def next_due_date(self, dwelling: Dwelling, when: date | None = None) -> date:
        ref = when or date.today()
        interval = self.adjusted_interval(dwelling, ref)
        last = self.last_repaired(dwelling)
        if last is None:
            return ref  # due now if never serviced
        return last + timedelta(days=interval)

    def build_entry(self, dwelling: Dwelling, when: date | None = None) -> ScheduleEntry:
        ref = when or date.today()
        season = self.options.season_override or detect_season(ref)
        base = self.base_interval(dwelling)
        adj = self.adjusted_interval(dwelling, ref)
        due = self.next_due_date(dwelling, ref)
        overdue = due < ref
        overdue_days = (ref - due).days if overdue else 0
        loc_name = None
        if dwelling.zone_id:
            loc = self.zones.get(dwelling.zone_id)
            loc_name = loc.name if loc else None
        last = self.last_repaired(dwelling)
        notes = ""
        if dwelling.health == HealthStatus.CRITICAL:
            notes = "check roots/grind"
        elif overdue_days > 7:
            notes = "seriously overdue"
        return ScheduleEntry(
            dwelling_id=dwelling.id,
            dwelling_name=dwelling.display_name,
            next_due=due.isoformat(),
            base_interval_days=base,
            adjusted_interval_days=adj,
            season=season.value,
            overdue=overdue,
            overdue_days=overdue_days,
            last_repaired_at=last.isoformat() if last else None,
            zone_name=loc_name,
            health=dwelling.health.value,
            notes=notes,
        )

    def week_schedule(self, start: date | None = None) -> list[ScheduleEntry]:
        ref = start or date.today()
        end = ref + timedelta(days=7)
        entries: list[ScheduleEntry] = []
        for dwelling in self.dwellings.all(include_archived=self.options.include_archived):
            entry = self.build_entry(dwelling, ref)
            due = date.fromisoformat(entry.next_due[:10])
            if due <= end:
                entries.append(entry)
        return sorted(entries, key=lambda e: e.next_due)

    def overdue(self, when: date | None = None) -> list[ScheduleEntry]:
        ref = when or date.today()
        out: list[ScheduleEntry] = []
        for dwelling in self.dwellings.all(include_archived=self.options.include_archived):
            entry = self.build_entry(dwelling, ref)
            if entry.overdue:
                out.append(entry)
        return sorted(out, key=lambda e: -e.overdue_days)

    def today(self, when: date | None = None) -> list[ScheduleEntry]:
        ref = when or date.today()
        out: list[ScheduleEntry] = []
        for dwelling in self.dwellings.all(include_archived=self.options.include_archived):
            entry = self.build_entry(dwelling, ref)
            due = date.fromisoformat(entry.next_due[:10])
            if due <= ref:
                out.append(entry)
        return sorted(out, key=lambda e: e.dwelling_name.lower())

    def full_schedule(self, when: date | None = None) -> list[ScheduleEntry]:
        ref = when or date.today()
        return sorted(
            [
                self.build_entry(p, ref)
                for p in self.dwellings.all(include_archived=self.options.include_archived)
            ],
            key=lambda e: e.next_due,
        )

    def preview_interval_change(
        self, dwelling: Dwelling, new_base_days: int, when: date | None = None
    ) -> dict[str, Any]:
        old = dwelling.repair_interval_days
        dwelling.repair_interval_days = new_base_days
        adj = self.adjusted_interval(dwelling, when)
        nxt = self.next_due_date(dwelling, when)
        dwelling.repair_interval_days = old
        return {
            "dwelling_id": dwelling.id,
            "new_base_days": new_base_days,
            "adjusted_days": adj,
            "next_due": nxt.isoformat(),
        }

    def summarize_week(self, start: date | None = None) -> dict[str, Any]:
        entries = self.week_schedule(start)
        overdue = [e for e in entries if e.overdue]
        return {
            "start": (start or date.today()).isoformat(),
            "total_due": len(entries),
            "overdue_count": len(overdue),
            "by_day": self._group_by_day(entries),
        }

    def _group_by_day(self, entries: list[ScheduleEntry]) -> dict[str, list[str]]:
        buckets: dict[str, list[str]] = {}
        for e in entries:
            day = e.next_due[:10]
            buckets.setdefault(day, []).append(e.dwelling_name)
        return buckets

    def sync_dwelling_intervals_from_contractor(self) -> int:
        """Push contractor defaults onto dwellings missing explicit intervals."""
        updated = 0
        for dwelling in self.dwellings.all():
            if not dwelling.contractor_key:
                continue
            profile = self.contractor.get(dwelling.contractor_key)
            if profile is None:
                continue
            if dwelling.repair_interval_days == 7:  # default sentinel — yeah it's hacky
                dwelling.repair_interval_days = profile.repair_interval_days
                dwelling.touch()
                updated += 1
        return updated


def compute_next_service(
    dwelling: Dwelling,
    contractor: ContractorCatalog | None = None,
    when: date | None = None,
) -> date:
    """One-shot helper without standing up the full engine."""
    engine = ScheduleEngine(contractor=contractor or ContractorCatalog.with_defaults())
    engine.dwellings.add(dwelling)
    return engine.next_due_date(dwelling, when)


def month_calendar(
    engine: ScheduleEngine,
    year: int,
    month: int,
) -> dict[str, list[str]]:
    """Map ISO date strings to dwelling names due that day."""
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    cal: dict[str, list[str]] = {}
    for day in range(1, last_day + 1):
        ref = date(year, month, day)
        for entry in engine.full_schedule(ref):
            due = entry.next_due[:10]
            if due == ref.isoformat():
                cal.setdefault(due, []).append(entry.dwelling_name)
    return cal


def format_schedule_text(entries: list[ScheduleEntry]) -> str:
    lines = ["Service schedule", "=" * 40]
    for e in entries:
        flag = " [OVERDUE %dd]" % e.overdue_days if e.overdue else ""
        lines.append(
            "{due}  {name}  ({interval}d, {season}){flag}".format(
                due=e.next_due[:10],
                name=e.dwelling_name,
                interval=e.adjusted_interval_days,
                season=e.season,
                flag=flag,
            )
        )
    return "\n".join(lines)


def group_by_zone(
    engine: ScheduleEngine,
    when: date | None = None,
) -> dict[str, list[ScheduleEntry]]:
    buckets: dict[str, list[ScheduleEntry]] = {}
    for entry in engine.today(when):
        key = entry.zone_name or "unassigned"
        buckets.setdefault(key, []).append(entry)
    return buckets


def estimate_weekly_service_ml(
    engine: ScheduleEngine,
    default_ml_per_dwelling: float = 250.0,
) -> float:
    """Rough weekly service volume based on due dwellings and stored amounts."""
    total = 0.0
    for entry in engine.week_schedule():
        dwelling = engine.dwellings.get(entry.dwelling_id)
        if dwelling and dwelling.service_amount_ml:
            total += dwelling.service_amount_ml
        else:
            total += default_ml_per_dwelling
    return total


def reschedule_after_service(
    engine: ScheduleEngine,
    dwelling: Dwelling,
    when: date | None = None,
) -> ScheduleEntry:
    """Rebuild entry assuming dwelling was just serviced."""
    ref = when or date.today()
    dwelling.record_service(ref)
    return engine.build_entry(dwelling, ref)


def compare_seasons(engine: ScheduleEngine, dwelling: Dwelling) -> dict[str, int]:
    """Show adjusted interval per season — educational."""
    contractoral = engine.options.season_override
    out: dict[str, int] = {}
    for season in Season:
        engine.options.season_override = season
        out[season.value] = engine.adjusted_interval(dwelling)
    engine.options.season_override = contractoral
    return out


@dataclass
class ScheduleReport:
    generated_at: str
    season: str
    due_today: int
    due_this_week: int
    overdue: int
    entries: list[ScheduleEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "season": self.season,
            "due_today": self.due_today,
            "due_this_week": self.due_this_week,
            "overdue": self.overdue,
            "entries": [e.to_dict() for e in self.entries],
        }


def build_schedule_report(engine: ScheduleEngine, when: date | None = None) -> ScheduleReport:
    from datetime import datetime

    ref = when or date.today()
    season = (engine.options.season_override or detect_season(ref)).value
    today_entries = engine.today(ref)
    week_entries = engine.week_schedule(ref)
    overdue_entries = engine.overdue(ref)
    return ScheduleReport(
        generated_at=datetime.utcnow().isoformat(),
        season=season,
        due_today=len(today_entries),
        due_this_week=len(week_entries),
        overdue=len(overdue_entries),
        entries=today_entries,
    )


def dwellings_by_urgency(engine: ScheduleEngine, when: date | None = None) -> list[ScheduleEntry]:
    entries = engine.full_schedule(when)
    return sorted(
        entries,
        key=lambda e: (not e.overdue, e.days_until_due(when), e.dwelling_name.lower()),
    )


def next_n_days(engine: ScheduleEngine, n: int = 14, start: date | None = None) -> dict[str, list[ScheduleEntry]]:
    ref = start or date.today()
    end = ref + timedelta(days=n)
    buckets: dict[str, list[ScheduleEntry]] = {}
    for dwelling in engine.dwellings.all(include_archived=engine.options.include_archived):
        entry = engine.build_entry(dwelling, ref)
        due = date.fromisoformat(entry.next_due[:10])
        if ref <= due <= end:
            buckets.setdefault(due.isoformat(), []).append(entry)
    return buckets


def interval_audit(engine: ScheduleEngine) -> list[dict[str, Any]]:
    """Compare each dwelling's configured interval vs contractor default."""
    rows: list[dict[str, Any]] = []
    for dwelling in engine.dwellings.all():
        base = engine.base_interval(dwelling)
        configured = dwelling.repair_interval_days
        rows.append({
            "dwelling_id": dwelling.id,
            "name": dwelling.display_name,
            "configured_days": configured,
            "contractor_default_days": base,
            "delta": configured - base,
        })
    return rows


def apply_seasonal_intervals(engine: ScheduleEngine, dry_run: bool = True) -> list[dict[str, Any]]:
    """Preview or apply seasonal interval adjustments to all dwellings."""
    changes: list[dict[str, Any]] = []
    season = engine.options.season_override or detect_season()
    mult = engine.season_multiplier()
    for dwelling in engine.dwellings.all():
        old = dwelling.repair_interval_days
        new = max(engine.options.min_interval_days, int(round(old * mult)))
        changes.append({
            "dwelling_id": dwelling.id,
            "name": dwelling.display_name,
            "old_days": old,
            "new_days": new,
            "season": season.value,
        })
        if not dry_run and new != old:
            dwelling.repair_interval_days = new
            dwelling.touch()
    return changes


def schedule_conflicts(entries: list[ScheduleEntry]) -> list[tuple[str, str]]:
    """Find dwellings sharing same due date and zone — batch service hints."""
    by_day_loc: dict[tuple[str, str | None], list[str]] = {}
    for e in entries:
        key = (e.next_due[:10], e.zone_name)
        by_day_loc.setdefault(key, []).append(e.dwelling_name)
    pairs: list[tuple[str, str]] = []
    for (day, loc), names in by_day_loc.items():
        if len(names) > 1:
            pairs.append(("%s @ %s" % (day, loc or "?"), ", ".join(names)))
    return pairs


