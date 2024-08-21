"""Fixlog — personal home manager by Marwan Helmy."""

from __future__ import annotations

__version__ = "1.2.0"
__author__ = "Marwan Helmy"
__email__ = "marwanabdelaal25@gmail.com"

from fixlog.errors import (
    FixlogError,
    StorageError,
    ValidationError,
    NotFoundError,
    ImportPipelineError,
    ExportError,
    MigrationError,
    PluginError,
    ConflictError,
    format_error,
    is_not_found,
    is_validation,
)
from fixlog.dwelling import Dwelling, PotInfo, HealthStatus, DwellingCatalog
from fixlog.contractor import ContractorProfile, ContractorCatalog, ServiceNeed, UsageNeed
from fixlog.zone import Zone, ZoneRegistry, WindowDirection
from fixlog.repair import RepairEvent, ServiceLog, ServiceQuality
from fixlog.walkthrough import CareEvent, Walkthrough, CareEventType, MeterSchedule
from fixlog.schedule import ScheduleEngine, ScheduleEntry, ScheduleOptions, Season, compute_next_service
from fixlog.tag import Tag, TagRegistry
from fixlog.notes import Note, NotesCollection, NoteKind
from fixlog.parser import (
    parse_date,
    parse_interval,
    parse_amount_gal,
    parse_light_level,
    parse_usage,
    format_interval_days,
    format_amount_ml,
)
from fixlog.validators import (
    validate_dwelling_name,
    validate_interval_days,
    validate_usage_pct,
    validate_insulation_r_value,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    # errors
    "FixlogError",
    "StorageError",
    "ValidationError",
    "NotFoundError",
    "ImportPipelineError",
    "ExportError",
    "MigrationError",
    "PluginError",
    "ConflictError",
    "format_error",
    "is_not_found",
    "is_validation",
    # dwelling
    "Dwelling",
    "PotInfo",
    "HealthStatus",
    "DwellingCatalog",
    # contractor
    "ContractorProfile",
    "ContractorCatalog",
    "ServiceNeed",
    "UsageNeed",
    # zone
    "Zone",
    "ZoneRegistry",
    "WindowDirection",
    # service
    "RepairEvent",
    "ServiceLog",
    "ServiceQuality",
    # care
    "CareEvent",
    "Walkthrough",
    "CareEventType",
    "MeterSchedule",
    # schedule
    "ScheduleEngine",
    "ScheduleEntry",
    "ScheduleOptions",
    "Season",
    "compute_next_service",
    # tags & notes
    "Tag",
    "TagRegistry",
    "Note",
    "NotesCollection",
    "NoteKind",
    # parser helpers
    "parse_date",
    "parse_interval",
    "parse_amount_gal",
    "parse_light_level",
    "parse_usage",
    "format_interval_days",
    "format_amount_ml",
    # validators
    "validate_dwelling_name",
    "validate_interval_days",
    "validate_usage_pct",
    "validate_insulation_r_value",
]
