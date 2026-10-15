#!/usr/bin/env python3
"""Build the Colorado place + ZIP lookup used for "near a town / zip" searches.

Source: US Census Bureau 2024 Gazetteer files (public domain), which give an interior
point (lat/lng) for every incorporated place, CDP and ZIP Code Tabulation Area:
  https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/

Output: inputs/places/co_places.json
  {"places": [["Breckenridge", 39.49946, -106.043243], ...],   # sorted by name
   "zips":   {"80424": [39.47, -106.03], ...}}

The downloads are cached in .cache/gazetteer/ (git-ignored); this only needs re-running
when the Census publishes a new year. Run:  python scripts/build_places.py
"""
from __future__ import annotations

import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".cache" / "gazetteer"
OUT = REPO / "inputs" / "places" / "co_places.json"
BASE = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/"
FILES = {"places": "2024_Gaz_place_national.zip", "zips": "2024_Gaz_zcta_national.zip"}

# "Breckenridge town", "Denver city and county", "Keystone CDP" -> the name people use.
SUFFIX = re.compile(r"\s+(city and county|city|town|CDP|village)$")


def rows(kind: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / FILES[kind]
    if not path.exists():
        with urllib.request.urlopen(BASE + FILES[kind], timeout=60) as resp:
            path.write_bytes(resp.read())
    with zipfile.ZipFile(path) as zf:
        text = zf.read(zf.namelist()[0]).decode("utf-8", errors="replace")
    lines = io.StringIO(text).read().splitlines()
    head = [h.strip() for h in lines[0].split("\t")]
    for line in lines[1:]:
        yield dict(zip(head, (v.strip() for v in line.split("\t"))))


def in_colorado(lat: float, lng: float) -> bool:
    return 36.9 <= lat <= 41.1 and -109.1 <= lng <= -102.0


def main() -> None:
    places = {}
    for r in rows("places"):
        if r["USPS"] != "CO":
            continue
        name = SUFFIX.sub("", r["NAME"])
        places[name] = [name, round(float(r["INTPTLAT"]), 5), round(float(r["INTPTLONG"]), 5)]
    zips = {}
    for r in rows("zips"):
        z, lat, lng = r["GEOID"], float(r["INTPTLAT"]), float(r["INTPTLONG"])
        if z[:2] in ("80", "81") and in_colorado(lat, lng):
            zips[z] = [round(lat, 4), round(lng, 4)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": BASE, "places": sorted(places.values()),
                               "zips": dict(sorted(zips.items()))},
                              separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(places)} places, {len(zips)} ZIPs -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
