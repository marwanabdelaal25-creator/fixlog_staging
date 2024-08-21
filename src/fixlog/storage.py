"""JSON persistence layer for homestead data.

Author: Marwan Helmy
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .errors import NotFoundError, StorageError, ValidationError
from .zone import Zone
from .dwelling import Dwelling
from .contractor import ContractorProfile

SCHEMA_VERSION = 2

DEFAULT_HOMESTEAD: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "dwellings": [],
    "contractor": [],
    "zones": [],
    "repair_events": [],
    "walkthroughs": [],
    "tags": [],
    "notes": [],
    "audit": [],
    "plugins": [],
    "recurring": [],
    "collections": [],
    "usage_readings": [],
    "climate_logs": [],
    "issue_reports": [],
    "inspection_events": [],
    "labels": [],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex[:12]
    return f"{prefix}{raw}" if prefix else raw


def _normalize_dwelling_row(row: dict) -> dict:
    """Bridge legacy homestead.json field names."""
    out = dict(row)
    if "contractor_key" not in out and out.get("contractor_id"):
        out["contractor_key"] = out["contractor_id"]
    if "tag_ids" not in out and out.get("tags"):
        out["tag_ids"] = list(out["tags"])
    if "archived" not in out and "active" in out:
        out["archived"] = not bool(out.get("active", True))
    return out


def _dwelling_payload(data: Dwelling | dict) -> dict:
    if isinstance(data, Dwelling):
        return data.to_dict()
    return _normalize_dwelling_row(dict(data))


def _normalize_contractor_row(row: dict) -> dict:
    out = dict(row)
    if "key" not in out and out.get("id"):
        out["key"] = out["id"]
    return out


def _contractor_payload(data: ContractorProfile | dict) -> dict:
    if isinstance(data, ContractorProfile):
        return data.to_dict()
    row = _normalize_contractor_row(dict(data))
    return row


class JsonStorage:
    """Thread-safe JSON file store with atomic writes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict[str, Any] = deepcopy(DEFAULT_HOMESTEAD)
        if self.path.exists():
            self.load()
        else:
            self._ensure_parent()
            self.save()

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        with self._lock:
            try:
                text = self.path.read_text(encoding="utf-8")
                payload = json.loads(text)
            except (OSError, json.JSONDecodeError) as exc:
                raise StorageError(f"failed to load {self.path}: {exc}") from exc
            if not isinstance(payload, dict):
                raise StorageError("homestead root must be an object")
            self._data = self._merge_defaults(payload)
            return deepcopy(self._data)

    def save(self) -> None:
        with self._lock:
            self._atomic_write(self._data)

    def _merge_defaults(self, payload: dict) -> dict:
        merged = deepcopy(DEFAULT_HOMESTEAD)
        merged.update(payload)
        for key in DEFAULT_HOMESTEAD:
            if key not in payload:
                merged[key] = deepcopy(DEFAULT_HOMESTEAD[key])
        return merged

    def _atomic_write(self, data: dict) -> None:
        self._ensure_parent()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise StorageError(f"failed to save {self.path}: {exc}") from exc

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def replace_all(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._data = self._merge_defaults(data)
            self._atomic_write(self._data)

    # --- generic list CRUD ---

    def _list(self, bucket: str) -> list[dict]:
        items = self._data.get(bucket, [])
        if not isinstance(items, list):
            raise StorageError(f"bucket {bucket!r} is corrupt")
        return items

    def _find_index(self, bucket: str, item_id: str, id_field: str = "id") -> int:
        for idx, row in enumerate(self._list(bucket)):
            if row.get(id_field) == item_id:
                return idx
        raise NotFoundError(bucket, item_id)

    def _create(self, bucket: str, record: dict, id_field: str = "id") -> dict:
        with self._lock:
            if not record.get(id_field):
                record[id_field] = _new_id()
            if any(r.get(id_field) == record[id_field] for r in self._list(bucket)):
                raise ValidationError(f"duplicate {id_field} in {bucket}")
            record.setdefault("created_at", _utc_now())
            record.setdefault("updated_at", record["created_at"])
            self._list(bucket).append(record)
            self._atomic_write(self._data)
            return deepcopy(record)

    def _read(self, bucket: str, item_id: str, id_field: str = "id") -> dict:
        idx = self._find_index(bucket, item_id, id_field)
        return deepcopy(self._list(bucket)[idx])

    def _update(self, bucket: str, item_id: str, patch: dict, id_field: str = "id") -> dict:
        with self._lock:
            idx = self._find_index(bucket, item_id, id_field)
            row = self._list(bucket)[idx]
            for k, v in patch.items():
                if k == id_field:
                    continue
                row[k] = v
            row["updated_at"] = _utc_now()
            self._atomic_write(self._data)
            return deepcopy(row)

    def _delete(self, bucket: str, item_id: str, id_field: str = "id") -> None:
        with self._lock:
            idx = self._find_index(bucket, item_id, id_field)
            del self._list(bucket)[idx]
            self._atomic_write(self._data)

    def _list_all(self, bucket: str) -> list[dict]:
        with self._lock:
            return deepcopy(self._list(bucket))

    # --- dwellings ---

    def list_dwellings(self, active_only: bool = False) -> list[Dwelling]:
        rows = self._list_all("dwellings")
        if active_only:
            rows = [r for r in rows if not r.get("archived", False)]
        return [Dwelling.from_dict(_normalize_dwelling_row(r)) for r in rows]

    def get_dwelling(self, dwelling_id: str) -> Dwelling:
        return Dwelling.from_dict(_normalize_dwelling_row(self._read("dwellings", dwelling_id)))

    def create_dwelling(self, dwelling: Dwelling | dict) -> Dwelling:
        return Dwelling.from_dict(self._create("dwellings", _dwelling_payload(dwelling)))

    def update_dwelling(self, dwelling_id: str, patch: dict) -> Dwelling:
        return Dwelling.from_dict(self._update("dwellings", dwelling_id, _normalize_dwelling_row(patch)))

    def delete_dwelling(self, dwelling_id: str) -> None:
        self._delete("dwellings", dwelling_id)

    # --- contractor ---

    def list_contractor(self) -> list[ContractorProfile]:
        return [ContractorProfile.from_dict(_normalize_contractor_row(r)) for r in self._list_all("contractor")]

    def get_contractor(self, contractor_id: str) -> ContractorProfile:
        for row in self._list_all("contractor"):
            if row.get("key") == contractor_id or row.get("id") == contractor_id:
                return ContractorProfile.from_dict(_normalize_contractor_row(row))
        raise NotFoundError("contractor", contractor_id)

    def create_contractor(self, contractor: ContractorProfile | dict) -> ContractorProfile:
        row = _contractor_payload(contractor)
        created = self._create("contractor", row, id_field="key")
        return ContractorProfile.from_dict(_normalize_contractor_row(created))

    def update_contractor(self, contractor_id: str, patch: dict) -> ContractorProfile:
        row = self._update("contractor", contractor_id, _normalize_contractor_row(patch), id_field="key")
        return ContractorProfile.from_dict(_normalize_contractor_row(row))

    def delete_contractor(self, contractor_id: str) -> None:
        with self._lock:
            rows = self._list("contractor")
            for idx, row in enumerate(rows):
                if row.get("key") == contractor_id or row.get("id") == contractor_id:
                    del rows[idx]
                    self._atomic_write(self._data)
                    return
        raise NotFoundError("contractor", contractor_id)

    # --- zones ---

    def list_zones(self) -> list[Zone]:
        return [Zone.from_dict(r) for r in self._list_all("zones")]

    def get_zone(self, zone_id: str) -> Zone:
        return Zone.from_dict(self._read("zones", zone_id))

    def create_zone(self, zone: Zone | dict) -> Zone:
        data = zone.to_dict() if isinstance(zone, Zone) else dict(zone)
        return Zone.from_dict(self._create("zones", data))

    def update_zone(self, zone_id: str, patch: dict) -> Zone:
        return Zone.from_dict(self._update("zones", zone_id, patch))

    def delete_zone(self, zone_id: str) -> None:
        self._delete("zones", zone_id)

    # --- service / care ---

    def list_repair_events(self, dwelling_id: Optional[str] = None) -> list[dict]:
        rows = self._list_all("repair_events")
        if dwelling_id:
            rows = [r for r in rows if r.get("dwelling_id") == dwelling_id]
        return rows

    def create_repair_event(self, event: dict) -> dict:
        event.setdefault("repaired_at", _utc_now())
        created = self._create("repair_events", event)
        # keep dwelling in sync - lazy but handy
        try:
            self.update_dwelling(created["dwelling_id"], {"last_repaired_at": created["repaired_at"]})
        except NotFoundError:
            pass
        return created

    def get_repair_event(self, event_id: str) -> dict:
        return self._read("repair_events", event_id)

    def update_repair_event(self, event_id: str, patch: dict) -> dict:
        return self._update("repair_events", event_id, patch)

    def delete_repair_event(self, event_id: str) -> None:
        self._delete("repair_events", event_id)

    def list_walkthroughs(self, dwelling_id: Optional[str] = None) -> list[dict]:
        rows = self._list_all("walkthroughs")
        if dwelling_id:
            rows = [r for r in rows if r.get("dwelling_id") == dwelling_id]
        return rows

    def create_walkthrough(self, log: dict) -> dict:
        log.setdefault("logged_at", _utc_now())
        return self._create("walkthroughs", log)

    def get_walkthrough(self, log_id: str) -> dict:
        return self._read("walkthroughs", log_id)

    def update_walkthrough(self, log_id: str, patch: dict) -> dict:
        return self._update("walkthroughs", log_id, patch)

    def delete_walkthrough(self, log_id: str) -> None:
        self._delete("walkthroughs", log_id)

    # --- tags / notes ---

    def list_tags(self) -> list[dict]:
        return self._list_all("tags")

    def create_tag(self, tag: dict) -> dict:
        tag.setdefault("name", tag.get("id", ""))
        return self._create("tags", tag)

    def update_tag(self, tag_id: str, patch: dict) -> dict:
        return self._update("tags", tag_id, patch)

    def delete_tag(self, tag_id: str) -> None:
        self._delete("tags", tag_id)

    def list_notes(self, dwelling_id: Optional[str] = None) -> list[dict]:
        rows = self._list_all("notes")
        if dwelling_id:
            rows = [r for r in rows if r.get("dwelling_id") == dwelling_id]
        return rows

    def create_note(self, note: dict) -> dict:
        note.setdefault("created_at", _utc_now())
        return self._create("notes", note)

    def update_note(self, note_id: str, patch: dict) -> dict:
        return self._update("notes", note_id, patch)

    def delete_note(self, note_id: str) -> None:
        self._delete("notes", note_id)

    # --- audit / plugins / recurring ---

    def list_audit(self) -> list[dict]:
        return self._list_all("audit")

    def append_audit(self, entry: dict) -> dict:
        entry.setdefault("timestamp", _utc_now())
        entry.setdefault("id", _new_id("aud_"))
        with self._lock:
            self._list("audit").append(entry)
            self._atomic_write(self._data)
            return deepcopy(entry)

    def list_plugins(self) -> list[dict]:
        return self._list_all("plugins")

    def upsert_plugin(self, plugin: dict) -> dict:
        pid = plugin.get("id")
        if not pid:
            return self._create("plugins", plugin)
        with self._lock:
            for idx, row in enumerate(self._list("plugins")):
                if row.get("id") == pid:
                    row.update(plugin)
                    row["updated_at"] = _utc_now()
                    self._atomic_write(self._data)
                    return deepcopy(row)
        return self._create("plugins", plugin)

    def delete_plugin(self, plugin_id: str) -> None:
        self._delete("plugins", plugin_id)

    def list_recurring(self) -> list[dict]:
        return self._list_all("recurring")

    def create_recurring(self, task: dict) -> dict:
        return self._create("recurring", task)

    def update_recurring(self, task_id: str, patch: dict) -> dict:
        return self._update("recurring", task_id, patch)

    def delete_recurring(self, task_id: str) -> None:
        self._delete("recurring", task_id)

    # --- extended buckets used by other modules ---

    def list_collections(self) -> list[dict]:
        return self._list_all("collections")

    def create_collection(self, coll: dict) -> dict:
        return self._create("collections", coll)

    def update_collection(self, coll_id: str, patch: dict) -> dict:
        return self._update("collections", coll_id, patch)

    def delete_collection(self, coll_id: str) -> None:
        self._delete("collections", coll_id)

    def mutate(self, fn: Callable[[dict[str, Any]], None]) -> None:
        """Run arbitrary in-lock mutation (used by migrations)."""
        with self._lock:
            fn(self._data)
            self._atomic_write(self._data)
