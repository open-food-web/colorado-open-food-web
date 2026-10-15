"""Source: USDA Local Food Portal — ALL FIVE local-food directories.

The portal hosts five directories, each with the same two access paths:

  farmersmarket · onfarmmarket · csa · foodhub · agritourism

  * data_share (NO key)  -> /mywp/wp-json/frontend/data_share?directory=<dir>&state=co
    Only returns listings that opted into data-sharing, with a thin field set
    (name/contact/address/website — no coords). CO counts as of 2026-07:
    farmersmarket ≈6, onfarmmarket 37, csa 41, foodhub 12, agritourism 12.

  * api (KEY required)   -> /api/<dir>/?apikey=KEY&... with location params:
    state=co (documented; tried first — one request per directory) or
    x=LON&y=LAT&radius=MILES (grid-sweep fallback across Colorado).
    Rich field set: coords, socials, description, plus listing_id + updatetime
    (captured for the update engine — see docs/UPDATE_ENGINE.md).

`parse_api` field names are verified against a live keyed farmersmarket sample
(scripts/tests/fixtures/usda_api_sample.json); records carry a `directory_type`
discriminator, so the same parser serves all five directories. Spot-checked live
on 2026-10-03: all five share the base field set, except agritourism has no
`location_street` (street is parsed from the one-line `location_address`), and
csa/foodhub carry season + a source-truncated product list in `mydesc`.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import List

from ..normalize import clean_url, facebook_url, instagram_url, phone, titlecase, zipcode
from ..schema import Market
from ..useragent import USER_AGENT

DATASHARE = "https://www.usdalocalfoodportal.com/mywp/wp-json/frontend/data_share"
API_BASE = "https://www.usdalocalfoodportal.com/api/{directory}/"
API = API_BASE.format(directory="farmersmarket")  # kept for back-compat
SOURCE = "usda"
UA = {"User-Agent": USER_AGENT}

# Portal directory slug -> our Category column value (Phase 1 bucket names where one
# exists; "Food Hub" is new — it has no Phase 1 equivalent).
DIRECTORIES = {
    "farmersmarket": "Farmers' Market",
    "onfarmmarket": "On-Farm / Ranch Sales",
    "csa": "CSA Farm",
    "foodhub": "Food Hub",
    "agritourism": "Agritourism",
}
DEFAULT_DIRECTORY = "farmersmarket"

# A coarse grid of points (lon, lat) covering Colorado; each queried with a radius
# wide enough to overlap its neighbors, so no market is missed. Deduped by id.
CO_GRID = [
    (lon, lat)
    for lat in (37.4, 38.4, 39.4, 40.4)
    for lon in (-108.2, -106.2, -104.2, -102.6)
]
GRID_RADIUS_MILES = 60


def _get_json(url: str, timeout: int = 40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---- keyless data_share (thin) ------------------------------------------------

def fetch_datashare_raw(state: str = "co", directory: str = DEFAULT_DIRECTORY) -> list:
    q = urllib.parse.urlencode({"directory": directory, "state": state})
    return _get_json(f"{DATASHARE}?{q}")


def parse_datashare(rows: list, directory: str = DEFAULT_DIRECTORY) -> List[Market]:
    category = DIRECTORIES.get(directory, "")
    out = []
    for r in rows:
        m = Market(source=SOURCE)
        if category:
            m.category = category
        m.set("business_name", r.get("Listing_Name", ""), SOURCE)
        m.set("address", r.get("Location_Street", ""), SOURCE)
        m.set("city", r.get("Location_City", ""), SOURCE)
        m.set("zip", zipcode(r.get("Location_Zipcode", "")), SOURCE)
        m.set("phone", phone(r.get("Contact_Phone", "")), SOURCE)
        m.set("email", r.get("Contact_Email", ""), SOURCE)
        m.set("website", clean_url(r.get("Media_Website", "")), SOURCE)
        if m.business_name:
            out.append(m)
    return out


# ---- keyed API (rich) ---------------------------------------------------------

def fetch_api_raw(apikey: str, lon: float, lat: float, radius: int = GRID_RADIUS_MILES,
                  directory: str = DEFAULT_DIRECTORY):
    q = urllib.parse.urlencode({"apikey": apikey, "x": lon, "y": lat, "radius": radius})
    return _get_json(f"{API_BASE.format(directory=directory)}?{q}")


def fetch_api_state_raw(apikey: str, directory: str = DEFAULT_DIRECTORY, state: str = "co"):
    """The documented `state` param — one request for the whole state. Tried first;
    the grid sweep is the fallback if this errors or comes back empty."""
    q = urllib.parse.urlencode({"apikey": apikey, "state": state})
    return _get_json(f"{API_BASE.format(directory=directory)}?{q}")


def _api_records(payload) -> list:
    """The portal has returned either a bare list or {'data': [...]}; handle both."""
    if isinstance(payload, dict):
        return payload.get("data") or payload.get("results") or []
    return payload or []


def _s(r, key):
    """Portal uses null and '' interchangeably; return a clean string."""
    v = r.get(key)
    return "" if v is None else str(v).strip()


_PO_BOX = re.compile(r"^\s*p\.?\s*o\.?\s*box\b", re.I)


def _street_from_address(full: str, city: str) -> str:
    """Street from the one-line `location_address` ("590 W. Colfax, Golden, CO 80401"),
    for directories that leave `location_street` empty (agritourism, many CSAs).
    Takes the segments before the city; PO boxes are mailing addresses, not a place
    to visit, so they're dropped. '' if the city can't be located (no guessing)."""
    parts = [p.strip() for p in full.split(",")]
    lowered = [p.lower() for p in parts]
    if not city or city.lower() not in lowered:
        return ""
    street = [p for p in parts[:lowered.index(city.lower())] if p and not _PO_BOX.match(p)]
    return street[-1] if street else ""


_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _months_open(text: str) -> str:
    """'June to December' -> 'June, July, ..., December' (the Months Open format
    used across the pipeline); 'Year-round' -> all twelve. '' if unrecognized."""
    t = text.strip().lower()
    if t in ("year-round", "year round"):
        return ", ".join(_MONTHS)
    m = re.fullmatch(r"([a-z]+)\s+to\s+([a-z]+)", t)
    names = [n.lower() for n in _MONTHS]
    if not m or m.group(1) not in names or m.group(2) not in names:
        return ""
    a, b = names.index(m.group(1)), names.index(m.group(2))
    span = range(a, b + 1) if a <= b else list(range(a, 12)) + list(range(0, b + 1))
    return ", ".join(_MONTHS[i] for i in span)


def _parse_mydesc(text: str) -> dict:
    """csa/foodhub `mydesc` is labelled lines: 'Open: June to December<br>Available
    Products: Apples; Grapes; ...'. Returns {label: value}."""
    out = {}
    for line in re.split(r"<br\s*/?>", text, flags=re.I):
        label, sep, value = line.partition(":")
        if sep and value.strip():
            out[label.strip().lower()] = value.strip()
    return out


def parse_api(payload, directory: str = "") -> List[Market]:
    """Map a real keyed-API response. Verified against a live CO sample: the farmers
    market API carries identity/location/contact/social only — NO hours, season,
    products, SNAP, organic, or county. Those stay empty here (filled by Colorado
    Proud or later per-site enrichment). County/coords-gap handled by the geocoder.

    Category comes from each record's own `directory_type` discriminator when
    present, falling back to the `directory` this payload was fetched from."""
    out = []
    for r in _api_records(payload):
        state = _s(r, "location_state").lower()
        if state and state not in ("colorado", "co"):
            continue  # grid edges can pull neighboring states
        m = Market(source=SOURCE)
        category = DIRECTORIES.get(_s(r, "directory_type") or directory, "")
        if category:
            m.category = category
        m.source_id = _s(r, "listing_id")
        m.source_updated = _s(r, "updatetime")
        m.set("business_name", _s(r, "listing_name"), SOURCE)
        street = _s(r, "location_street") or _street_from_address(
            _s(r, "location_address"), _s(r, "location_city"))
        m.set("address", titlecase(street), SOURCE)
        m.set("city", titlecase(_s(r, "location_city")), SOURCE)
        m.set("zip", zipcode(_s(r, "location_zipcode")), SOURCE)
        m.set("phone", phone(_s(r, "contact_phone")), SOURCE)
        m.set("email", _s(r, "contact_email"), SOURCE)
        m.set("website", clean_url(_s(r, "media_website")), SOURCE)
        m.set("facebook", facebook_url(_s(r, "media_facebook")), SOURCE)
        m.set("instagram", instagram_url(_s(r, "media_instagram")), SOURCE)
        desc = _parse_mydesc(_s(r, "mydesc"))
        m.set("months_open", _months_open(desc.get("open", "")), SOURCE)
        # The portal truncates the product list ("...") at the source, so it fails
        # the explicit-only bar for Products; keep it as context in Notes instead.
        products = desc.get("available products", "")
        if products.endswith("..."):
            products = products[:-3].rstrip(" ,;") + " (partial list)"
        notes = _s(r, "listing_desc") or _s(r, "brief_desc")
        if not notes and products:
            notes = f"Products listed on USDA: {products}"
        m.set("notes", notes, SOURCE)
        lon, lat = _s(r, "location_x"), _s(r, "location_y")
        try:
            if lon and lat:
                m.longitude, m.latitude = float(lon), float(lat)
                m.geo_source = "source"
        except (TypeError, ValueError):
            pass
        if m.business_name:
            out.append(m)
    return out


def fetch_api_directory(apikey: str, directory: str) -> List[Market]:
    """One directory statewide: try the documented state=co query first; fall back
    to the grid sweep. Dedupe within the directory by (name, city)."""
    try:
        markets = parse_api(fetch_api_state_raw(apikey, directory), directory)
        if markets:
            return markets
    except Exception:
        pass
    seen, out = set(), []
    for lon, lat in CO_GRID:
        try:
            payload = fetch_api_raw(apikey, lon, lat, directory=directory)
        except Exception:
            continue
        for m in parse_api(payload, directory):
            key = (m.business_name.lower(), m.city.lower())
            if key not in seen:
                seen.add(key)
                out.append(m)
    return out


def fetch_api(apikey: str, directories=None) -> List[Market]:
    """All requested directories statewide. The same business listed in two
    directories (e.g. a CSA that also runs an on-farm stand) is NOT collapsed here —
    merge.py folds same-name+city records so directory records fill each other's
    gaps, with the higher-priority record's Category winning."""
    out = []
    for directory in (directories or DIRECTORIES):
        out += fetch_api_directory(apikey, directory)
    return out


def fetch_datashare(directories=None) -> List[Market]:
    """Keyless fallback: every requested directory via data_share (thin fields,
    opt-in listings only, no coords — the geocoder fills those)."""
    out = []
    for directory in (directories or DIRECTORIES):
        try:
            out += parse_datashare(fetch_datashare_raw(directory=directory), directory)
        except Exception:
            continue
    return out
