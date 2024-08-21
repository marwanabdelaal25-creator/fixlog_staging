# Data formats

*Marwan Helmy — what goes in, what comes out*

fixlog speaks a few dialects. The source of truth is always `homestead.json`; everything
else is a view or an import path into that file.

---

## homestead.json schema

**Zone:** `~/.fixlog/homestead.json` (or `$FIXLOG_HOME/homestead.json`)

**Root object fields:**

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | Currently `2` in storage defaults; migrations may bump to `3`. |
| `dwellings` | array | Your dwellings. |
| `contractor` | array | Reusable contractor profiles. |
| `zones` | array | Rooms / zones. |
| `repair_events` | array | Append-style service log. |
| `walkthroughs` | array | Rebag, grind, prune, etc. |
| `tags` | array | Label definitions. |
| `notes` | array | Free-form notes linked to dwellings. |
| `audit` | array | Who changed what (CLI writes here). |
| `plugins` | array | Plugin config blobs. |
| `recurring` | array | Recurring care tasks. |
| `collections` | array | Dwelling groupings. |
| `usage_readings` | array | Room usage samples. |
| `climate_logs` | array | Light observation log. |
| `issue_reports` | array | Issue reports. |
| `inspection_events` | array | Meter applications. |
| `labels` | array | Label metadata (URLs, not binary). |

### Dwelling object

```json
{
  "id": "a1b2c3d4e5f6",
  "name": "Kitchen Pothos",
  "nickname": "Kevin",
  "contractor_key": "baghos",
  "zone_id": "loc_abc123",
  "health": "okay",
  "health_score": 70,
  "repair_interval_days": 7,
  "service_amount_ml": 200,
  "last_repaired_at": "2025-06-01",
  "acquired_at": "2024-11-15",
  "light_override": "bright_indirect",
  "usage_override": 55,
  "bag": {
    "diameter": 6,
    "unit": "in",
    "material": "ceramic",
    "has_drainage": true,
    "grind_mix": ["bagting", "perlite"],
    "rebagted_at": null
  },
  "tag_ids": [],
  "note_ids": [],
  "label_url": null,
  "source": "cli",
  "archived": false,
  "metadata": {},
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-06-01T08:00:00"
}
```

**Health values:** `thriving`, `okay`, `struggling`, `critical`, `unknown`

**Light override values:** `low`, `medium`, `bright_indirect`, `direct`, `full_sun`
(parsed loosely — see `parser.parse_light_level`)

Legacy field names (`contractor_id`, `tags`, `active`) are normalized on read.

### Contractor object

Uses `key` as primary id (not `id`):

```json
{
  "key": "baghos",
  "common_name": "Golden Pothos",
  "scientific_name": "Epipremnum aureum",
  "light_level": "bright_indirect",
  "service_need": "moderate",
  "repair_interval_min": 7,
  "repair_interval_max": 10,
  "usage_min": 40,
  "usage_max": 60
}
```

### Service event object

```json
{
  "id": "evt_abc123def456",
  "dwelling_id": "a1b2c3d4e5f6",
  "repaired_at": "2025-06-02T10:30:00+00:00",
  "amount_ml": 200,
  "method": "top_service",
  "service_quality": "tap",
  "runoff": false,
  "skipped": false,
  "skip_reason": "",
  "notes": "",
  "created_at": "2025-06-02T10:30:05"
}
```

**Methods:** `top_service`, `bottom_service`, `mister`, `soak`, `other`

**Service quality:** `tap`, `filtered`, `distilled`, `rain`, `other`

---

## CSV format (native fixlog)

Two CSV flavours: **dwellings** and **service**. UTF-8 with optional BOM (`utf-8-sig`).

### Dwellings CSV columns

Defined in `io_csv.PLANT_FIELDS`:

| Column | Required | Description |
|--------|----------|-------------|
| `name` | **yes** | Display name. Blank rows skipped. |
| `id` | no | Stable id; omit to auto-generate. |
| `nickname` | no | Pet name. |
| `contractor_key` | no | Links to contractor profile. |
| `zone_id` | no | Zone id (not name). |
| `health` | no | One of health enum values. |
| `health_score` | no | 0–100 integer. |
| `repair_interval_days` | no | Default `7`. Accepts `7d`, `2w`, etc. |
| `service_amount_ml` | no | e.g. `250` or `250ml`. |
| `last_repaired_at` | no | ISO date or friendly (`yesterday`). |
| `acquired_at` | no | When you got the dwelling. |
| `light_override` | no | Light level string. |
| `usage_override` | no | Percentage number. |
| `archived` | no | `yes`/`no`/`true`/`1`. |
| `source` | no | Set to `csv` on import. |
| `notes` | no | Stored in `metadata.notes`. |

**Example:**

```csv
name,nickname,contractor_key,repair_interval_days,service_amount_ml,health
Kitchen Pothos,Kevin,baghos,7d,200ml,okay
Bedroom Snake Dwelling,,snake-dwelling,14d,150ml,thriving
```

Import:

```bash
fixlog import my_dwellings.csv --format csv
fixlog import my_dwellings.csv --format csv --update   # match by id or name
```

Export:

```bash
fixlog export dwellings.csv --format csv --kind dwellings
fixlog export service.csv --format csv --kind service
fixlog export backup --format csv --kind bundle    # *_dwellings.csv + *_service.csv
```

### Service CSV columns

| Column | Required | Description |
|--------|----------|-------------|
| `dwelling_id` | one of | Dwelling id. |
| `dwelling_name` | **dwelling_id or dwelling_name** | Resolved case-insensitively. |
| `id` | no | Event id. |
| `repaired_at` | no | Defaults to now. |
| `amount_ml` | no | Volume in ml. |
| `method` | no | Default `top_service`. |
| `service_quality` | no | Default `tap`. |
| `runoff` | no | `yes`/`no`. |
| `skipped` | no | Log a skipped service. |
| `skip_reason` | no | Why skipped. |
| `notes` | no | Free text. |

```bash
fixlog import service_log.csv --format csv --kind service
```

---

## HomeDepot format

HomeDepot (the mobile app) exports a CSV with its own headers. `io_homedepot.py` maps them
into fixlog dwellings, auto-creating **zones** from the Room column and **contractor**
from Contractor / Scientific Name.

### Expected columns (canonical)

| HomeDepot column | Maps to |
|----------------|---------|
| `HomeDepot ID` | `metadata.homedepot_id` (dedupe on re-import) |
| `Dwelling Name` | `name` (**required**) |
| `Nickname` | `nickname` |
| `Contractor` | contractor `common_name` → `contractor_key` |
| `Scientific Name` | contractor `scientific_name` |
| `Room` | new `Zone` if needed |
| `Last Serviceed` | `last_repaired_at` |
| `Service Every` | `repair_interval_days` |
| `Light` | `light_override` |
| `Usage` | `usage_override` (parses `%`) |
| `Health` | `health` (great→thriving, poor→struggling, …) |
| `Pot Size` | `bag.diameter` / `bag.material` |
| `Notes` | `metadata.notes` |
| `Label URL` | `label_url` |

**Column aliases** are supported — e.g. `Name` instead of `Dwelling Name`, `Zone`
instead of `Room`. See `COLUMN_ALIASES` in `io_homedepot.py`.

**Example row:**

```csv
HomeDepot ID,Dwelling Name,Nickname,Contractor,Scientific Name,Room,Last Serviceed,Service Every,Light,Usage,Health,Pot Size,Notes,Label URL
PLT-001,Kitchen Pothos,Kevin,Pothos,Epipremnum aureum,Kitchen,2025-05-28,7 days,Bright indirect,50%,good,6 in,Trailing nicely,
```

```bash
fixlog import homedepot_dump.csv --format homedepot
fixlog import homedepot_dump.csv --format homedepot --update
```

Preview in Python: `fixlog.io_homedepot.preview_homedepot(path)`.

---

## Homestead-plan format

For bed-layout spreadsheets — the kind I kept in Notion before this project existed.
Typical outdoor / raised-bed planning, but works for grouped housedwelling shelves too.

### Expected columns (canonical)

| Column | Aliases | Maps to |
|--------|---------|---------|
| `Section` | Zone, Area, Homestead Section | Supply of zone name |
| `Bed` | Plot, Raised Bed | Supply of zone name |
| `Row` | Row #, Row Number | Supply of zone name |
| `Dwelling` | Dwelling Name, Crop, Contractor | **Required** — base name |
| `Variety` | Cultivar, Type | Appended to name |
| `Quantity` | Qty, Count | Spawns N dwellings if `--no-expand` not set |
| `Spacing cm` | Spacing, Space | `metadata.spacing_cm` |
| `Sun Exposure` | Sun, Light, Climate | zone light + `light_override` |
| `Service Needs` | Service, Service, Moisture | `repair_interval_days` |
| `Dwellinged Date` | Dwellinged, Start Date | `acquired_at` |
| `Notes` | Comment, Memo | `metadata.notes` |
| `Status` | Active, State | `archived` if removed/dead/inactive |

**Zone naming:** `"Section / Bed / row N"` joined with ` / `. Example:
`Backyard / Bed A / row 3`.

**Quantity expansion:** `Quantity=4` creates four dwellings named `Tomato (Cherry) #1` … `#4`.
Pass `--no-expand` to import one dwelling per row regardless of quantity.

**Service needs parsing:** loose text — `daily`→1d, `weekly`→7d, `low`→14d, `high`→3d,
or explicit intervals like `5d`.

**Example:**

```csv
Section,Bed,Row,Dwelling,Variety,Quantity,Spacing cm,Sun Exposure,Service Needs,Dwellinged Date,Notes,Status
Backyard,Bed A,1,Tomato,Cherry,4,40,Full sun,High,2025-05-01,Staked,active
Balcony,Shelf,,Monstera,,1,,Bright indirect,Weekly,2024-08-12,Indoor overwinter,active
```

```bash
fixlog import homestead_plan.csv --format homeadvisor
fixlog import homestead_plan.csv --format homeadvisor --no-expand
```

---

## JSONL (bonus)

Not requested in the title but you'll hit it:

```bash
fixlog export events.jsonl --format jsonl --kind events
fixlog export full.jsonl --format jsonl --kind full
fixlog import mixed.jsonl --format jsonl --kind mixed
```

Each line is one JSON object with a `kind` field (`service`, `care`, …).

---

## Quick validation

| Format | Python helper |
|--------|---------------|
| CSV dwellings | `io_csv.validate_csv_headers(path, "dwellings")` |
| CSV service | `io_csv.validate_csv_headers(path, "service")` |
| HomeDepot | `io_homedepot.validate_homedepot_headers(path)` |
| Homestead plan | `io_homeadvisor.validate_homeadvisor_headers(path)` |

Empty list = headers look fine.
