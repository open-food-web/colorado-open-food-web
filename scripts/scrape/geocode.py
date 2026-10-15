"""Free, key-less geocoding + county lookup.

Two public services, both no-key and generous for our volume (~150 rows):

  * US Census Geocoder  -> forward geocode an address to lat/lon *and* county.
    https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress
  * FCC Area API        -> reverse lookup a county name from lat/lon (for records
    that already have coordinates from their source but no county).
    https://geo.fcc.gov/api/census/block/find

Every coordinate produced here is tagged geo_source='census-geocoder' so the map/raw
CSV can distinguish source-provided pins from derived ones (the geocode+flag rule).
Network calls are isolated behind tiny functions so tests can monkeypatch them.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Optional, Tuple

UA = {"User-Agent": "ColoradoFarmTrail/1.0 (+https://github.com) data build"}
CENSUS = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
FCC = "https://geo.fcc.gov/api/census/block/find"
CENSUS_COORDS = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"


def _get_json(url: str, timeout: int = 30) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def geocode_address(address: str, city: str, zipc: str) -> Optional[Tuple[float, float, str]]:
    """Forward-geocode 'address, city, CO zip'. Returns (lat, lon, county) or None.

    County comes back from the same call (Census geographies layer), so a single
    request fills both the coordinates and the County column at high confidence."""
    line = ", ".join(p for p in [address, city, "CO", zipc] if p)
    if not address or not city:
        return None
    q = urllib.parse.urlencode({
        "address": line, "benchmark": "Public_AR_Current",
        "vintage": "Current_Current", "format": "json",
    })
    data = _get_json(f"{CENSUS}?{q}")
    try:
        matches = data["result"]["addressMatches"]
        if not matches:
            return None
        m = matches[0]
        lat = float(m["coordinates"]["y"])
        lon = float(m["coordinates"]["x"])
        county = ""
        counties = m.get("geographies", {}).get("Counties", [])
        if counties:
            county = counties[0].get("NAME", "").replace(" County", "").strip()
        return lat, lon, county
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def county_for(lat: float, lon: float) -> str:
    """Reverse lookup: county name for a lat/lon (no key). '' on failure.
    FCC first; falls back to the Census coordinates endpoint (FCC had a
    server-side outage on 2026-10-03 that returned errors with HTTP 400)."""
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "format": "json"})
    data = _get_json(f"{FCC}?{q}")
    try:
        name = (data.get("County", {}).get("name") or "").strip()
    except AttributeError:
        name = ""
    if not name:
        q = urllib.parse.urlencode({
            "x": lon, "y": lat, "benchmark": "Public_AR_Current",
            "vintage": "Current_Current", "layers": "Counties", "format": "json"})
        data = _get_json(f"{CENSUS_COORDS}?{q}")
        try:
            name = data["result"]["geographies"]["Counties"][0].get("NAME", "")
        except (KeyError, IndexError, TypeError):
            name = ""
    return re.sub(r"\s+County$", "", name.strip())


# ---- persistent cache -------------------------------------------------------------
# Address geocodes and coordinate->county answers don't change between builds, so they
# are remembered in .cache/geocode.json and only new records hit the network. A miss
# (no match) is remembered too and retried only after MISS_RETRY_DAYS, so unmatchable
# addresses don't cost a lookup every build. GEOCODE_REFRESH=1 ignores everything stored.

import os as _os
import time as _time

MISS_RETRY_DAYS = 30

CACHE_PATH = _os.path.normpath(_os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "..", "..", "inputs", "geocode_cache.json"))


class GeoCache:
    def __init__(self, path: str = CACHE_PATH, refresh: bool = False,
                 geocode=None, county=None):
        self.path, self.refresh = path, refresh
        self._geocode = geocode or geocode_address
        self._county = county or county_for
        self.data = {"address": {}, "county": {}, "miss": {}}
        self.now = _time.time
        self.hits = self.lookups = 0
        if not refresh and path and _os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                self.data["address"].update(loaded.get("address", {}))
                self.data["county"].update(loaded.get("county", {}))
                self.data["miss"].update(loaded.get("miss", {}))
            except (OSError, ValueError):
                pass

    @staticmethod
    def _akey(address, city, zipc) -> str:
        return "|".join(re.sub(r"\s+", " ", (x or "").strip().lower()) for x in (address, city, zipc))

    @staticmethod
    def _ckey(lat, lon) -> str:
        return f"{round(float(lat), 5)},{round(float(lon), 5)}"

    def _recent_miss(self, k: str) -> bool:
        t = self.data["miss"].get(k)
        return t is not None and self.now() - t < MISS_RETRY_DAYS * 86400

    def geocode_address(self, address, city, zipc):
        k = self._akey(address, city, zipc)
        if k in self.data["address"]:
            self.hits += 1
            lat, lon, county = self.data["address"][k]
            return lat, lon, county
        if self._recent_miss("a:" + k):
            self.hits += 1
            return None
        self.lookups += 1
        r = self._geocode(address, city, zipc)
        if r:
            self.data["address"][k] = list(r)
            self.data["miss"].pop("a:" + k, None)
        else:
            self.data["miss"]["a:" + k] = self.now()
        return r

    def county_for(self, lat, lon):
        k = self._ckey(lat, lon)
        if k in self.data["county"]:
            self.hits += 1
            return self.data["county"][k]
        if self._recent_miss("c:" + k):
            self.hits += 1
            return ""
        self.lookups += 1
        c = self._county(lat, lon)
        if c:
            self.data["county"][k] = c
            self.data["miss"].pop("c:" + k, None)
        else:
            self.data["miss"]["c:" + k] = self.now()
        return c

    def save(self) -> None:
        if not self.path:
            return
        _os.makedirs(_os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=0, sort_keys=True)

