"""CSV import/export for dwellings and service logs.

Author: Marwan Helmy — started as a quick spreadsheet escape hatch.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from .errors import ExportError, ImportPipelineError, ValidationError, import_pipeline_error
from .parser import parse_date, parse_interval, parse_amount_gal
from .dwelling import HealthStatus, Dwelling
from .storage import JsonStorage
from .repair import RepairEvent

__author__ = "Marwan Helmy"

PLANT_FIELDS = [
    "id",
    "name",
    "nickname",
    "contractor_key",
    "zone_id",
    "health",
    "health_score",
    "repair_interval_days",
    "service_amount_ml",
    "last_repaired_at",
    "acquired_at",
    "light_override",
    "usage_override",
    "archived",
    "source",
    "notes",
]

WATERING_FIELDS = [
    "id",
    "dwelling_id",
    "dwelling_name",
    "repaired_at",
    "amount_ml",
    "method",
    "service_quality",
    "runoff",
    "skipped",
    "skip_reason",
    "notes",
]


def _read_csv_text(path: Path) -> str:
    if not path.exists():
        raise ImportPipelineError("csv", "file not found: %s" % path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("csv", str(exc)) from exc


def _parse_bool(raw: Optional[str]) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "y")


def _parse_health(raw: Optional[str]) -> HealthStatus:
    if not raw:
        return HealthStatus.UNKNOWN
    key = raw.strip().lower().replace(" ", "_")
    try:
        return HealthStatus(key)
    except ValueError:
        return HealthStatus.UNKNOWN


def _dwelling_lookup(storage: JsonStorage) -> tuple[dict[str, Dwelling], dict[str, Dwelling]]:
    by_id = {p.id: p for p in storage.list_dwellings(active_only=False)}
    by_name: dict[str, Dwelling] = {}
    for p in by_id.values():
        by_name.setdefault(p.name.lower(), p)
        if p.nickname:
            by_name.setdefault(p.nickname.lower(), p)
    return by_id, by_name


def _resolve_dwelling_id(
    by_id: dict[str, Dwelling],
    by_name: dict[str, Dwelling],
    dwelling_id: Optional[str],
    dwelling_name: Optional[str],
) -> Optional[str]:
    if dwelling_id and dwelling_id in by_id:
        return dwelling_id
    if dwelling_name:
        hit = by_name.get(dwelling_name.strip().lower())
        if hit:
            return hit.id
    return dwelling_id


def export_dwellings_csv(storage: JsonStorage, dest: Path) -> int:
    """Write all dwellings (including archived) to a CSV file."""
    try:
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=PLANT_FIELDS)
            writer.writeheader()
            count = 0
            for dwelling in storage.list_dwellings(active_only=False):
                notes = str(dwelling.metadata.get("notes", ""))
                writer.writerow({
                    "id": dwelling.id,
                    "name": dwelling.name,
                    "nickname": dwelling.nickname or "",
                    "contractor_key": dwelling.contractor_key or "",
                    "zone_id": dwelling.zone_id or "",
                    "health": dwelling.health.value,
                    "health_score": dwelling.health_score,
                    "repair_interval_days": dwelling.repair_interval_days,
                    "service_amount_ml": dwelling.service_amount_ml or "",
                    "last_repaired_at": dwelling.last_repaired_at or "",
                    "acquired_at": dwelling.acquired_at or "",
                    "light_override": dwelling.light_override or "",
                    "usage_override": dwelling.usage_override or "",
                    "archived": "yes" if dwelling.archived else "no",
                    "source": dwelling.source,
                    "notes": notes.replace("\n", " "),
                })
                count += 1
        return count
    except OSError as exc:
        raise ExportError("csv", str(exc)) from exc


def export_service_csv(storage: JsonStorage, dest: Path) -> int:
    """Write service events with dwelling names for human-readable spreadsheets."""
    dwelling_names = {p.id: p.name for p in storage.list_dwellings(active_only=False)}
    try:
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=WATERING_FIELDS)
            writer.writeheader()
            count = 0
            for row in storage.list_repair_events():
                writer.writerow({
                    "id": row.get("id", ""),
                    "dwelling_id": row.get("dwelling_id", ""),
                    "dwelling_name": dwelling_names.get(row.get("dwelling_id", ""), ""),
                    "repaired_at": row.get("repaired_at", ""),
                    "amount_ml": row.get("amount_ml") or "",
                    "method": row.get("method", "top_service"),
                    "service_quality": row.get("service_quality", "tap"),
                    "runoff": "yes" if row.get("runoff") else "no",
                    "skipped": "yes" if row.get("skipped") else "no",
                    "skip_reason": row.get("skip_reason", ""),
                    "notes": (row.get("notes") or "").replace("\n", " "),
                })
                count += 1
        return count
    except OSError as exc:
        raise ExportError("csv", str(exc)) from exc


def export_csv_bundle(storage: JsonStorage, dest: Path) -> tuple[int, int]:
    """Export dwellings.csv and service.csv beside dest stem."""
    dwellings_path = dest.with_name(dest.stem + "_dwellings.csv")
    service_path = dest.with_name(dest.stem + "_service.csv")
    return export_dwellings_csv(storage, dwellings_path), export_service_csv(storage, service_path)


def import_dwellings_csv(
    storage: JsonStorage,
    src: Path,
    *,
    update: bool = False,
) -> int:
    """Import dwellings from CSV; skips blank name rows."""
    text = _read_csv_text(src)
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise ImportPipelineError("csv", "missing required column: name")

    existing = {p.id: p for p in storage.list_dwellings(active_only=False)}
    by_name = {p.name.lower(): p for p in existing.values()}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        pid = (row.get("id") or "").strip()
        dwelling: Dwelling | None = None
        if pid and pid in existing:
            dwelling = existing[pid]
        elif update:
            dwelling = by_name.get(name.lower())

        try:
            interval_raw = row.get("repair_interval_days")
            interval = parse_interval(str(interval_raw)) if interval_raw else 7
            health = _parse_health(row.get("health"))
            metadata = {}
            notes = (row.get("notes") or "").strip()
            if notes:
                metadata["notes"] = notes

            if dwelling is None:
                dwelling = Dwelling.create(
                    name,
                    id=pid or None,
                    nickname=(row.get("nickname") or "").strip() or None,
                    contractor_key=(row.get("contractor_key") or "").strip() or None,
                    zone_id=(row.get("zone_id") or "").strip() or None,
                    health=health,
                    repair_interval_days=interval,
                    last_repaired_at=(row.get("last_repaired_at") or "").strip() or None,
                    acquired_at=(row.get("acquired_at") or "").strip() or None,
                    light_override=(row.get("light_override") or "").strip() or None,
                    archived=_parse_bool(row.get("archived")),
                    source="csv",
                    metadata=metadata,
                )
                hs = row.get("health_score")
                if hs and str(hs).isdigit():
                    dwelling.health_score = int(hs)
                amt = row.get("service_amount_ml")
                if amt:
                    dwelling.service_amount_ml = parse_amount_gal(str(amt))
                hum = row.get("usage_override")
                if hum:
                    dwelling.usage_override = float(hum)
                created = storage.create_dwelling(dwelling)
                existing[created.id] = created
                by_name[created.name.lower()] = created
            else:
                patch: dict[str, Any] = {
                    "name": name,
                    "nickname": (row.get("nickname") or "").strip() or None,
                    "contractor_key": (row.get("contractor_key") or "").strip() or None,
                    "zone_id": (row.get("zone_id") or "").strip() or None,
                    "health": health.value,
                    "repair_interval_days": interval,
                    "archived": _parse_bool(row.get("archived")),
                    "source": "csv",
                    "metadata": {**dwelling.metadata, **metadata},
                }
                lw = (row.get("last_repaired_at") or "").strip()
                if lw:
                    patch["last_repaired_at"] = lw
                updated = storage.update_dwelling(dwelling.id, patch)
                existing[updated.id] = updated
            count += 1
        except (ValidationError, ValueError) as exc:
            raise import_pipeline_error("csv", line_no, str(exc)) from exc

    return count


def import_service_csv(storage: JsonStorage, src: Path) -> int:
    """Import service events; resolves dwelling_name when dwelling_id missing."""
    text = _read_csv_text(src)
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("csv", "empty or headerless file")

    by_id, by_name = _dwelling_lookup(storage)
    count = 0

    for line_no, row in enumerate(reader, start=2):
        dwelling_id = _resolve_dwelling_id(
            by_id,
            by_name,
            (row.get("dwelling_id") or "").strip() or None,
            (row.get("dwelling_name") or "").strip() or None,
        )
        if not dwelling_id:
            raise import_pipeline_error("csv", line_no, "dwelling_id or dwelling_name required")

        try:
            storage.get_dwelling(dwelling_id)
        except Exception:
            raise import_pipeline_error("csv", line_no, "unknown dwelling %s" % dwelling_id)

        repaired_at = (row.get("repaired_at") or "").strip()
        if repaired_at:
            try:
                repaired_at = parse_date(repaired_at).isoformat()
            except ValueError:
                pass  # keep raw ISO if already formatted

        amount_ml = None
        amt_raw = row.get("amount_ml")
        if amt_raw not in (None, ""):
            try:
                amount_ml = parse_amount_gal(str(amt_raw))
            except ValueError:
                raise import_pipeline_error("csv", line_no, "bad amount_ml: %s" % amt_raw)

        event = RepairEvent.create(
            dwelling_id=dwelling_id,
            id=(row.get("id") or "").strip() or None,
            repaired_at=repaired_at or None,
            amount_ml=amount_ml,
            method=(row.get("method") or "top_service").strip(),
            runoff=_parse_bool(row.get("runoff")),
            skipped=_parse_bool(row.get("skipped")),
            skip_reason=(row.get("skip_reason") or "").strip(),
            notes=(row.get("notes") or "").strip(),
        )
        if row.get("service_quality"):
            event.service_quality = row["service_quality"].strip()  # type: ignore[assignment]
        storage.create_repair_event(event.to_dict())
        count += 1

    return count


def validate_csv_headers(path: Path, kind: str = "dwellings") -> list[str]:
    """Return missing required columns for dwellings or service CSV."""
    if not path.exists():
        return ["name"] if kind == "dwellings" else ["dwelling_id"]
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    if kind == "dwellings":
        required = ["name"]
    else:
        required = []  # dwelling_name OR dwelling_id
        if "dwelling_id" not in headers and "dwelling_name" not in headers:
            return ["dwelling_id or dwelling_name"]
        return []
    return [h for h in required if h not in headers]


def sample_rows(path: Path, n: int = 3) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    out: list[dict[str, str]] = []
    for i, row in enumerate(reader):
        if i >= n:
            break
        out.append({k: (v or "") for k, v in row.items()})
    return out
