#!/usr/bin/env python3
"""Build the public app export (docs/EXPORTS.md) for one app from a county's canonical tables.

This is where the public release rules are applied: hidden addresses are withheld and the pin
moves to the nearest town centre, opted-out fields are dropped, closed and removed records leave
the file (removed ones appear as an ID only). Apps never read the canonical tables.

Usage:
  python scripts/export_app.py --tables data/chaffee-county --out exports/chaffee-provides.json \
      --release 2026-11 --county-fips 08015 --include-source chaffee_provides
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys

FORMAT_VERSION = 1
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import products as PRODUCTS  # noqa: E402
TOWNS = os.path.join(HERE, "..", "data", "towns.csv")

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
CHANNEL_LABELS = {
    "farm_stand": "Farm stand / on-farm sales", "u_pick": "U-pick", "csa": "CSA", "farmers_market": "Farmers market",
    "pickup": "Pickup point", "delivery": "Delivery", "online": "Online orders", "wholesale": "Wholesale",
    "retail_partners": "Sold in stores"}
SOURCE_LABELS = {
    "producer_site": "Producer's own website", "chaffee_provides": "Chaffee Provides", "colorado_proud": "Colorado Proud",
    "cfma": "Colorado Farmers Market Association", "usda_lfd": "USDA Local Food Directories",
    "curated": "Farmers market vendor lists, checked by hand", "guidestone": "Guidestone Colorado review",
    "census_geocoder": "US Census geocoder", "reviewed": "Reviewed by hand", "maintainer": "Maintainer"}
# What a producer calls itself (producers.kind). Farms and ranches are different things to a shopper.
KIND_LABELS = {"farm": "Farms", "ranch": "Ranches", "orchard": "Orchards", "maker": "Food makers", "winery": "Wineries"}
# Records with these statuses are not published. "removed" is listed by ID only.
HIDDEN_STATUS = {"closed", "removed"}


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def lst(v):
    return [x for x in (v or "").split(";") if x]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def boolish(v):
    return {"true": True, "false": False}.get((v or "").strip().lower())


def km(a, b):
    dy, dx = (a[0] - b[0]) * 111.2, (a[1] - b[1]) * 111.2 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--release", required=True, help="release label, e.g. 2026-11")
    ap.add_argument("--county-fips", required=True, nargs="+")
    ap.add_argument("--include-source", nargs="*", default=[],
                    help="also include records that this source lists, even outside the county")
    ap.add_argument("--unconfirmed-home-pins", choices=["show", "hide"], default="show",
                    help="draw a home-base pin for producers whose sales channels are not confirmed yet")
    ap.add_argument("--config", help="app config JSON: {\"exclude_slugs\": {slug: reason}} for the app's own scope choices")
    ap.add_argument("--generated", default=dt.date.today().isoformat())
    a = ap.parse_args()
    T = lambda n: read(os.path.join(a.tables, n + ".csv"))
    cfg = json.load(open(a.config, encoding="utf-8")) if a.config else {}
    exclude_slugs = set((cfg.get("exclude_slugs") or {}).keys())

    locations = {r["location_id"]: r for r in T("locations")}
    towns = [(r["name"], float(r["lat"]), float(r["lon"])) for r in read(TOWNS) if r["county_fips"] in a.county_fips]
    links = {}
    for r in T("source_links"):
        links.setdefault((r["record_type"], r["record_id"]), []).append(r)
    areas = {}
    for r in T("service_areas"):
        areas.setdefault(r["producer_id"], set()).add(r["county_fips"])
    plocs = {}
    for r in T("producer_locations"):
        plocs.setdefault(r["producer_id"], []).append(r)

    def sources(rtype, rid):
        out, seen = [], set()
        for l in links.get((rtype, rid), []):
            if l["source"] in seen:
                continue
            seen.add(l["source"])
            out.append({"source": l["source"], "label": SOURCE_LABELS.get(l["source"], l["source"]),
                        "url": l["url"] or None})
        return out

    def in_area(rtype, rid, loc_ids):
        if any(locations[i]["county_fips"] in a.county_fips for i in loc_ids if i in locations):
            return True
        if areas.get(rid, set()) & set(a.county_fips):
            return True
        return any(l["source"] in a.include_source for l in links.get((rtype, rid), []))

    market_name = {m["location_id"]: m["name"] for m in T("markets")}

    def public_location(loc_id, role, pin, pin_basis, extra=None, use_market_name=False):
        """One map location with the public rules applied."""
        L = locations[loc_id]
        lat, lon = num(L["lat"]), num(L["lon"])
        hidden = boolish(L["hide_address"]) is True
        town = None
        if hidden and lat is not None and towns:
            town = min(towns, key=lambda t: km((lat, lon), (t[1], t[2])))
            lat, lon = town[1], town[2]
        street = None if hidden else (L["address"] or None)
        if street and re.match(r"(?i)\s*p\.?\s*o\.?\s*box", street):  # a mailbox is not a place to visit
            street = None
        out = {"id": loc_id, "role": role, "name": L["name"] or (market_name.get(loc_id) if use_market_name else None) or None,
               "address": street,
               "city": L["city"] or (town[0] if town else None), "zip": None if hidden else (L["zip"] or None),
               "county_fips": L["county_fips"] or None,
               "lat": None if lat is None else round(lat, 6), "lon": None if lon is None else round(lon, 6),
               "precision": "none" if lat is None else ("town" if hidden else ("exact" if street and L["geo_source"] != "town_centre" else "approximate")),
               "pin": bool(pin and lat is not None), "pin_basis": pin_basis}
        out.update(extra or {})
        return out

    producers, removed = [], []
    for p in T("producers"):
        pid = p["producer_id"]
        if p["status"] == "removed":
            removed.append(pid)
            continue
        locs = plocs.get(pid, [])
        if p["slug"] in exclude_slugs:
            continue
        if p["status"] in HIDDEN_STATUS or not in_area("producer", pid, [l["location_id"] for l in locs]):
            continue
        channels = lst(p["sales_channels"])
        sells_at_farm = bool({"farm_stand", "u_pick"} & set(channels))
        opted = set(lst(p["opted_out_fields"]))
        out_locs = []
        for l in locs:
            if l["role"] == "home_base":
                pin = sells_at_farm or (not channels and a.unconfirmed_home_pins == "show")
                basis = "confirmed" if sells_at_farm else "unconfirmed"
            else:
                pin, basis = True, "confirmed"
            out_locs.append(public_location(l["location_id"], l["role"], pin, basis, {
                "days": lst(l["days"]), "hours_text": l["hours_text"] or None,
                "season_start": l["season_start"] or None, "season_end": l["season_end"] or None,
                "status": l["status"]}, use_market_name=True))
        rec = {
            "id": pid, "slug": p["slug"], "name": p["name"], "kind": p["kind"],
            "categories": lst(p["categories"]), "products": lst(p["products"]),
            "product_groups": lst(p.get("product_groups", "")),
            "months_open": [MONTHS[int(m) - 1] for m in lst(p["seasonal_months"])],
            "hours_text": p["hours_text"] or None, "website": p["website"] or None, "phone": p["phone"] or None,
            "email": p["email"] or None, "facebook": p["facebook"] or None, "instagram": p["instagram"] or None,
            "sales_channels": channels, "certified_organic": boolish(p["certified_organic"]),
            "accepts_snap": boolish(p["accepts_snap"]), "ada_accessible": boolish(p["ada_accessible"]),
            "call_first": boolish(p["call_first"]), "status": p["status"], "claimed": boolish(p["claimed"]) is True,
            "last_verified": p["last_verified"] or None, "locations": out_locs,
            "sources": sources("producer", pid)}
        for f in opted:  # fields the producer asked to have removed
            if f in rec:
                rec[f] = None if not isinstance(rec[f], list) else []
        producers.append(rec)

    markets = []
    for m in T("markets"):
        if m["status"] in HIDDEN_STATUS or not in_area("market", m["market_id"], [m["location_id"]]):
            continue
        markets.append({
            "id": m["market_id"], "slug": m["slug"], "name": m["name"], "operator": m["operator"] or None,
            "days": lst(m["days"]), "hours_text": m["hours_text"] or None, "website": m["website"] or None,
            "phone": m["phone"] or None, "email": m["email"] or None, "facebook": m["facebook"] or None,
            "instagram": m["instagram"] or None, "accepts_snap": boolish(m["accepts_snap"]),
            "ada_accessible": boolish(m["ada_accessible"]), "status": m["status"],
            "last_verified": m["last_verified"] or None,
            "location": public_location(m["location_id"], "market_site", True, "confirmed"),
            "sources": sources("market", m["market_id"])})

    access = []
    for r in T("access_points"):
        if r["status"] in HIDDEN_STATUS or not in_area("access_point", r["access_point_id"], [r["location_id"]]):
            continue
        access.append({
            "id": r["access_point_id"], "slug": r["slug"], "name": r["name"], "kind": r["kind"],
            "hours_text": r["hours_text"] or None, "website": r["website"] or None, "phone": r["phone"] or None,
            "email": r["email"] or None, "facebook": r["facebook"] or None, "instagram": r["instagram"] or None,
            "status": r["status"], "last_verified": r["last_verified"] or None,
            "location": public_location(r["location_id"], "access_site", True, "confirmed"),
            "sources": sources("access_point", r["access_point_id"])})

    doc = {
        "export": {
            "app": os.path.splitext(os.path.basename(a.out))[0], "format_version": FORMAT_VERSION,
            "release": a.release, "generated": a.generated, "source": "Colorado Open Food Web",
            "county_fips": a.county_fips,
            "attribution": "Colorado Open Food Web, CC BY 4.0. Partner data from Guidestone Colorado.",
            "counts": {"producers": len(producers), "markets": len(markets), "access_points": len(access),
                       "pins": sum(l["pin"] for p in producers for l in p["locations"])
                       + len(markets) + len(access)}},
        "vocab": {"sales_channels": CHANNEL_LABELS, "months": MONTHS, "kinds": KIND_LABELS,
                  "product_groups": PRODUCTS.LABELS},
        "producers": sorted(producers, key=lambda x: x["name"].lower()),
        "markets": sorted(markets, key=lambda x: x["name"].lower()),
        "access_points": sorted(access, key=lambda x: x["name"].lower()),
        "removed_ids": sorted(removed)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    print(doc["export"]["counts"])


if __name__ == "__main__":
    main()
