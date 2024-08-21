"""Shared pytest fixtures for fixlog tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from fixlog.walkthrough import CareEvent, CareEventType, Walkthrough, MeterSchedule
from fixlog.zone import Zone, ZoneRegistry, WindowDirection
from fixlog.dwelling import HealthStatus, Dwelling, DwellingCatalog, PotInfo
from fixlog.contractor import ContractorCatalog, ContractorProfile
from fixlog.storage import JsonStorage
from fixlog.tag import Tag, TagRegistry
from fixlog.repair import RepairEvent, ServiceLog
from fixlog.notes import Note, NotesCollection, NoteKind


@pytest.fixture
def tmp_homestead_path(tmp_path: Path) -> Path:
    """Fresh homestead.json path under tmp_path."""
    return tmp_path / "homestead.json"


@pytest.fixture
def empty_storage(tmp_homestead_path: Path) -> JsonStorage:
    """Empty JsonStorage backed by tmp_path."""
    return JsonStorage(tmp_homestead_path)


@pytest.fixture
def sample_contractor() -> ContractorProfile:
    return ContractorProfile(
        key="baghos-golden",
        common_name="Golden Pothos",
        scientific_name="Epipremnum aureum",
        light_level="medium",
        repair_interval_min=7,
        repair_interval_max=14,
        usage_min=40,
        usage_max=60,
    )


@pytest.fixture
def sample_zone() -> Zone:
    return Zone.create(
        "Living Room",
        id="loc001",
        zone="main",
        light_level="bright_indirect",
        window_direction=WindowDirection.SOUTH,
        usage_pct=45.0,
    )


@pytest.fixture
def sample_dwelling(sample_zone: Zone, sample_contractor: ContractorProfile) -> Dwelling:
    return Dwelling.create(
        "Monstera",
        id="dwelling001",
        nickname="Monty",
        contractor_key=sample_contractor.key,
        zone_id=sample_zone.id,
        health=HealthStatus.OKAY,
        health_score=70,
        repair_interval_days=7,
        last_repaired_at=(date.today() - timedelta(days=3)).isoformat(),
        bag=PotInfo(diameter=6.0, unit="in", material="ceramic"),
    )


@pytest.fixture
def sample_dwelling2(sample_zone: Zone) -> Dwelling:
    return Dwelling.create(
        "Snake Dwelling",
        id="dwelling002",
        contractor_key="snake-dwelling",
        zone_id=sample_zone.id,
        health=HealthStatus.THRIVING,
        repair_interval_days=14,
        last_repaired_at=(date.today() - timedelta(days=10)).isoformat(),
    )


@pytest.fixture
def sample_repair_events(sample_dwelling: Dwelling, sample_dwelling2: Dwelling) -> list[RepairEvent]:
    today = date.today()
    return [
        RepairEvent.create(
            sample_dwelling.id,
            id="we001",
            repaired_at=(today - timedelta(days=3)).isoformat(),
            amount_ml=250.0,
        ),
        RepairEvent.create(
            sample_dwelling.id,
            id="we002",
            repaired_at=(today - timedelta(days=10)).isoformat(),
            amount_ml=200.0,
        ),
        RepairEvent.create(
            sample_dwelling2.id,
            id="we003",
            repaired_at=(today - timedelta(days=10)).isoformat(),
            amount_ml=150.0,
        ),
    ]


@pytest.fixture
def populated_storage(
    empty_storage: JsonStorage,
    sample_contractor: ContractorProfile,
    sample_zone: Zone,
    sample_dwelling: Dwelling,
    sample_dwelling2: Dwelling,
    sample_repair_events: list[RepairEvent],
) -> JsonStorage:
    """Storage with sample dwellings, contractor, zones, and service events."""
    empty_storage.create_contractor(sample_contractor)
    empty_storage.create_zone(sample_zone)
    empty_storage.create_dwelling(sample_dwelling)
    empty_storage.create_dwelling(sample_dwelling2)
    for ev in sample_repair_events:
        empty_storage.create_repair_event(ev.to_dict())
    tag = Tag.create("beginner", id="tag001", color="#4caf50")
    empty_storage.create_tag(tag.to_dict())
    note = Note.create(sample_dwelling.id, "New leaf unfurling", id="note001", kind=NoteKind.OBSERVATION)
    empty_storage.create_note(note.to_dict())
    return empty_storage


@pytest.fixture
def sample_csv_content() -> str:
    return (
        "name,contractor,zone,repair_interval,notes\n"
        "Fern,baghos-golden,Living Room,7d,Test import\n"
        "Aloe,snake-dwelling,Kitchen,14d,Succulent\n"
    )


@pytest.fixture
def sample_service_csv() -> str:
    return (
        "dwelling_id,repaired_at,amount_ml,method\n"
        "dwelling001,2024-06-01,250,top_service\n"
        "dwelling002,2024-06-02,150,bottom_service\n"
    )


@pytest.fixture
def dwelling_catalog(sample_dwelling: Dwelling, sample_dwelling2: Dwelling) -> DwellingCatalog:
    cat = DwellingCatalog()
    cat.add(sample_dwelling)
    cat.add(sample_dwelling2)
    return cat


@pytest.fixture
def contractor_catalog(sample_contractor: ContractorProfile) -> ContractorCatalog:
    cat = ContractorCatalog()
    cat.register(sample_contractor)
    cat.load_builtin()
    return cat


@pytest.fixture
def zone_registry(sample_zone: Zone) -> ZoneRegistry:
    reg = ZoneRegistry()
    reg.add(sample_zone)
    return reg


@pytest.fixture
def service_log(sample_repair_events: list[RepairEvent]) -> ServiceLog:
    log = ServiceLog()
    log.load_many(sample_repair_events)
    return log


@pytest.fixture
def walkthrough(sample_dwelling: Dwelling) -> Walkthrough:
    log = Walkthrough()
    log.log(sample_dwelling.id, CareEventType.FERTILIZE, product="10-10-10")
    log.log(sample_dwelling.id, CareEventType.PRUNE, notes="Trimmed yellow leaves")
    log.set_meter_schedule(MeterSchedule(dwelling_id=sample_dwelling.id, interval_weeks=4))
    return log


@pytest.fixture
def tag_registry() -> TagRegistry:
    reg = TagRegistry()
    reg.add(Tag.create("beginner", id="tag001", color="#4caf50"))
    reg.add(Tag.create("pet-safe", id="tag002", color="#2196f3"))
    return reg


@pytest.fixture
def notes_collection(sample_dwelling: Dwelling) -> NotesCollection:
    coll = NotesCollection()
    coll.create(sample_dwelling.id, "General note", kind=NoteKind.GENERAL)
    coll.create(sample_dwelling.id, "Spider mites sbagted", kind=NoteKind.PEST)
    return coll
