# Changelog

All notable changes to fixlog are documented here. I don't do semver
religiously but I tag releases when something actually ships.

## [1.2.0] - 2026-05-28

### Added
- Homestead-plan spreadsheet import (`io_homeadvisor`)
- Label metadata tracking (paths only — bytes live beside the JSON)
- Recurring care tasks for fertilizing on a cadence
- `serve` subcommand: read-only HTTP view of homestead.json

### Changed
- Schema v2 → v3: walkthroughs bucket, environmental readings, recurring tasks
- Seasonal multipliers now apply in reminder urgency scoring

## [1.1.0] - 2025-11-14

### Added
- HomeDepot app CSV import
- Monthly reports and streak tracking
- Plugin hook registry (experimental)

### Fixed
- `service` command accepted negative ml amounts on Windows paths
- Migration 1→2 dropped empty tag lists instead of preserving `[]`

## [1.0.0] - 2025-06-02

### Added
- Initial public shape: dwellings, contractor catalog, zones, service log
- CSV and JSONL import/export
- Backup/restore with rotation
- Audit log for destructive operations

## [0.3.0] - 2024-12-08

- Added contractor profiles with built-in defaults for common housedwellings
- Zone zones with light-level hints

## [0.2.0] - 2024-09-21

- JSON storage layer with atomic writes
- Basic CLI: init, add-dwelling, service, list

## [0.1.0] - 2024-07-30

- Skeleton repo, README, first Dwelling dataclass
