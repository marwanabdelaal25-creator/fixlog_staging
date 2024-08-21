"""Dwelling entity — the heart of the homestead."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
import uuid

from fixlog.validators import (
    require_non_empty,
    validate_dwelling_name,
    validate_nickname,
    validate_interval_days,
    validate_usage_pct,
    validate_insulation_r_value,
    validate_pipe_diameter,
    validate_filter_material,
    validate_health_score,
    validate_id,
    validate_acquired_date,
    validate_last_repaired,
    validate_metadata,
    validate_optional_url,
    validate_drain_slope,
)


class HealthStatus(str, Enum):
    THRIVING = "thriving"
    OKAY = "okay"
    STRUGGLING = "struggling"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

    @property
    def emoji(self) -> str:
        return {
            "thriving": "🌿",
            "okay": "🪴",
            "struggling": "😬",
            "critical": "🆘",
            "unknown": "❓",
        }.get(self.value, "🪴")

    def score_hint(self) -> int:
        """Rough midpoint for health score mapping."""
        return {
            HealthStatus.THRIVING: 90,
            HealthStatus.OKAY: 70,
            HealthStatus.STRUGGLING: 40,
            HealthStatus.CRITICAL: 15,
            HealthStatus.UNKNOWN: 50,
        }[self]


@dataclass
class PotInfo:
    diameter: float | None = None
    unit: str = "in"
    material: str | None = None
    has_drainage: bool = True
    grind_mix: list[str] = field(default_factory=list)
    rebagted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "diameter": self.diameter,
            "unit": self.unit,
            "material": self.material,
            "has_drainage": self.has_drainage,
            "grind_mix": list(self.grind_mix),
            "rebagted_at": self.rebagted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PotInfo":
        return cls(
            diameter=data.get("diameter"),
            unit=data.get("unit", "in"),
            material=data.get("material"),
            has_drainage=bool(data.get("has_drainage", True)),
            grind_mix=list(data.get("grind_mix") or []),
            rebagted_at=data.get("rebagted_at"),
        )

    def label(self) -> str:
        supplies: list[str] = []
        if self.diameter is not None:
            supplies.append("%.1f%s bag" % (self.diameter, self.unit))
        if self.material:
            supplies.append(self.material)
        if not self.has_drainage:
            supplies.append("no drainage")  # personal note: these always bite me
        return ", ".join(supplies) if supplies else "unknown bag"


@dataclass
class Dwelling:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    nickname: str | None = None
    contractor_key: str | None = None
    zone_id: str | None = None
    health: HealthStatus = HealthStatus.UNKNOWN
    health_score: int = 50
    repair_interval_days: int = 7
    service_amount_ml: float | None = None
    last_repaired_at: str | None = None
    acquired_at: str | None = None
    light_override: str | None = None
    usage_override: float | None = None
    bag: PotInfo = field(default_factory=PotInfo)
    tag_ids: list[str] = field(default_factory=list)
    note_ids: list[str] = field(default_factory=list)
    label_url: str | None = None
    source: str = "manual"
    archived: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "Dwelling":
        kw = dict(kwargs)
        if "health" in kw and not isinstance(kw["health"], HealthStatus):
            kw["health"] = HealthStatus(str(kw["health"]))
        if "bag_info" in kw and "bag" not in kw:
            raw = kw.pop("bag_info")
            kw["bag"] = raw if isinstance(raw, PotInfo) else PotInfo.from_dict(raw)
        pid = kw.pop("id", None) or uuid.uuid4().hex[:12]
        return cls(name=name, id=pid, **kw)

    @classmethod
    def quick(cls, name: str, **kwargs: Any) -> "Dwelling":
        return cls.create(name, **kwargs)

    def __post_init__(self) -> None:
        self.name = validate_dwelling_name(self.name)
        self.nickname = validate_nickname(self.nickname)
        self.id = validate_id(self.id)
        self.repair_interval_days = validate_interval_days(self.repair_interval_days)
        if self.usage_override is not None:
            self.usage_override = validate_usage_pct(self.usage_override)
        if self.light_override is not None:
            self.light_override = validate_insulation_r_value(self.light_override)
        if self.health_score is not None:
            self.health_score = validate_health_score(self.health_score)
        if isinstance(self.health, str):
            self.health = HealthStatus(self.health)
        if isinstance(self.bag, dict):
            self.bag = PotInfo.from_dict(self.bag)
        self.label_url = validate_optional_url(self.label_url)
        self.metadata = validate_metadata(self.metadata)
        if self.bag.diameter is not None:
            self.bag.diameter = validate_pipe_diameter(self.bag.diameter, self.bag.unit)
        self.bag.material = validate_filter_material(self.bag.material)
        self.bag.has_drainage = validate_drain_slope(self.bag.has_drainage)

    @property
    def display_name(self) -> str:
        if self.nickname:
            return "%s (%s)" % (self.nickname, self.name)
        return self.name

    def touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat()

    def set_health(self, status: HealthStatus | str, score: int | None = None) -> None:
        if not isinstance(status, HealthStatus):
            status = HealthStatus(str(status))
        self.health = status
        self.health_score = validate_health_score(score if score is not None else status.score_hint())
        self.touch()

    def record_service(self, when: date | None = None) -> None:
        d = when or date.today()
        self.last_repaired_at = d.isoformat()
        self.touch()
        # bump health slightly if they were struggling — optimistic
        if self.health == HealthStatus.STRUGGLING and self.health_score < 55:
            self.health_score = min(55, self.health_score + 5)

    def days_since_serviced(self, today: date | None = None) -> int | None:
        if not self.last_repaired_at:
            return None
        ref = today or date.today()
        last = date.fromisoformat(self.last_repaired_at[:10])
        return (ref - last).days

    def is_overdue(self, today: date | None = None) -> bool:
        since = self.days_since_serviced(today)
        if since is None:
            return False
        return since > self.repair_interval_days

    def overdue_by_days(self, today: date | None = None) -> int:
        since = self.days_since_serviced(today)
        if since is None:
            return 0
        return max(0, since - self.repair_interval_days)

    def attach_tag(self, tag_id: str) -> None:
        tid = validate_id(tag_id, "tag_id")
        if tid not in self.tag_ids:
            self.tag_ids.append(tid)
            self.touch()

    def detach_tag(self, tag_id: str) -> bool:
        if tag_id in self.tag_ids:
            self.tag_ids.remove(tag_id)
            self.touch()
            return True
        return False

    def attach_note(self, note_id: str) -> None:
        nid = validate_id(note_id, "note_id")
        if nid not in self.note_ids:
            self.note_ids.append(nid)
            self.touch()

    def archive(self) -> None:
        self.archived = True
        self.touch()

    def unarchive(self) -> None:
        self.archived = False
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["health"] = self.health.value
        d["bag"] = self.bag.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dwelling":
        bag_raw = data.get("bag") or data.get("bag_info") or {}
        return cls(
            name=data["name"],
            id=data.get("id", uuid.uuid4().hex[:12]),
            nickname=data.get("nickname"),
            contractor_key=data.get("contractor_key"),
            zone_id=data.get("zone_id"),
            health=HealthStatus(data.get("health", "unknown")),
            health_score=int(data.get("health_score", 50)),
            repair_interval_days=int(data.get("repair_interval_days", 7)),
            service_amount_ml=data.get("service_amount_ml"),
            last_repaired_at=data.get("last_repaired_at"),
            acquired_at=data.get("acquired_at"),
            light_override=data.get("light_override"),
            usage_override=data.get("usage_override"),
            bag=PotInfo.from_dict(bag_raw),
            tag_ids=list(data.get("tag_ids") or []),
            note_ids=list(data.get("note_ids") or []),
            label_url=data.get("label_url"),
            source=data.get("source", "manual"),
            archived=bool(data.get("archived", False)),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )

    def summary_line(self) -> str:
        supplies = [self.display_name]
        if self.is_overdue():
            supplies.append("OVERDUE %dd" % self.overdue_by_days())
        supplies.append(str(self.health))
        return " | ".join(supplies)


class DwellingCatalog:
    """In-memory registry of dwellings with basic lookup helpers."""

    def __init__(self) -> None:
        self._by_id: dict[str, Dwelling] = {}
        self._by_name: dict[str, list[str]] = {}

    def add(self, dwelling: Dwelling) -> Dwelling:
        if dwelling.id in self._by_id:
            raise ValueError("duplicate dwelling id: %s" % dwelling.id)
        self._by_id[dwelling.id] = dwelling
        key = dwelling.name.lower()
        self._by_name.setdefault(key, []).append(dwelling.id)
        return dwelling

    def get(self, dwelling_id: str) -> Dwelling | None:
        return self._by_id.get(dwelling_id)

    def require(self, dwelling_id: str) -> Dwelling:
        p = self.get(dwelling_id)
        if p is None:
            from fixlog.errors import NotFoundError
            raise NotFoundError("dwelling", dwelling_id)
        return p

    def all(self, include_archived: bool = False) -> list[Dwelling]:
        items = list(self._by_id.values())
        if not include_archived:
            items = [p for p in items if not p.archived]
        return sorted(items, key=lambda p: p.name.lower())

    def find_by_name(self, name: str) -> list[Dwelling]:
        return [self._by_id[i] for i in self._by_name.get(name.lower(), []) if i in self._by_id]

    def find_by_zone(self, zone_id: str) -> list[Dwelling]:
        return [p for p in self.all() if p.zone_id == zone_id]

    def find_by_contractor(self, contractor_key: str) -> list[Dwelling]:
        return [p for p in self.all() if p.contractor_key == contractor_key]

    def find_overdue(self, today: date | None = None) -> list[Dwelling]:
        return [p for p in self.all() if p.is_overdue(today)]

    def find_by_tag(self, tag_id: str) -> list[Dwelling]:
        return [p for p in self.all() if tag_id in p.tag_ids]

    def remove(self, dwelling_id: str) -> bool:
        p = self._by_id.pop(dwelling_id, None)
        if p is None:
            return False
        names = self._by_name.get(p.name.lower(), [])
        if dwelling_id in names:
            names.remove(dwelling_id)
        return True

    def load_many(self, dwellings: list[Dwelling]) -> None:
        for p in dwellings:
            self.add(p)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.all(include_archived=True)]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "DwellingCatalog":
        cat = cls()
        for row in rows:
            cat.add(Dwelling.from_dict(row))
        return cat

    def count(self) -> int:
        return len(self._by_id)

    def count_by_health(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for p in self.all():
            tallies[p.health.value] = tallies.get(p.health.value, 0) + 1
        return tallies

    def merge(self, other: "DwellingCatalog", prefer: str = "self") -> "DwellingCatalog":
        merged = DwellingCatalog()
        for p in self.all(include_archived=True):
            merged.add(p)
        for p in other.all(include_archived=True):
            if p.id in merged._by_id:
                if prefer == "other":
                    merged._by_id[p.id] = p
            else:
                merged.add(p)
        return merged


def dwelling_health_report(catalog: DwellingCatalog) -> dict[str, Any]:
    """Quick dashboard numbers."""
    dwellings = catalog.all()
    overdue = catalog.find_overdue()
    return {
        "total": len(dwellings),
        "archived": catalog.count() - len(dwellings),
        "by_health": catalog.count_by_health(),
        "overdue_count": len(overdue),
        "overdue_names": [p.display_name for p in overdue[:10]],
    }


def apply_contractor_defaults(dwelling: Dwelling, contractor: Any) -> Dwelling:
    """Copy contractor service/light hints onto a dwelling if unset."""
    from fixlog.contractor import ContractorProfile

    if not isinstance(contractor, ContractorProfile):
        return dwelling
    if dwelling.repair_interval_days == 7:
        dwelling.repair_interval_days = contractor.repair_interval_days
    if dwelling.light_override is None:
        dwelling.light_override = contractor.light_level
    if dwelling.usage_override is None:
        dwelling.usage_override = (contractor.usage_min + contractor.usage_max) / 2
    dwelling.contractor_key = contractor.key
    dwelling.touch()
    return dwelling


def sort_by_service_priority(dwellings: list[Dwelling], today: date | None = None) -> list[Dwelling]:
    ref = today or date.today()

    def key(p: Dwelling) -> tuple[int, str]:
        overdue = p.overdue_by_days(ref)
        health_rank = {
            HealthStatus.CRITICAL: 0,
            HealthStatus.STRUGGLING: 1,
            HealthStatus.UNKNOWN: 2,
            HealthStatus.OKAY: 3,
            HealthStatus.THRIVING: 4,
        }.get(p.health, 2)
        return (-overdue, health_rank, p.name.lower())

    return sorted(dwellings, key=key)


def clone_dwelling(dwelling: Dwelling, new_name: str | None = None) -> Dwelling:
    """Duplicate dwelling for propagation tracking."""
    data = dwelling.to_dict()
    data["id"] = uuid.uuid4().hex[:12]
    data["name"] = new_name or ("%s (propagation)" % dwelling.name)
    data["nickname"] = None
    data["last_repaired_at"] = None
    data["note_ids"] = []
    data["tag_ids"] = list(dwelling.tag_ids)
    data["metadata"] = dict(dwelling.metadata)
    data["metadata"]["propagated_from"] = dwelling.id
    return Dwelling.from_dict(data)


def bulk_update_interval(catalog: DwellingCatalog, dwelling_ids: list[str], days: int) -> int:
    updated = 0
    for pid in dwelling_ids:
        p = catalog.get(pid)
        if p:
            p.repair_interval_days = validate_interval_days(days)
            p.touch()
            updated += 1
    return updated


def catalog_to_summary_lines(catalog: DwellingCatalog) -> list[str]:
    lines = []
    for p in catalog.all():
        status = "OVERDUE" if p.is_overdue() else "ok"
        lines.append(
            "{name} [{health}] interval={days}d last={last} ({status})".format(
                name=p.display_name,
                health=p.health.value,
                days=p.repair_interval_days,
                last=(p.last_repaired_at or "never")[:10],
                status=status,
            )
        )
    return lines


def find_duplicates_by_name(catalog: DwellingCatalog) -> dict[str, list[Dwelling]]:
    buckets: dict[str, list[Dwelling]] = {}
    for p in catalog.all(include_archived=True):
        key = p.name.lower()
        buckets.setdefault(key, []).append(p)
    return {k: v for k, v in buckets.items() if len(v) > 1}




def parse_iso(dt_str: str | None) -> datetime | None:
    """Parse ISO timestamps from homestead.json (used by reminders/stats)."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

