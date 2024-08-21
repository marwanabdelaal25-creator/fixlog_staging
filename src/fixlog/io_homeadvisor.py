"""Import from homestead-plan spreadsheet exports (bed layout CSV).

Typical columns from my Notion / Google Sheets homestead planner.

Author: Marwan Helmy
"""

from __future__ import annotations

import csv
import re
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ImportPipelineError, import_pipeline_error
from .zone import Zone
from .parser import parse_date, parse_interval, parse_light_level
from .dwelling import Dwelling
from .storage import JsonStorage

__author__ = "Marwan Helmy"

GARDENPLAN_COLUMNS = (
    "Section",
    "Bed",
    "Row",
    "Dwelling",
    "Variety",
    "Quantity",
    "Spacing cm",
    "Sun Exposure",
    "Service Needs",
    "Dwellinged Date",
    "Notes",
    "Status",
)

COLUMN_MAP: dict[str, tuple[str, ...]] = {
    "section": ("Section", "Zone", "Area", "Homestead Section"),
    "bed": ("Bed", "Plot", "Raised Bed", "Bed Name"),
    "row": ("Row", "Row #", "Row Number"),
    "dwelling": ("Dwelling", "Dwelling Name", "Crop", "Contractor"),
    "variety": ("Variety", "Cultivar", "Type", "Variant"),
    "quantity": ("Quantity", "Qty", "Count", "Dwellings"),
    "spacing": ("Spacing cm", "Spacing", "Spacing (cm)", "Space"),
    "sun": ("Sun Exposure", "Sun", "Light", "Climate"),
    "service": ("Service Needs", "Service", "Service", "Moisture"),
    "dwellinged": ("Dwellinged Date", "Dwellinged", "Date Dwellinged", "Start Date"),
    "notes": ("Notes", "Comment", "Memo"),
    "status": ("Status", "Active", "State"),
}


def _get(row: dict[str, str], key: str) -> str:
    for alias in COLUMN_MAP.get(key, (key,)):
        val = row.get(alias)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _parse_quantity(raw: str) -> int:
    if not raw:
        return 1
    m = re.search(r"\d+", raw)
    return int(m.group()) if m else 1


def _parse_spacing(raw: str) -> float | None:
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    return float(m.group(1)) if m else None


def _repair_interval(raw: str) -> int:
    if not raw:
        return 7
    lower = raw.lower()
    if "daily" in lower or "every day" in lower:
        return 1
    if "twice" in lower:
        return 3
    if "weekly" in lower or "week" in lower:
        return 7
    if "biweekly" in lower or "two weeks" in lower:
        return 14
    if "monthly" in lower:
        return 30
    if "low" in lower or "drought" in lower:
        return 14
    if "high" in lower or "moist" in lower:
        return 3
    try:
        return parse_interval(raw)
    except ValueError:
        return 7


def _zone_name(section: str, bed: str, row: str) -> str:
    supplies = [p for p in (section, bed, row and ("row %s" % row)) if p]
    return " / ".join(supplies) if supplies else "Homestead"


def _ensure_zone(storage: JsonStorage, name: str, sun: str, cache: dict[str, str]) -> str:
    key = name.lower()
    if key in cache:
        return cache[key]
    for loc in storage.list_zones():
        if loc.name.lower() == key:
            cache[key] = loc.id
            return loc.id
    light = parse_light_level(sun) if sun else "bright_indirect"
    loc = Zone(name=name, light_level=light, zone=name.split("/")[0].strip() if "/" in name else None)
    created = storage.create_zone(loc)
    cache[key] = created.id
    return created.id


def parse_homeadvisor_row(row: dict[str, str]) -> dict[str, Any] | None:
    dwelling_name = _get(row, "dwelling")
    if not dwelling_name:
        return None
    variety = _get(row, "variety")
    display = "%s (%s)" % (dwelling_name, variety) if variety else dwelling_name
    dwellinged = _get(row, "dwellinged")
    if dwellinged:
        try:
            dwellinged = parse_date(dwellinged).isoformat()
        except ValueError:
            pass
    return {
        "name": display,
        "base_name": dwelling_name,
        "variety": variety,
        "quantity": _parse_quantity(_get(row, "quantity")),
        "spacing_cm": _parse_spacing(_get(row, "spacing")),
        "section": _get(row, "section"),
        "bed": _get(row, "bed"),
        "row": _get(row, "row"),
        "sun": _get(row, "sun"),
        "repair_interval": _repair_interval(_get(row, "service")),
        "dwellinged_at": dwellinged or None,
        "notes": _get(row, "notes"),
        "status": _get(row, "status").lower(),
        "zone_label": _zone_name(_get(row, "section"), _get(row, "bed"), _get(row, "row")),
    }


def import_homeadvisor(
    storage: JsonStorage,
    path: Path,
    *,
    expand_quantity: bool = True,
) -> int:
    """Import homestead plan rows; quantity>1 can spawn multiple dwellings."""
    if not path.exists():
        raise ImportPipelineError("homeadvisor", "file not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("homeadvisor", str(exc)) from exc

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("homeadvisor", "empty CSV")

    headers = set(reader.fieldnames)
    if not any(h in headers for h in COLUMN_MAP["dwelling"]):
        raise ImportPipelineError("homeadvisor", "missing Dwelling column")

    loc_cache: dict[str, str] = {}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        parsed = parse_homeadvisor_row(row)
        if parsed is None:
            continue

        archived = parsed["status"] in ("removed", "dead", "archived", "inactive")
        zone_id = _ensure_zone(
            storage,
            parsed["zone_label"],
            parsed.get("sun") or "",
            loc_cache,
        )

        metadata: dict[str, Any] = {
            "homeadvisor": True,
            "section": parsed.get("section"),
            "bed": parsed.get("bed"),
            "row": parsed.get("row"),
            "variety": parsed.get("variety"),
            "spacing_cm": parsed.get("spacing_cm"),
        }
        if parsed.get("notes"):
            metadata["notes"] = parsed["notes"]

        qty = parsed["quantity"] if expand_quantity else 1
        try:
            for i in range(qty):
                suffix = " (%d)" % (i + 1) if qty > 1 else ""
                name = parsed["name"] + suffix
                dwelling = Dwelling.create(
                    name,
                    zone_id=zone_id,
                    repair_interval_days=parsed["repair_interval"],
                    acquired_at=parsed.get("dwellinged_at"),
                    light_override=parse_light_level(parsed["sun"]) if parsed.get("sun") else None,
                    archived=archived,
                    source="homeadvisor",
                    metadata=dict(metadata),
                )
                storage.create_dwelling(dwelling)
                count += 1
        except Exception as exc:
            raise import_pipeline_error("homeadvisor", line_no, str(exc)) from exc

    return count


def preview_homeadvisor(path: Path, limit: int = 5) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    lines: list[str] = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        parsed = parse_homeadvisor_row(row)
        if parsed:
            lines.append(
                "%s x%d @ %s" % (
                    parsed["name"],
                    parsed["quantity"],
                    parsed["zone_label"],
                )
            )
    return lines


def validate_homeadvisor_headers(path: Path) -> list[str]:
    if not path.exists():
        return ["Dwelling"]
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    if not any(h in headers for h in COLUMN_MAP["dwelling"]):
        return ["Dwelling (or Dwelling Name / Crop)"]
    return []
