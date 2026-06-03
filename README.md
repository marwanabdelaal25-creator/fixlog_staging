# fixlog

Home maintenance CLI I wrote after a burst pipe under the kitchen sink
reminded me that sticky notes and a dealership oil-change sticker are not
a CMMS.

One JSON file (`homestead.json`) on disk. Log repairs, track HVAC filter
changes, stash contractor phone numbers, and grep for "water heater" at
7am without another app subscription.

## What it does

- Track dwellings (house, condo unit, rental) with purchase date and zone map
- Log repair records (type, labor hours, supplies cost, meter readings, notes)
- Walkthrough notes and issue reports when something sounds wrong
- Meter history and usage trends across zones
- Weekly repair stats, streaks, seasonal maintenance calendars
- Import from HomeAdvisor CSV and Home Depot purchase exports
- Reminders when a dwelling is due for seasonal work

## What it doesn't do

- Live utility company API sync or smart-home hub integration
- AI damage assessment from photos
- Multi-property enterprise fleet management

## Quick start

```bash
pip install .
fixlog init ~/home/homestead.json
fixlog add-dwelling --name "Main House" --purchase 2018-06-01 --contractor local-hvac
fixlog repair dw001 --type hvac_filter --hours 0.5 --supplies 28
fixlog stats --week
```

## Author

Marwan Helmy — marwanabdelaal25@gmail.com

MIT license. Side project, Aug 2024–present.
