#!/usr/bin/env python3
"""Build data/towns.csv: every Colorado city, town and CDP with its county and an interior point.

Sources (US Census Bureau, public domain):
  - 2024 Gazetteer places file (interior point), via scripts/build_places.py's cached download
  - 2020 place-by-county reference file (which county or counties each place is in)
  - 2024 Gazetteer counties file (county interior point; used only to pick one county for a place
    that spans several: the county whose interior point is nearest the place's point)

scripts/export_app.py snaps hidden-address pins to the nearest town in this file, limited to the
counties requested. Rows already in data/towns.csv keep their values (the first five are Chaffee towns).
Run:  python scripts/build_towns.py
"""
from __future__ import annotations

import csv
import math
import urllib.request
from pathlib import Path

import build_places as bp

REPO = bp.REPO
OUT = REPO / "data" / "towns.csv"
PLACE_COUNTY = "https://www2.census.gov/geo/docs/reference/codes2020/place_by_cou/st08_co_place_by_county2020.txt"
FILES = {**bp.FILES, "counties": "2024_Gaz_counties_national.zip"}
bp.FILES.update(FILES)


def place_counties() -> dict[str, list[str]]:
    path = bp.CACHE / "st08_co_place_by_county2020.txt"
    if not path.exists():
        bp.CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(PLACE_COUNTY, timeout=60) as resp:
            path.write_bytes(resp.read())
    out: dict[str, list[str]] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("|")
    for line in lines[1:]:
        r = dict(zip(head, line.split("|")))
        out.setdefault("08" + r["PLACEFP"], []).append("08" + r["COUNTYFP"])
    return out


def main() -> None:
    cent = {r["GEOID"]: (float(r["INTPTLAT"]), float(r["INTPTLONG"]))
            for r in bp.rows("counties") if r["USPS"] == "CO"}
    pc = place_counties()
    with OUT.open(encoding="utf-8", newline="") as f:
        existing = list(csv.DictReader(f))
    seen = {r["name"] for r in existing}
    new = []
    for r in bp.rows("places"):
        if r["USPS"] != "CO":
            continue
        name = bp.SUFFIX.sub("", r["NAME"])
        counties = pc.get(r["GEOID"])
        if not counties or name in seen:
            continue
        lat, lon = float(r["INTPTLAT"]), float(r["INTPTLONG"])
        fips = min(counties, key=lambda c: math.hypot(lat - cent[c][0], (lon - cent[c][1]) * 0.78))
        seen.add(name)
        new.append({"name": name, "county_fips": fips, "lat": f"{lat:.4f}", "lon": f"{lon:.4f}"})
    new.sort(key=lambda r: (r["county_fips"], r["name"]))
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "county_fips", "lat", "lon"], lineterminator="\n")
        w.writeheader()
        w.writerows(existing + new)
    print(f"{len(existing)} kept + {len(new)} added -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
