"""Tests for fixlog.storage."""

import json

import pytest

from fixlog.errors import NotFoundError, StorageError, ValidationError
from fixlog.zone import Zone
from fixlog.dwelling import Dwelling, HealthStatus
from fixlog.contractor import ContractorProfile
from fixlog.storage import JsonStorage, DEFAULT_HOMESTEAD, SCHEMA_VERSION


class TestJsonStorageInit:
    def test_creates_empty_homestead(self, tmp_homestead_path):
        storage = JsonStorage(tmp_homestead_path)
        assert tmp_homestead_path.exists()

    def test_loads_existing(self, populated_storage, tmp_homestead_path):
        storage2 = JsonStorage(tmp_homestead_path)
        assert len(storage2.list_dwellings()) >= 2


class TestDwellings:
    def test_create_and_list(self, empty_storage, sample_dwelling):
        created = empty_storage.create_dwelling(sample_dwelling)
        assert created.name == sample_dwelling.name

    def test_get_dwelling(self, populated_storage, sample_dwelling):
        dwelling = populated_storage.get_dwelling(sample_dwelling.id)
        assert dwelling.id == sample_dwelling.id

    def test_get_dwelling_not_found(self, empty_storage):
        with pytest.raises(NotFoundError):
            empty_storage.get_dwelling("missing")

    def test_update_dwelling(self, populated_storage, sample_dwelling):
        updated = populated_storage.update_dwelling(sample_dwelling.id, {"nickname": "NewNick"})
        assert updated.nickname == "NewNick"

    def test_delete_dwelling(self, populated_storage, sample_dwelling):
        populated_storage.delete_dwelling(sample_dwelling.id)
        with pytest.raises(NotFoundError):
            populated_storage.get_dwelling(sample_dwelling.id)

    def test_list_dwellings_active_only(self, populated_storage, sample_dwelling):
        populated_storage.update_dwelling(sample_dwelling.id, {"archived": True})
        active = populated_storage.list_dwellings(active_only=True)
        assert all(not p.archived for p in active)

    def test_duplicate_dwelling_raises(self, populated_storage, sample_dwelling):
        with pytest.raises(ValidationError):
            populated_storage.create_dwelling(sample_dwelling.to_dict())


class TestContractor:
    def test_create_contractor(self, empty_storage, sample_contractor):
        created = empty_storage.create_contractor(sample_contractor)
        assert created.key == sample_contractor.key

    def test_get_contractor(self, populated_storage, sample_contractor):
        sp = populated_storage.get_contractor(sample_contractor.key)
        assert sp.common_name == sample_contractor.common_name

    def test_delete_contractor(self, populated_storage, sample_contractor):
        populated_storage.delete_contractor(sample_contractor.key)
        with pytest.raises(NotFoundError):
            populated_storage.get_contractor(sample_contractor.key)


class TestZones:
    def test_create_zone(self, empty_storage, sample_zone):
        created = empty_storage.create_zone(sample_zone)
        assert created.name == sample_zone.name

    def test_get_zone(self, populated_storage, sample_zone):
        loc = populated_storage.get_zone(sample_zone.id)
        assert loc.id == sample_zone.id

    def test_update_zone(self, populated_storage, sample_zone):
        updated = populated_storage.update_zone(sample_zone.id, {"notes": "Updated"})
        assert updated.notes == "Updated"


class TestService:
    def test_create_repair_event(self, populated_storage, sample_dwelling):
        event = populated_storage.create_repair_event({
            "id": "we_new",
            "dwelling_id": sample_dwelling.id,
            "amount_ml": 300,
        })
        assert event["dwelling_id"] == sample_dwelling.id

    def test_list_repair_events_filtered(self, populated_storage, sample_dwelling):
        events = populated_storage.list_repair_events(dwelling_id=sample_dwelling.id)
        assert len(events) >= 1

    def test_delete_repair_event(self, populated_storage):
        events = populated_storage.list_repair_events()
        eid = events[0]["id"]
        populated_storage.delete_repair_event(eid)
        with pytest.raises(NotFoundError):
            populated_storage.get_repair_event(eid)


class TestTagsAndNotes:
    def test_create_tag(self, empty_storage):
        tag = empty_storage.create_tag({"id": "tag_new", "name": "test"})
        assert tag["name"] == "test"

    def test_create_note(self, populated_storage, sample_dwelling):
        note = populated_storage.create_note({
            "id": "note_new",
            "dwelling_id": sample_dwelling.id,
            "body": "Test note",
        })
        assert note["body"] == "Test note"

    def test_list_notes_filtered(self, populated_storage, sample_dwelling):
        notes = populated_storage.list_notes(dwelling_id=sample_dwelling.id)
        assert len(notes) >= 1


class TestAuditAndPlugins:
    def test_append_audit(self, empty_storage):
        entry = empty_storage.append_audit({"action": "create", "entity": "dwelling"})
        assert "timestamp" in entry

    def test_upsert_plugin(self, empty_storage):
        plugin = empty_storage.upsert_plugin({"id": "p1", "name": "Test Plugin"})
        assert plugin["name"] == "Test Plugin"
        updated = empty_storage.upsert_plugin({"id": "p1", "name": "Updated"})
        assert updated["name"] == "Updated"


class TestRecurringAndCollections:
    def test_create_recurring(self, empty_storage):
        task = empty_storage.create_recurring({"id": "r1", "title": "Weekly mist"})
        assert task["title"] == "Weekly mist"

    def test_create_collection(self, empty_storage):
        coll = empty_storage.create_collection({"id": "c1", "name": "Favorites"})
        assert coll["name"] == "Favorites"


class TestStorageCore:
    def test_snapshot(self, populated_storage):
        snap = populated_storage.snapshot()
        assert "dwellings" in snap

    def test_replace_all(self, empty_storage, sample_dwelling):
        empty_storage.replace_all({
            **DEFAULT_HOMESTEAD,
            "dwellings": [sample_dwelling.to_dict()],
        })
        assert len(empty_storage.list_dwellings()) == 1

    def test_mutate(self, empty_storage):
        def add_tag(data):
            data["tags"].append({"id": "t1", "name": "test"})
        empty_storage.mutate(add_tag)
        assert len(empty_storage.list_tags()) == 1

    def test_load_corrupt_json(self, tmp_homestead_path):
        tmp_homestead_path.write_text("{not json", encoding="utf-8")
        with pytest.raises(StorageError):
            JsonStorage(tmp_homestead_path)

    def test_schema_version_in_default(self):
        assert DEFAULT_HOMESTEAD["schema_version"] == SCHEMA_VERSION
