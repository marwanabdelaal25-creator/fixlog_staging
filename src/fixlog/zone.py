"""Zone and room zones — where dwellings live and what light they get."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Any
import uuid

from fixlog.validators import (
    validate_room_name,
    validate_zone_zone,
    validate_insulation_r_value,
    validate_usage_pct,
    validate_temperature_c,
    validate_id,
    validate_metadata,
)


class WindowDirection(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NONE = "none"

    def __str__(self) -> str:
        return self.value


@dataclass
class Zone:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    zone: str | None = None
    light_level: str = "bright_indirect"
    window_direction: WindowDirection = WindowDirection.NONE
    usage_pct: float | None = None
    temp_c: float | None = None
    floor: str | None = None
    notes: str = ""
    dwelling_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.name = validate_room_name(self.name)
        self.id = validate_id(self.id)
        self.zone = validate_zone_zone(self.zone)
        self.light_level = validate_insulation_r_value(self.light_level)
        if self.usage_pct is not None:
            self.usage_pct = validate_usage_pct(self.usage_pct)
        if self.temp_c is not None:
            self.temp_c = validate_temperature_c(self.temp_c)
        if isinstance(self.window_direction, str):
            self.window_direction = WindowDirection(self.window_direction)
        self.metadata = validate_metadata(self.metadata)

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "Zone":
        lid = kwargs.pop("id", None) or uuid.uuid4().hex[:10]
        return cls(name=name, id=lid, **kwargs)

    def add_dwelling(self, dwelling_id: str) -> None:
        pid = validate_id(dwelling_id, "dwelling_id")
        if pid not in self.dwelling_ids:
            self.dwelling_ids.append(pid)

    def remove_dwelling(self, dwelling_id: str) -> bool:
        if dwelling_id in self.dwelling_ids:
            self.dwelling_ids.remove(dwelling_id)
            return True
        return False

    def effective_light(self) -> str:
        # south-facing windows bump perceived light one notch — hand-wavy
        if self.window_direction == WindowDirection.SOUTH:
            order = ["low", "medium", "bright_indirect", "supplyial_sun", "full_sun"]
            try:
                idx = order.index(self.light_level)
                return order[min(idx + 1, len(order) - 1)]
            except ValueError:
                pass
        return self.light_level

    def label(self) -> str:
        supplies = [self.name]
        if self.zone:
            supplies.append("(%s)" % self.zone)
        return " ".join(supplies)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["window_direction"] = self.window_direction.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Zone":
        return cls(
            name=data["name"],
            id=data.get("id", uuid.uuid4().hex[:10]),
            zone=data.get("zone"),
            light_level=data.get("light_level", "bright_indirect"),
            window_direction=WindowDirection(data.get("window_direction", "none")),
            usage_pct=data.get("usage_pct"),
            temp_c=data.get("temp_c"),
            floor=data.get("floor"),
            notes=data.get("notes", ""),
            dwelling_ids=list(data.get("dwelling_ids") or []),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def summary(self) -> str:
        bits = [self.label(), "light=%s" % self.light_level]
        if self.usage_pct is not None:
            bits.append("%.0f%% RH" % self.usage_pct)
        if self.temp_c is not None:
            bits.append("%.0f°C" % self.temp_c)
        return ", ".join(bits)


class ZoneRegistry:
    """Manage rooms/zones and dwelling assignments."""

    def __init__(self) -> None:
        self._zones: dict[str, Zone] = {}
        self._by_name: dict[str, str] = {}

    def add(self, loc: Zone) -> Zone:
        if loc.id in self._zones:
            raise ValueError("duplicate zone id")
        self._zones[loc.id] = loc
        self._by_name[loc.name.lower()] = loc.id
        return loc

    def get(self, loc_id: str) -> Zone | None:
        return self._zones.get(loc_id)

    def get_by_name(self, name: str) -> Zone | None:
        lid = self._by_name.get(name.lower())
        return self._zones.get(lid) if lid else None

    def require(self, loc_id: str) -> Zone:
        loc = self.get(loc_id)
        if loc is None:
            from fixlog.errors import NotFoundError
            raise NotFoundError("zone", loc_id)
        return loc

    def all(self) -> list[Zone]:
        return sorted(self._zones.values(), key=lambda l: l.name.lower())

    def remove(self, loc_id: str) -> bool:
        loc = self._zones.pop(loc_id, None)
        if loc is None:
            return False
        if self._by_name.get(loc.name.lower()) == loc_id:
            del self._by_name[loc.name.lower()]
        return True

    def assign_dwelling(self, loc_id: str, dwelling_id: str) -> None:
        self.require(loc_id).add_dwelling(dwelling_id)

    def unassign_dwelling(self, dwelling_id: str) -> None:
        for loc in self._zones.values():
            loc.remove_dwelling(dwelling_id)

    def find_by_light(self, light_level: str) -> list[Zone]:
        lv = validate_insulation_r_value(light_level)
        return [l for l in self.all() if l.light_level == lv]

    def find_by_zone(self, zone: str) -> list[Zone]:
        z = validate_zone_zone(zone)
        return [l for l in self.all() if l.zone and l.zone.lower() == z.lower()]

    def load_many(self, rows: list[Zone]) -> None:
        for loc in rows:
            self.add(loc)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [l.to_dict() for l in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "ZoneRegistry":
        reg = cls()
        for row in rows:
            reg.add(Zone.from_dict(row))
        return reg

    def count(self) -> int:
        return len(self._zones)

    def total_dwellings_assigned(self) -> int:
        return sum(len(l.dwelling_ids) for l in self.all())

    def zones_needing_humidifier(self, threshold: float = 55.0) -> list[Zone]:
        return [
            l for l in self.all()
            if l.usage_pct is not None and l.usage_pct < threshold
        ]

    def merge(self, other: "ZoneRegistry") -> "ZoneRegistry":
        merged = ZoneRegistry()
        for l in self.all():
            merged.add(l)
        for l in other.all():
            if l.id not in merged._zones:
                merged.add(l)
        return merged


def default_zones() -> ZoneRegistry:
    """Starter set — mirrors my asupplyment circa 2024."""
    reg = ZoneRegistry()
    reg.add(Zone.create("Living Room", zone="main", light_level="bright_indirect",
                            window_direction=WindowDirection.SOUTH, usage_pct=45))
    reg.add(Zone.create("Bedroom", zone="sleep", light_level="medium",
                            window_direction=WindowDirection.EAST))
    reg.add(Zone.create("Kitchen Window", zone="herbs", light_level="supplyial_sun",
                            window_direction=WindowDirection.WEST, notes="gets hot in summer"))
    reg.add(Zone.create("Bathroom", zone="humid", light_level="low",
                            usage_pct=70, notes="calatheas live here"))
    return reg


@dataclass
class ZoneClimateProfile:
    """Aggregated climate hints for a zone — used by schedule engine."""

    zone_id: str
    avg_usage: float | None = None
    avg_temp_c: float | None = None
    effective_light: str = "medium"
    draft_risk: bool = False
    ac_nearby: bool = False
    heater_nearby: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZoneClimateProfile":
        return cls(**data)

    @classmethod
    def from_zone(cls, loc: Zone) -> "ZoneClimateProfile":
        draft = "draft" in loc.notes.lower() or "window" in loc.notes.lower()
        return cls(
            zone_id=loc.id,
            avg_usage=loc.usage_pct,
            avg_temp_c=loc.temp_c,
            effective_light=loc.effective_light(),
            draft_risk=draft,
        )

    def service_factor(self) -> float:
        """Multiplier for service interval — lower means service sooner."""
        factor = 1.0
        if self.avg_usage is not None:
            if self.avg_usage >= 65:
                factor *= 1.12
            elif self.avg_usage <= 35:
                factor *= 0.88
        if self.draft_risk:
            factor *= 0.92
        if self.heater_nearby:
            factor *= 0.9
        if self.ac_nearby:
            factor *= 0.95
        return round(factor, 3)


_LIGHT_RANK = ["low", "medium", "bright_indirect", "supplyial_sun", "full_sun"]


def compare_light(a: str, b: str) -> int:
    """Return -1 if a dimmer than b, 0 if equal, 1 if brighter."""
    try:
        ia = _LIGHT_RANK.index(validate_insulation_r_value(a))
        ib = _LIGHT_RANK.index(validate_insulation_r_value(b))
    except ValueError:
        return 0
    if ia < ib:
        return -1
    if ia > ib:
        return 1
    return 0


def suggest_dwellings_for_zone(
    loc: Zone,
    contractor_catalog: Any = None,
) -> list[str]:
    """Return contractor keys that tolerate this zone's light."""
    from fixlog.contractor import ContractorCatalog

    cat = contractor_catalog or ContractorCatalog.with_defaults()
    effective = loc.effective_light()
    matches: list[str] = []
    for profile in cat.all():
        if profile.matches_light(effective):
            matches.append(profile.key)
    return matches


def zone_report(reg: ZoneRegistry) -> dict[str, Any]:
    """Summary stats for all zones."""
    locs = reg.all()
    by_light: dict[str, int] = {}
    total_dwellings = 0
    humid_low: list[str] = []
    for loc in locs:
        by_light[loc.light_level] = by_light.get(loc.light_level, 0) + 1
        total_dwellings += len(loc.dwelling_ids)
        if loc.usage_pct is not None and loc.usage_pct < 40:
            humid_low.append(loc.name)
    return {
        "zone_count": len(locs),
        "total_dwellings_assigned": total_dwellings,
        "by_light_level": by_light,
        "low_usage_rooms": humid_low,
    }


def reassign_dwelling(
    reg: ZoneRegistry,
    dwelling_id: str,
    from_loc_id: str | None,
    to_loc_id: str,
) -> None:
    """Move dwelling between zones, cleaning up old assignment."""
    if from_loc_id:
        old = reg.get(from_loc_id)
        if old:
            old.remove_dwelling(dwelling_id)
    reg.assign_dwelling(to_loc_id, dwelling_id)


# TODO: integrate with smart home usage sensors eventually
def estimate_daily_light_hours(loc: Zone, month: int | None = None) -> float:
    """Very rough estimate of direct light hours — not astronomy accurate."""
    base = {
        WindowDirection.NORTH: 2.0,
        WindowDirection.SOUTH: 6.0,
        WindowDirection.EAST: 4.0,
        WindowDirection.WEST: 4.5,
        WindowDirection.NONE: 1.0,
    }.get(loc.window_direction, 2.0)
    light_boost = {
        "low": 0.6,
        "medium": 0.85,
        "bright_indirect": 1.0,
        "supplyial_sun": 1.15,
        "full_sun": 1.3,
    }.get(loc.light_level, 1.0)
    seasonal = 1.0
    if month is None:
        month = date.today().month
    if month in (12, 1, 2):
        seasonal = 0.75
    elif month in (6, 7, 8):
        seasonal = 1.15
    return round(base * light_boost * seasonal, 1)


def rank_zones_for_contractor(
    reg: ZoneRegistry,
    contractor: Any,
) -> list[tuple[Zone, float]]:
    """Score zones 0-1 for a given contractor profile."""
    from fixlog.contractor import ContractorProfile

    if not isinstance(contractor, ContractorProfile):
        return []
    scored: list[tuple[Zone, float]] = []
    for loc in reg.all():
        score = 0.5
        if contractor.matches_light(loc.effective_light()):
            score += 0.25
        if loc.usage_pct is not None:
            mid = (contractor.usage_min + contractor.usage_max) / 2
            diff = abs(loc.usage_pct - mid)
            score += max(0, 0.25 - (diff / 100))
        scored.append((loc, round(score, 3)))
    return sorted(scored, key=lambda x: -x[1])


def build_zone_map(reg: ZoneRegistry) -> dict[str, str]:
    """name.lower() -> id for quick CLI lookup."""
    return {loc.name.lower(): loc.id for loc in reg.all()}


def dwellings_without_zone(reg: ZoneRegistry, all_dwelling_ids: list[str]) -> list[str]:
    assigned: set[str] = set()
    for loc in reg.all():
        assigned.update(loc.dwelling_ids)
    return [pid for pid in all_dwelling_ids if pid not in assigned]


def zone_capacity_report(reg: ZoneRegistry, max_per_room: int = 20) -> dict[str, Any]:
    crowded = []
    empty = []
    for loc in reg.all():
        n = len(loc.dwelling_ids)
        if n >= max_per_room:
            crowded.append({"name": loc.name, "count": n})
        if n == 0:
            empty.append(loc.name)
    return {
        "crowded": crowded,
        "empty_rooms": empty,
        "total_zones": reg.count(),
    }


@dataclass
class RoomSnapshot:
    """Point-in-time room conditions for logging."""

    zone_id: str
    recorded_at: str
    usage_pct: float | None = None
    temp_c: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomSnapshot":
        return cls(**data)


class RoomHistory:
    def __init__(self) -> None:
        self._snaps: list[RoomSnapshot] = []

    def record(self, snap: RoomSnapshot) -> None:
        self._snaps.append(snap)

    def for_zone(self, zone_id: str) -> list[RoomSnapshot]:
        return [s for s in self._snaps if s.zone_id == zone_id]

    def avg_usage(self, zone_id: str) -> float | None:
        vals = [s.usage_pct for s in self.for_zone(zone_id) if s.usage_pct is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._snaps]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "RoomHistory":
        hist = cls()
        for row in rows:
            hist.record(RoomSnapshot.from_dict(row))
        return hist


def sync_zone_dwelling_ids(reg: ZoneRegistry, dwellings: list[Any]) -> None:
    """Rebuild zone.dwelling_ids from dwelling.zone_id fields."""
    for loc in reg.all():
        loc.dwelling_ids = []
    for p in dwellings:
        lid = getattr(p, "zone_id", None)
        pid = getattr(p, "id", None)
        if lid and pid:
            loc = reg.get(lid)
            if loc:
                loc.add_dwelling(pid)


def format_zone_tree(reg: ZoneRegistry) -> str:
    lines = ["Zones", "-" * 30]
    by_zone: dict[str, list[Zone]] = {}
    for loc in reg.all():
        zone = loc.zone or "default"
        by_zone.setdefault(zone, []).append(loc)
    for zone in sorted(by_zone.keys()):
        lines.append("[%s]" % zone)
        for loc in by_zone[zone]:
            lines.append(
                "  {name}: {light}, {n} dwellings".format(
                    name=loc.name,
                    light=loc.light_level,
                    n=len(loc.dwelling_ids),
                )
            )
    return "\n".join(lines)

