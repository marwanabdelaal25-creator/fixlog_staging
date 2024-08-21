"""Tests for fixlog.collections."""

import pytest

from fixlog.errors import NotFoundError, ValidationError
from fixlog.collections import CollectionManager


class TestCollectionManager:
    def test_create(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Kitchen Herbs", dwelling_ids=[sample_dwelling.id])
        assert coll["name"] == "Kitchen Herbs"
        assert sample_dwelling.id in coll["dwelling_ids"]

    def test_create_empty_name_raises(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(ValidationError):
            mgr.create("  ")

    def test_create_invalid_dwelling_raises(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.create("Bad", dwelling_ids=["missing"])

    def test_list_all(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        mgr.create("Group A", dwelling_ids=[sample_dwelling.id])
        assert len(mgr.list_all()) == 1

    def test_get(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Favorites")
        found = mgr.get(coll["id"])
        assert found["name"] == "Favorites"

    def test_get_not_found(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.get("missing")

    def test_add_dwelling(self, populated_storage, sample_dwelling, sample_dwelling2):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        updated = mgr.add_dwelling(coll["id"], sample_dwelling.id)
        updated = mgr.add_dwelling(coll["id"], sample_dwelling2.id)
        assert len(updated["dwelling_ids"]) == 2

    def test_add_dwelling_dedupes(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", dwelling_ids=[sample_dwelling.id])
        updated = mgr.add_dwelling(coll["id"], sample_dwelling.id)
        assert updated["dwelling_ids"].count(sample_dwelling.id) == 1

    def test_remove_dwelling(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", dwelling_ids=[sample_dwelling.id])
        updated = mgr.remove_dwelling(coll["id"], sample_dwelling.id)
        assert sample_dwelling.id not in updated["dwelling_ids"]

    def test_rename(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Old Name")
        updated = mgr.rename(coll["id"], "New Name")
        assert updated["name"] == "New Name"

    def test_rename_blank_raises(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Name")
        with pytest.raises(ValidationError):
            mgr.rename(coll["id"], "  ")

    def test_delete(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Temp")
        mgr.delete(coll["id"])
        assert mgr.list_all() == []

    def test_dwellings_in(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", dwelling_ids=[sample_dwelling.id])
        dwellings = mgr.dwellings_in(coll["id"])
        assert len(dwellings) == 1

    def test_dwellings_in_skips_stale(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        populated_storage.update_collection(coll["id"], {"dwelling_ids": ["stale_id"]})
        assert mgr.dwellings_in(coll["id"]) == []

    def test_collections_for_dwelling(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        mgr.create("A", dwelling_ids=[sample_dwelling.id])
        mgr.create("B", dwelling_ids=[sample_dwelling.id])
        cols = mgr.collections_for_dwelling(sample_dwelling.id)
        assert len(cols) == 2

    def test_merge(self, populated_storage, sample_dwelling, sample_dwelling2):
        mgr = CollectionManager(populated_storage)
        t = mgr.create("Target", dwelling_ids=[sample_dwelling.id])
        s = mgr.create("Source", dwelling_ids=[sample_dwelling2.id])
        merged = mgr.merge(t["id"], s["id"])
        assert sample_dwelling2.id in merged["dwelling_ids"]
        assert len(mgr.list_all()) == 1

    def test_merge_dedupes_overlap(self, populated_storage, sample_dwelling):
        mgr = CollectionManager(populated_storage)
        t = mgr.create("Target", dwelling_ids=[sample_dwelling.id])
        s = mgr.create("Source", dwelling_ids=[sample_dwelling.id])
        merged = mgr.merge(t["id"], s["id"])
        assert merged["dwelling_ids"].count(sample_dwelling.id) == 1

    def test_description_stored(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Herbs", description="Kitchen window")
        assert coll["description"] == "Kitchen window"

    def test_add_unknown_dwelling_raises(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        with pytest.raises(NotFoundError):
            mgr.add_dwelling(coll["id"], "missing")
