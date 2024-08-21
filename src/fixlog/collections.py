"""Dwelling groupings / collections (e.g. kitchen herbs).

Author: Marwan Helmy
"""

from __future__ import annotations

import uuid
from typing import Iterable, Optional

from .errors import NotFoundError, ValidationError
from .storage import JsonStorage


class CollectionManager:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def create(self, name: str, description: str = "", dwelling_ids: Optional[Iterable[str]] = None) -> dict:
        if not name.strip():
            raise ValidationError("collection name required")
        ids = list(dwelling_ids or [])
        for pid in ids:
            self.storage.get_dwelling(pid)
        return self.storage.create_collection({
            "id": uuid.uuid4().hex[:12],
            "name": name.strip(),
            "description": description,
            "dwelling_ids": ids,
        })

    def list_all(self) -> list[dict]:
        return self.storage.list_collections()

    def get(self, collection_id: str) -> dict:
        for c in self.list_all():
            if c.get("id") == collection_id:
                return c
        raise NotFoundError("collections", collection_id)

    def add_dwelling(self, collection_id: str, dwelling_id: str) -> dict:
        coll = self.get(collection_id)
        self.storage.get_dwelling(dwelling_id)
        ids = list(coll.get("dwelling_ids", []))
        if dwelling_id not in ids:
            ids.append(dwelling_id)
        return self.storage.update_collection(collection_id, {"dwelling_ids": ids})

    def remove_dwelling(self, collection_id: str, dwelling_id: str) -> dict:
        coll = self.get(collection_id)
        ids = [x for x in coll.get("dwelling_ids", []) if x != dwelling_id]
        return self.storage.update_collection(collection_id, {"dwelling_ids": ids})

    def rename(self, collection_id: str, name: str) -> dict:
        if not name.strip():
            raise ValidationError("name required")
        return self.storage.update_collection(collection_id, {"name": name.strip()})

    def delete(self, collection_id: str) -> None:
        self.storage.delete_collection(collection_id)

    def dwellings_in(self, collection_id: str) -> list[dict]:
        coll = self.get(collection_id)
        out = []
        for pid in coll.get("dwelling_ids", []):
            try:
                out.append(self.storage.get_dwelling(pid).to_dict())
            except NotFoundError:
                pass  # stale id
        return out

    def collections_for_dwelling(self, dwelling_id: str) -> list[dict]:
        return [
            c for c in self.list_all()
            if dwelling_id in c.get("dwelling_ids", [])
        ]

    def merge(self, target_id: str, source_id: str) -> dict:
        target = self.get(target_id)
        source = self.get(source_id)
        merged_ids = list(dict.fromkeys(
            list(target.get("dwelling_ids", [])) + list(source.get("dwelling_ids", []))
        ))
        self.storage.update_collection(target_id, {"dwelling_ids": merged_ids})
        self.delete(source_id)
        return self.get(target_id)
