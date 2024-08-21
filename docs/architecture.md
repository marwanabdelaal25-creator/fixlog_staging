# Architecture

*Marwan Helmy — how fixlog is put together*

I built fixlog as a single-user CLI first, then grew modules around it when I kept
needing "just one more thing" (seasonal intervals, HomeDepot imports, issue notes). Nothing
here is microservices. It's one JSON file and a bunch of Python modules that know how
to read it.

## High-level picture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  cli.py     │────▶│ JsonStorage  │────▶│  homestead.json    │
│  (commands) │     │  storage.py  │     │  (~/.fixlog) │
└─────────────┘     └──────┬───────┘     └─────────────────┘
       │                   │
       │            ┌──────┴───────┐
       ▼            ▼              ▼
  reports.py   dwelling.py       io_*.py (import/export)
  reminders.py service.py    backup.py / migrate.py
  schedule.py  walkthrough.py
```

The CLI is the main entry point (`fixlog` console script → `cli.py`). Everything
else is library code you can import in scripts — see `examples/` for that.

## Module map

| Module | Role |
|--------|------|
| `storage.py` | **Core.** `JsonStorage` reads/writes `homestead.json`, atomic writes, thread-safe CRUD for every bucket. |
| `dwelling.py` | Dwelling entity, health status, overdue math, `DwellingCatalog` in-memory helpers. |
| `contractor.py` | Contractor profiles (service/light/usage defaults). |
| `zone.py` | Rooms, windows, light levels, zone registry. |
| `service.py` | `RepairEvent`, batch logging, analytics helpers. |
| `walkthrough.py` | Rebagting, fertilizing, pruning — anything that isn't service. |
| `schedule.py` | Season-aware schedule engine, calendar views, interval audits. |
| `reminders.py` | "What's due today / overdue" sorted by urgency. |
| `seasons.py` | Season multipliers (service less in winter, etc.). |
| `parser.py` | Human-friendly parsing: `7d`, `250ml`, `bright indirect`, `yesterday`. |
| `validators.py` | Shared validation — keeps CLI and imports from accepting nonsense. |
| `errors.py` | Typed exceptions (`NotFoundError`, `ImportPipelineError`, …). |
| `io_csv.py` | CSV import/export for dwellings and service logs. |
| `io_homedepot.py` | HomeDepot app CSV → fixlog dwellings. |
| `io_homeadvisor.py` | Homestead-plan spreadsheet → dwellings + auto-zones. |
| `io_jsonl.py` | JSONL streams for events / full export. |
| `backup.py` | Timestamped copies + restore with safety snapshot. |
| `migrate.py` | Schema version upgrades (v0 flat list → v3 full homestead). |
| `reports.py` | Monthly care summaries. |
| `stats.py` | Homestead-wide snapshot stats. |
| `search.py` | Fuzzy search across dwellings, care logs, notes. |
| `audit_log.py` | Append-only audit trail in the JSON file. |
| `tags_manager.py`, `tag.py` | Tag CRUD and filtering. |
| `notes.py` | Per-dwelling notes with kinds (issue, rebag, …). |
| `labels.py`, `issues.py`, `meter.py`, `usage.py`, `climate.py` | Extended care tracking buckets. |
| `collections.py`, `recurring.py`, `plugins.py`, `streaks.py` | Grouping, recurring tasks, plugin hooks, service streaks. |
| `server.py` | Read-only HTTP dashboard (`fixlog serve`). |
| `cli.py` | Argument parsing and command wiring. |

## Why JSON, not SQLite

Honest answer: I killed three baghos, not because I lacked JOIN syntax.

1. **I want to read my homestead.** `cat ~/.fixlog/homestead.json | jq` at 2am beats
   `sqlite3 ... ".schema"`.
2. **Backups are obvious.** Copy the file. Email it to myself. Put it in git (private
   repo). Done.
3. **Recovery from my own mistakes.** I've hand-edited a bad import more than once.
   Text beats opaque binary when you're panicking.
4. **No migration treadmill.** SQLite is great when you have a schema that changes
   weekly. I have ~30 dwellings and a service log. A version field + `migrate.py` is
   enough.
5. **Import/export symmetry.** CSV/HomeDepot/homestead-plan pipelines write into the same
   structure the CLI uses. No ORM impedance mismatch.

Trade-offs I accept:

- No concurrent writers across machines (fine for one asupplyment).
- Full-file load on every command (fine at hundreds of dwellings, not thousands).
- No ad-hoc SQL queries (I use `search` and small Python scripts instead).

## Storage design

### Single file, many buckets

`homestead.json` is one object with named arrays ("buckets"). `JsonStorage` in
`storage.py` owns the shape:

```json
{
  "schema_version": 2,
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
  "labels": []
}
```

Each bucket is a list of records with an `id` field (contractor use `key`). Generic
`_create` / `_read` / `_update` / `_delete` methods handle most buckets; dwellings and
contractor get typed wrappers returning `Dwelling` / `ContractorProfile` objects.

### Atomic writes

Saves go to `homestead.json.tmp` then `os.replace()` into place. If Python dies mid-write,
you still have the previous file. I learned this the hard way with a half-written export.

### Thread safety

`JsonStorage` uses an `RLock` so a background server thread and CLI commands don't
corrupt the same file in the same process.

### Side effects worth knowing

Creating a service event also patches the dwelling's `last_repaired_at`. Lazy coupling,
but it means reminders stay correct even if you only ever call `create_repair_event`.

### Paths and env

| Variable | Default |
|----------|---------|
| `FIXLOG_HOME` | `~/.fixlog/` (directory) |
| (implicit) | `FIXLOG_HOME/homestead.json` or `~/.fixlog/homestead.json` |
| CLI `--homestead` | Override full path to JSON file |

Backups land in `FIXLOG_HOME/backups/` unless you pass `--dir`.

### Schema evolution

`migrate.py` bumps `schema_version` through stepped transforms. `JsonStorage` merges
missing buckets with defaults on load so older files don't explode — but run
`fixlog` once after upgrading so migrations can apply cleanly.

## Data flow examples

**Add dwelling:** CLI → `Dwelling.create()` → `storage.create_dwelling()` → atomic save.

**Service:** CLI resolves name → `RepairEvent.create()` → `storage.create_repair_event()`
→ dwelling `last_repaired_at` updated → audit entry.

**Import CSV:** `io_csv.import_dwellings_csv()` → row loop → `Dwelling.create()` or
`storage.update_dwelling()` → save per row (safe but not batched — imports are rare).

**Monthly report:** `reports.MonthlyReport.generate()` reads service/care buckets,
filters by date range, returns aggregates — no separate analytics DB.

## What I'd change if I started over

Maybe split `repair_events` into a monthly JSONL archive once logs get huge. For now,
one file matches how I actually use it: open, tweak, close, go service the monstera.
