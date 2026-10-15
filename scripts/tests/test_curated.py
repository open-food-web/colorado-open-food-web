"""Offline tests for the curated new-records source (curated_records.csv)."""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape.sources import curated

HEADER = ["Business Name", "Category", "Address", "City", "Zip", "Phone", "Website",
          "Facebook", "Products", "Hours", "Notes", "Latitude", "Longitude",
          "Status", "Source URLs", "Researched"]


def _write(tmp_path, rows):
    p = tmp_path / "curated_records.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})
    return str(p)


def test_only_status_add_rows_become_records(tmp_path):
    path = _write(tmp_path, [
        {"Business Name": "Stand Farm", "Category": "Roadside Market", "Status": "add",
         "Address": "1 Main St", "City": "Salida", "Zip": "81201",
         "Source URLs": "https://stand.example/ ; https://fb.example/stand", "Researched": "2026-10-04"},
        {"Business Name": "Market Only Bakery", "Status": "market-only"},
        {"Business Name": "Ghost Farm", "Status": "skip"},
        {"Business Name": "", "Status": "add"},
    ])
    ms = curated.fetch(path)
    assert [m.business_name for m in ms] == ["Stand Farm"]
    m = ms[0]
    assert m.category == "Roadside Market"
    assert (m.address, m.city, m.zip) == ("1 Main St", "Salida", "81201")
    assert m.provenance["Address"] == "curated" and m.source == "curated"
    assert m.source_id == "https://stand.example/"       # first source URL
    assert m.source_updated == "2026-10-04"


def test_normalizes_and_keeps_explicit_only(tmp_path):
    path = _write(tmp_path, [{
        "Business Name": "Bakeshop", "Category": "Bakery", "Status": "ADD",
        "Phone": "7195551234", "Website": "bakeshop.example", "Zip": "Alma CO 80420",
    }])
    m = curated.fetch(path)[0]
    assert m.phone == "(719) 555-1234"
    assert m.website.startswith("http") and "bakeshop.example" in m.website
    assert m.zip == "80420"
    assert m.address == "" and m.hours == "" and m.latitude is None   # nothing invented


def test_coordinates_are_optional(tmp_path):
    path = _write(tmp_path, [
        {"Business Name": "Pinned", "Status": "add", "Latitude": "38.53", "Longitude": "-106.0"},
        {"Business Name": "Unpinned", "Status": "add", "Latitude": "n/a"},
    ])
    pinned, unpinned = curated.fetch(path)
    assert (pinned.latitude, pinned.longitude, pinned.geo_source) == (38.53, -106.0, "source")
    assert unpinned.latitude is None and unpinned.geo_source == ""


def test_missing_file_is_empty(tmp_path):
    assert curated.fetch(str(tmp_path / "nope.csv")) == []
