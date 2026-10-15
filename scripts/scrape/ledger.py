"""Append-only transaction ledger for the Phase 2 dataset.

Every build compares the records it just produced with the state saved after the previous
build and appends one row per event to inputs/ledger/transactions.csv:

  baseline  the record was already present when the ledger started (true first-seen date
            is unknown, only "on or before this date")
  added     a record that was not in the previous build
  changed   a tracked field changed (Field / Old Value / New Value filled in)
  closed    Status went Open -> Closed
  reopened  Status went Closed -> Open
  removed   the record left the dataset

The ledger is never rewritten, only appended to, so it answers "when did we first see
this farm" (its `added` or `baseline` row), "what changed and when", and, with the
`Year Opened` column, "how long has it been in business". A rebuild with nothing new
appends nothing. A rename shows as removed + added (records are keyed by name + town).

Usage:
  python scripts/scrape/ledger.py bootstrap origin/main   # once: baseline from a git ref
  python scripts/scrape/ledger.py history "Thistle Whistle Farm" [city]
The build calls update() itself (batch label: LEDGER_BATCH env var, date: LEDGER_DATE).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from scrape.normalize import name_key  # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
DIR = os.path.join(REPO, "inputs", "ledger")
LOG = os.path.join(DIR, "transactions.csv")
STATE = os.path.join(DIR, "state.json")
RAW_REL = "source-data/phase2/co_farmers_markets_all_raw.csv"
FIELDS = ["Date", "Event", "Business Name", "City", "Field", "Old Value", "New Value",
          "Source", "Batch", "Note"]
# column label -> Market attribute; notes, coordinates and provenance are too noisy to log
TRACKED = {"Category": "category", "Address": "address", "County": "county", "Phone": "phone",
           "Website": "website", "Email": "email", "Hours": "hours", "Months Open": "months_open",
           "Products": "products", "Year Opened": "year_opened"}


def key(name: str, city: str) -> str:
    return f"{name_key(name)}|{(city or '').strip().lower()}"


def _today() -> str:
    return os.environ.get("LEDGER_DATE") or dt.date.today().isoformat()


def snapshot_of(markets) -> dict:
    out = {}
    for m in markets:
        rec = {"name": m.business_name, "city": m.city, "source": m.source,
               "Status": "Closed" if m.status == "Closed" else "Open"}
        for col, attr in TRACKED.items():
            rec[col] = str(getattr(m, attr, "") or "")
        out[key(m.business_name, m.city)] = rec
    return out


def diff(old: dict, new: dict, date: str, batch: str, baseline: bool = False) -> list:
    rows = []

    def row(event, rec, **kw):
        rows.append({"Date": date, "Event": event, "Business Name": rec["name"], "City": rec["city"],
                     "Field": kw.get("field", ""), "Old Value": kw.get("old", ""),
                     "New Value": kw.get("new", ""), "Source": kw.get("source", rec.get("source", "")),
                     "Batch": batch, "Note": kw.get("note", "")})
    for k, rec in sorted(new.items()):
        if k not in old:
            row("baseline" if baseline else "added", rec,
                note="present when the ledger started; first-seen date is this or earlier" if baseline else "")
            if rec["Status"] == "Closed":
                row("closed", rec, field="Status", old="Open", new="Closed")
            continue
        prev = old[k]
        if prev.get("Status") != rec["Status"]:
            row("closed" if rec["Status"] == "Closed" else "reopened", rec,
                field="Status", old=prev.get("Status", ""), new=rec["Status"])
        for col in TRACKED:
            if (prev.get(col) or "") != (rec.get(col) or ""):
                row("changed", rec, field=col, old=prev.get(col, ""), new=rec.get(col, ""))
    for k, rec in sorted(old.items()):
        if k not in new:
            row("removed", rec)
    return rows


def _append(rows: list) -> None:
    os.makedirs(DIR, exist_ok=True)
    new_file = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)


def update(markets, batch: str | None = None) -> int:
    """Append this build's events and save the new state. Returns the number of events."""
    new = snapshot_of(markets)
    baseline = not os.path.exists(STATE)
    old = {} if baseline else json.load(open(STATE, encoding="utf-8"))
    rows = diff(old, new, _today(), batch or os.environ.get("LEDGER_BATCH") or "build", baseline)
    _append(rows)
    os.makedirs(DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(new, fh, ensure_ascii=False, sort_keys=True, indent=0)
    return len(rows)


def bootstrap(ref: str) -> None:
    """Seed the ledger from the raw CSV at a git ref (e.g. origin/main): every record in it
    is a baseline entry dated that commit; the next build logs what is new since."""
    if os.path.exists(STATE):
        sys.exit("ledger already started; refusing to bootstrap again")
    text = subprocess.check_output(["git", "show", f"{ref}:{RAW_REL}"], cwd=REPO).decode("utf-8-sig")
    date = subprocess.check_output(["git", "log", "-1", "--format=%cs", ref], cwd=REPO).decode().strip()
    state = {}
    for r in csv.DictReader(io.StringIO(text)):
        rec = {"name": r["Business Name"], "city": r["City"], "source": r.get("Source", ""),
               "Status": r.get("Status") or "Open"}
        for col in TRACKED:
            rec[col] = r.get(col, "") or ""
        state[key(r["Business Name"], r["City"])] = rec
    rows = diff({}, state, date, f"baseline from {ref}", baseline=True)
    _append(rows)
    os.makedirs(DIR, exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True, indent=0)
    print(f"bootstrapped {len(rows)} baseline entries dated {date} from {ref}")


def history(name: str, city: str = "") -> None:
    k = name_key(name)
    rows = [r for r in csv.DictReader(open(LOG, encoding="utf-8"))
            if name_key(r["Business Name"]) == k and (not city or r["City"].lower() == city.lower())]
    if not rows:
        print("no ledger entries")
        return
    for r in rows:
        extra = f" {r['Field']}: {r['Old Value']!r} -> {r['New Value']!r}" if r["Field"] else ""
        print(f"{r['Date']}  {r['Event']:<8}{extra}  [{r['Batch']}]")
    first = rows[0]
    print(f"first entry: {first['Date']} ({first['Event']})")
    state = json.load(open(STATE, encoding="utf-8")).get(key(name, rows[0]["City"]), {})
    year = state.get("Year Opened", "")
    if year.isdigit():
        closed = next((r["Date"][:4] for r in rows if r["Event"] == "closed"), "")
        end = int(closed) if closed else dt.date.today().year
        print(f"opened {year}: about {end - int(year)} years {'before closing' if closed else 'in business'}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "bootstrap":
        bootstrap(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "history":
        history(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        sys.exit(__doc__)
