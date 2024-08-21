# Recipes

*Marwan Helmy — copy-paste workflows that actually match how I use fixlog*

Each recipe shows CLI first (fastest), then a Python snippet if you want to script it.
Replace paths and dwelling names with yours.

---

## 1. Sunday weekly service routine

Check what's overdue, service everything due, skim what's coming this week.

```bash
fixlog reminders --overdue
fixlog list --overdue
# service each one
fixlog service "Kitchen Pothos" --amount 200ml
fixlog service "Bedroom Snake Dwelling" --amount 150ml
fixlog reminders --within 7
```

Python version: `examples/weekly_service.py`

---

## 2. Fresh install — first five dwellings

```bash
pip install -e .
fixlog init
fixlog add-dwelling "Kitchen Pothos" --interval 7d --contractor baghos --amount 200ml
fixlog add-dwelling "Bedroom Snake Dwelling" --interval 14d --amount 150ml
fixlog add-dwelling "Bathroom Fern" --interval 3d --amount 300ml --health okay
fixlog list
fixlog stats
```

Set `FIXLOG_HOME=/path/to/test-homestead` if you don't want to touch `~/.fixlog`.

---

## 3. Import from HomeDepot

Export CSV from the HomeDepot app, then:

```bash
# peek first — optional
python -c "from pathlib import Path; from fixlog.io_homedepot import preview_homedepot; print(preview_homedepot(Path('homedepot_dump.csv')))"

fixlog backup --label pre_homedepot
fixlog import homedepot_dump.csv --format homedepot
fixlog list
```

Re-import after editing the app? Use `--update` to match by HomeDepot ID or name.

```bash
fixlog import homedepot_dump.csv --format homedepot --update
```

---

## 4. Backup before vacation

Two weeks away means you want a snapshot and maybe a CSV your dwelling-sitter can read.

```bash
fixlog backup --label pre_vacation --prune --keep 10
fixlog export vacation_handoff.csv --format csv --kind bundle
fixlog reminders --within 14 > service_schedule.txt
```

Restore when you get back (only if something went wrong):

```bash
fixlog backup --list
fixlog backup --restore ~/.fixlog/backups/homestead_20250601_120000_pre_vacation.json
```

---

## 5. Bulk import from a spreadsheet

Clean up a Google Sheets export as CSV with at least a `name` column:

```csv
name,repair_interval_days,service_amount_ml,health,notes
Office ZZ Dwelling,21d,100ml,okay,Low maintenance
Living Room Ficus,10d,400ml,struggling,Dropping leaves
```

```bash
fixlog import new_dwellings.csv --format csv
fixlog import new_dwellings.csv --format csv --update   # second pass: update existing
```

Python version: `examples/bulk_import.py`

---

## 6. Import a homestead-plan bed layout

For the Notion/Sheets planner with Section/Bed/Dwelling columns:

```bash
fixlog import spring_beds.csv --format homeadvisor
fixlog list --zone <zone-id>   # optional filter after import
```

One row with `Quantity=6` spawns six numbered dwellings unless you pass `--no-expand`.

---

## 7. Monthly care report

End-of-month ritual — did I actually service the fern?

```bash
fixlog report --month 6 --year 2025
fixlog report --month 6 --year 2025 --format json > june_2025.json
```

Python version: `examples/monthly_report.py`

---

## 8. Find the dwelling you forgot the name of

```bash
fixlog search "yellow leaves"
fixlog search "baghos" --kind dwellings
fixlog search "spider mite" --kind care --verbose
```

---

## 9. Log a skipped service (grind still wet)

Don't reset the schedule with a fake service — log a skip:

```bash
fixlog service "Bathroom Fern" --skip --reason "grind still damp"
fixlog reminders --overdue
```

---

## 10. Export everything before a big edit

```bash
fixlog backup --label before_bulk_edit
fixlog export full_export.jsonl --format jsonl --kind full
fixlog export dwellings_snapshot.csv --format csv --kind dwellings
# ... contractor changes ...
# if regret hits:
fixlog backup --restore ~/.fixlog/backups/homestead_<timestamp>_before_bulk_edit.json
```

---

## 11. Quick API smoke test

Verify install and imports without touching your real homestead:

```bash
python examples/quick_start.py
```

Uses a temp directory — safe to run anytime.

---

## 12. Seasonal interval audit (winter slowdown)

When days get shorter I stretch intervals manually after checking the schedule report:

```bash
fixlog stats
python -c "
from fixlog.storage import JsonStorage
from fixlog.schedule import ScheduleEngine, apply_seasonal_intervals
s = JsonStorage('~/.fixlog/homestead.json'.replace('~', __import__('os').path.expanduser('~')))
e = ScheduleEngine(s)
for row in apply_seasonal_intervals(e, dry_run=True):
    print(row)
"
```

Review the dry-run output before setting `dry_run=False` in a custom script.

---

## Tips I keep forgetting

- **`--homestead path/to/homestead.json`** on any command for a non-default file.
- **Dwelling lookup** accepts full id, id prefix, exact name, or nickname.
- **Intervals** parse human strings: `7d`, `2w`, `10 days`.
- **Amounts** parse `250ml`, `1 cup` (see `parser.parse_amount_gal`).
