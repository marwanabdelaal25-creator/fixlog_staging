#!/usr/bin/env python3
"""Generate large homestead JSON fixtures (stdlib only)."""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "homesteads"

ZONES = ["kitchen", "basement", "attic", "garage-zone", "hvac-closet", "utility-room"]
CONTRACTOR_KEYS = [
    "local-hvac", "roof-guy", "plumber-mike", "electric-co", "handyman-dan",
    "window-shop", "gutter-crew", "appliance-fix", "pest-control", "landscape-pro",
]
PERSONAS = [
    "hvac_filter_nut", "weekend_landlord", "smoke_detector_travel", "winter_prep_batch", "single_contractor_only",
    "summer_beater", "guest_rental", "company_units", "family_duplex", "two_home_owner",
]


def _dwelling_name(rng: random.Random, n: int) -> str:
    adj = rng.choice(["Fresh", "Resting", "Peak", "Old", "Sample", "Backup"])
    sp = rng.choice(CONTRACTOR_KEYS).replace("-", " ").title()
    return f"{adj} {sp} #{n}"


def _dwelling_entry(rng: random.Random, idx: int, year: int) -> dict:
    purchase = date(year, rng.randint(1, 12), rng.randint(1, 28))
    interval = rng.choice([30, 60, 90, 180, 365])
    last = purchase + timedelta(days=rng.randint(0, interval // 2))
    return {
        "id": f"dw-{year}-{idx:06d}",
        "name": _dwelling_name(rng, idx),
        "contractor_key": rng.choice(CONTRACTOR_KEYS),
        "zone_id": f"zn-{rng.choice(ZONES)}",
        "repair_interval_days": interval,
        "last_repaired": last.isoformat(),
        "purchase_date": purchase.isoformat(),
        "labor_hours": rng.choice([1, 2, 4, 8]),
        "tag_ids": [f"tag-{rng.randint(1, 12)}" for _ in range(rng.randint(0, 2))],
        "notes": rng.choice(["", "rental unit", "weekend place", "guest house"]),
    }


def _repair_events(rng: random.Random, dwellings: list[dict], count: int) -> list[dict]:
    out = []
    for _ in range(count):
        d = rng.choice(dwellings)
        dt = date.fromisoformat(d["last_repaired"]) - timedelta(days=rng.randint(0, 30))
        out.append({
            "id": f"rp-{rng.randint(1, 999999):06d}",
            "dwelling_id": d["id"],
            "repaired_at": dt.isoformat(),
            "method": rng.choice(["hvac_filter", "gutter_clean", "smoke_detector", "water_heater_flush", "outlet_test"]),
            "labor_hours": d.get("labor_hours", 2),
            "supplies_cost": rng.randint(25, 450),
        })
    return out


def _homestead(rng: random.Random, name: str, dwellings_n: int) -> dict:
    dwellings = [_dwelling_entry(rng, i, rng.randint(2015, 2025)) for i in range(dwellings_n)]
    return {
        "schema_version": 2,
        "meta": {"name": name, "persona": rng.choice(PERSONAS)},
        "dwellings": dwellings,
        "contractors": [{"key": k, "name": k.replace("-", " ").title()} for k in CONTRACTOR_KEYS],
        "zones": [{"id": f"zn-{z}", "name": z} for z in ZONES],
        "repair_events": _repair_events(rng, dwellings, min(dwellings_n * 3, 8000)),
        "walkthrough_logs": [],
        "tags": [],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7291846)
    mega = _homestead(rng, "megahomestead", 4200)
    (OUT / "megahomestead.json").write_text(json.dumps(mega, indent=0), encoding="utf-8")
    for persona in PERSONAS:
        h = _homestead(rng, persona, rng.randint(40, 120))
        (OUT / f"{persona}.json").write_text(json.dumps(h, indent=0), encoding="utf-8")
    for year in range(2018, 2026):
        h = _homestead(rng, f"year-{year}", rng.randint(80, 200))
        (OUT / f"snapshot_{year}.json").write_text(json.dumps(h), encoding="utf-8")
    print("Wrote fixtures to", OUT)


if __name__ == "__main__":
    main()
