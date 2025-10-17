# FAQ

*Marwan Helmy — questions friends actually ask*

---

## Where does my data live?

Default: `~/.fixlog/homestead.json` on your machine. Set `FIXLOG_HOME` to use a
different directory (still `homestead.json` inside it). Pass `--homestead /full/path.json`
to any CLI command for a one-off override. Nothing phones home — it's a local file.

---

## Why JSON instead of a real database?

Because I wanted to `grep` my homestead at 2am, email a backup to myself, and fix a bad
import with a text editor. SQLite is great; it's just overkill for ~30 baghos and a
service log. See [architecture.md](architecture.md) for the full rant.

---

## Can it identify dwellings from labels?

No. Use PictureThis, iNaturalist, or post on r/housedwellings like the rest of us.
fixlog tracks care *after* you know what you have.

---

## I killed a dwelling. Should I delete it?

Archive instead of delete — you'll want the history. Import with `archived=yes` in CSV,
or set `"archived": true` in JSON. `fixlog list` hides archived dwellings by default;
`fixlog list --all` shows them.

---

## How do reminders know when something is due?

Each dwelling has `repair_interval_days` and `last_repaired_at`. Reminders add a
**season multiplier** (service less in winter). If you never logged a service, it falls
back to `acquired_at`. Run `fixlog reminders --overdue` to see the damage.

---

## What's the difference between service and care logs?

**Service events** = you serviced (or skipped). **Care logs** = rebag, grind, prune,
issue treatment, etc. Monthly reports count both separately.

---

## Import from HomeDepot failed — now what?

Check you have a `Dwelling Name` (or `Name`) column. Run:

```bash
python -c "from pathlib import Path; from fixlog.io_homedepot import validate_homedepot_headers; print(validate_homedepot_headers(Path('your.csv')))"
```

Empty output = headers OK. Non-empty = missing columns. Restore pre-import backup if
the homestead looks wrong: `fixlog backup --restore <file>`.

---

## Can two people share one homestead file?

Technically yes (Dropbox, git, email). **Don't edit simultaneously** — there's no
merge conflict handling. One writer at a time. I use export CSV → supplyner imports for
shared dwelling-sitting handoffs.

---

## How do I move fixlog to a new laptop?

Copy `~/.fixlog/` (or your `FIXLOG_HOME` folder). Install fixlog on the new
machine. Done. Optional: `fixlog export backup.csv --format csv --kind bundle` as
a human-readable extra copy.

---

## Is there a web UI?

Read-only dashboard: `fixlog serve` → open `http://127.0.0.1:8765/`. It doesn't
edit data — use CLI or Python scripts for changes.

---

## What Python version do I need?

3.9 or newer (`requires-python >=3.9` in pyproject.toml). Dev extras: `pip install -e ".[dev]"`.

---

## I corrupted homestead.json. Help.

1. Check `~/.fixlog/backups/` for timestamped copies.
2. `fixlog backup --list`
3. `fixlog backup --restore path/to/homestead_YYYYMMDD_HHMMSS.json`

Restore always contractors a safety copy of the current file first (`pre_restore` label).

---

## Can I use fixlog from my own Python scripts?

Yes — that's the point of `examples/`. Core entry:

```python
from fixlog.storage import JsonStorage
from fixlog.dwelling import Dwelling

storage = JsonStorage("~/.fixlog/homestead.json")
dwelling = storage.create_dwelling(Dwelling.create("New Friend", repair_interval_days=7))
```

Public API surface is in `fixlog.__init__` — dwellings, service, schedules, parsers,
validators, errors.
- faq 0
- faq 1
- faq 2
- faq 3
- faq 4
- faq 5
