#!/usr/bin/env python3
"""Build the public app export (docs/EXPORTS.md) for one app from the statewide canonical tables.

This is where the public release rules are applied: hidden addresses are withheld and the pin
moves to the nearest town centre, opted-out fields are dropped, closed and removed records leave
the file (removed ones appear as an ID only). Apps never read the canonical tables.

Usage:
  python scripts/export_app.py --tables data/colorado --out exports/chaffee-provides.json \
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
KIND_LABELS = {"farm": "Farms", "ranch": "Ranches", "orchard": "Orchards", "bakery": "Bakeries", "maker": "Food makers",
               "winery": "Wineries"}
FIELD_LABEL = {"phone": "phone", "email": "email", "website": "website", "facebook": "Facebook", "instagram": "Instagram",
               "hours_text": "hours", "seasonal_months": "season", "products": "products", "address": "address",
               "city": "town", "zip": "ZIP", "categories": "type", "certified_organic": "organic status",
               "accepts_snap": "SNAP", "ada_accessible": "accessibility"}
BY_LABEL = {"guidestone": "Guidestone Colorado", "producer_site": "the business's own website",
            "producer_facebook": "the business's Facebook page"}
# Records with these statuses are not published. "removed" is listed by ID only.
HIDDEN_STATUS = {"closed", "removed"}


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def compact_hours(text):
    """'Mon: 8 am - 6 pm; Tue: 8 am - 6 pm; ... Sat: 8 am - 6 pm' -> 'Mon-Sat: 8 am - 6 pm'.
    Anything that is not a plain list of 'Day: hours' stays as written."""
    parts = [x.strip() for x in (text or "").split(";") if x.strip()]
    rows = []
    for x in parts:
        day, _, hrs = x.partition(":")
        if len(day.strip()) != 3 or day.strip() not in DAYS or not hrs.strip():
            return (text or "").strip()     # already a range ("Tue-Sun: ...") or free text: leave it alone
        rows.append((DAYS.index(day.strip()[:3]), hrs.strip()))
    out, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1][1] == rows[i][1] and rows[j + 1][0] == rows[j][0] + 1:
            j += 1
        a, b = DAYS[rows[i][0]], DAYS[rows[j][0]]
        out.append("%s: %s" % (a if i == j else ("%s-%s" % (a, b) if j > i + 1 else "%s, %s" % (a, b)), rows[i][1]))
        i = j + 1
    return "; ".join(out)


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
    ap.add_argument("--config", help="app config JSON: {\"exclude_slugs\": {slug: reason}, \"include_categories\": {category: reason}, \"exclude_categories\": {category: reason}, \"hide_pin_slugs\": {slug: reason}} for the app's own scope choices")
    ap.add_argument("--generated", default=dt.date.today().isoformat())
    a = ap.parse_args()
    T = lambda n: read(os.path.join(a.tables, n + ".csv"))
    cfg = json.load(open(a.config, encoding="utf-8")) if a.config else {}
    exclude_slugs = set((cfg.get("exclude_slugs") or {}).keys())
    hide_pin_slugs = set((cfg.get("hide_pin_slugs") or {}).keys())
    include_categories = set((cfg.get("include_categories") or {}).keys())
    exclude_categories = set((cfg.get("exclude_categories") or {}).keys())
    exclude_kinds = set(cfg.get("exclude_kinds") or [])   # e.g. ["bakery"]: a whole category left out of a launch

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
    # structured hours, and which markets each producer sells at (both are additive fields; see EXPORTS.md)
    hours_by = {}
    for r in T("hours"):
        h = {"day": r["day"], "opens": r["opens"], "closes": r["closes"]}
        if r["closes_next_day"] == "true":
            h["closes_next_day"] = True
        if r["inferred"] == "true":
            h["inferred"] = True
        hours_by.setdefault((r["record_type"], r["record_id"]), []).append(h)
    market_rows = {m["market_id"]: m for m in T("markets")}
    sells, vendors_of = {}, {}
    for r in T("market_vendors"):
        m = market_rows.get(r["market_id"])
        if not m:
            continue
        sells.setdefault(r["producer_id"], {})[(r["market_id"], r["year"])] = {
            "market_id": r["market_id"], "name": m["name"],
            "county_fips": (locations.get(m["location_id"]) or {}).get("county_fips") or None,
            "year": int(r["year"]) if r["year"] else None, "season_label": r["season_label"] or None,
            "basis": r["match_basis"], "source_url": r["source_url"] or None}
        vendors_of.setdefault(r["market_id"], set()).add(r["producer_id"])

    fsrc = {}
    for r in T("field_sources"):
        fsrc.setdefault((r["record_type"], r["record_id"]), []).append(r)

    def confirmed_by(rtype, rid, website=""):
        """Who stands behind which details: a partner, or the business's own website or Facebook page."""
        groups = {}
        for r in fsrc.get((rtype, rid), []):
            src = r["source"]
            if src == "producer_site" and "facebook.com" in (r["source_url"] or ""):
                src = "producer_facebook"   # found on the business's Facebook page, not a website
            if not (r["verified_by"] == "partner" or src in ("producer_site", "producer_facebook")):
                continue
            if r["field"] not in FIELD_LABEL:
                continue
            if src != "guidestone" and r["field"] in ("facebook", "instagram", "website"):
                continue   # a page "confirming" its own link says nothing
            url = r["source_url"] if src == "producer_facebook" else (website if src == "producer_site" else "")
            g = groups.setdefault((src, url, r["verified_on"] if src != "producer_site" else ""), [])
            g.append(FIELD_LABEL[r["field"]])
        return [{"by": BY_LABEL.get(k[0], k[0]), "fields": sorted(set(v)), "url": k[1] or None, "date": k[2] or None}
                for k, v in sorted(groups.items(), key=lambda kv: (kv[0][0] != "guidestone", kv[0]))]

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
        if p["slug"] in exclude_slugs or p["kind"] in exclude_kinds:
            continue
        # excluded only when every category the record has is one the app leaves out
        if exclude_categories and lst(p["categories"]) and set(lst(p["categories"])) <= exclude_categories:
            continue
        # an allowlist, when the app has one: a record with categories stays only if one of them is on the list
        if include_categories and lst(p["categories"]) and not (set(lst(p["categories"])) & include_categories):
            continue
        if p["status"] in HIDDEN_STATUS or not in_area("producer", pid, [l["location_id"] for l in locs]):
            continue
        channels = lst(p["sales_channels"])
        sells_at_farm = bool({"farm_stand", "u_pick"} & set(channels))
        opted = set(lst(p["opted_out_fields"]))
        # Two different questions. A person's answer (set in inputs/producer_kinds.csv) always wins. Otherwise the
        # listing itself is the evidence; with none, the answer stays unknown (null), never a guess.
        #   dropin_visits: can a customer just show up? Yes when a farm stand, roadside market or u-pick is stated.
        #   farm_pickup: can a customer collect an order at the farm, by arrangement? Yes when the farm is listed as a
        #   pickup, farm stand or CSA spot, or any visit is advertised: drop-ins, u-pick, farm tours (agritourism).
        def own(field):
            v = p.get(field)
            return None if v in (None, "") else boolish(v)
        home = next((l for l in locs if l["role"] == "home_base"), None)
        home_addr = ((locations.get(home["location_id"]) or {}).get("address") or "").strip().lower() if home else ""
        farm_is_a_spot = any(l["role"] in ("pickup", "farm_stand", "csa_dropoff") and (
            l["location_id"] == (home or {}).get("location_id")
            or (home_addr and ((locations.get(l["location_id"]) or {}).get("address") or "").strip().lower() == home_addr))
            for l in locs)
        dropin, dropin_basis = own("dropin_visits"), ("set" if own("dropin_visits") is not None else None)
        if dropin is None and sells_at_farm:
            dropin, dropin_basis = True, "listing"
        # When drop-ins are welcome, the farm stand's or store's hours are the drop-in hours (a person can set them
        # in inputs/producer_kinds.csv). "By appointment" is not drop-in time, so it is never used.
        dropin_hours = None
        if dropin is True:
            stand = next((l["hours_text"] for l in locs if l["role"] in ("farm_stand", "home_base") and l["hours_text"]), "")
            cand = (p.get("dropin_hours") or stand or p["hours_text"] or "").strip()
            if cand and not re.search(r"appointment|arrangement|call ahead", cand, re.I):
                dropin_hours = compact_hours(cand)
        farm_pickup, pickup_basis = own("farm_pickup"), ("set" if own("farm_pickup") is not None else None)
        if farm_pickup is None and (farm_is_a_spot or dropin is True or "Agritourism" in lst(p["categories"])):
            farm_pickup, pickup_basis = True, "listing"
        out_locs = []
        for l in locs:
            if l["role"] == "home_base":
                pin = sells_at_farm or (not channels and a.unconfirmed_home_pins == "show")
                basis = "confirmed" if sells_at_farm else "unconfirmed"
                if p["slug"] in hide_pin_slugs and not sells_at_farm:
                    pin = False
            else:
                pin, basis = True, "confirmed"
            if l["role"] == "home_base" and not (locations.get(l["location_id"]) or {}).get("address") \
                    and (locations.get(l["location_id"]) or {}).get("hide_address") != "true":
                pin = False       # no street address and not a hidden one: nothing to point to
            lcf = (locations.get(l["location_id"]) or {}).get("county_fips")
            if lcf and lcf not in a.county_fips:
                pin = False       # a place outside this county is not a place to buy on this county's map
            out_locs.append(public_location(l["location_id"], l["role"], pin, basis, {
                "days": lst(l["days"]), "hours_text": l["hours_text"] or None,
                "season_start": l["season_start"] or None, "season_end": l["season_end"] or None,
                "status": l["status"], "confirm_url": l.get("confirm_url") or None}, use_market_name=True))
        rec = {
            "id": pid, "slug": p["slug"], "name": p["name"], "kind": p["kind"],
            "categories": lst(p["categories"]), "products": lst(p["products"]),
            "product_groups": lst(p.get("product_groups", "")),
            "dropin_visits": dropin, "dropin_hours": dropin_hours, "farm_pickup": farm_pickup, "visit_basis": {"dropin": dropin_basis, "pickup": pickup_basis},
            "visit_note": p.get("visit_note") or None,
            "months_open": [MONTHS[int(m) - 1] for m in lst(p["seasonal_months"])],
            "hours_text": p["hours_text"] or None, "hours": hours_by.get(("producer", pid), []),
            "hours_status": p.get("hours_status") or "none",
            "website": p["website"] or None, "phone": p["phone"] or None,
            "email": p["email"] or None, "facebook": p["facebook"] or None, "instagram": p["instagram"] or None,
            "sales_channels": channels,
            "sells_at": sorted(sells.get(pid, {}).values(), key=lambda x: (x["name"].lower(), x["year"] or 0)), "certified_organic": boolish(p["certified_organic"]),
            "accepts_snap": boolish(p["accepts_snap"]), "ada_accessible": boolish(p["ada_accessible"]),
            "call_first": boolish(p["call_first"]), "status": p["status"], "claimed": boolish(p["claimed"]) is True,
            "last_verified": p["last_verified"] or None, "locations": out_locs,
            "sources": sources("producer", pid), "confirmed_by": confirmed_by("producer", pid, p["website"])}
        for f in opted:  # fields the producer asked to have removed
            if f in rec:
                rec[f] = None if not isinstance(rec[f], list) else []
        producers.append(rec)

    included = {p["id"] for p in producers}
    markets = []
    for m in T("markets"):
        if m["status"] in HIDDEN_STATUS or not in_area("market", m["market_id"], [m["location_id"]]):
            continue
        markets.append({
            "id": m["market_id"], "slug": m["slug"], "name": m["name"], "operator": m["operator"] or None,
            "days": lst(m["days"]), "hours_text": m["hours_text"] or None, "hours": hours_by.get(("market", m["market_id"]), []),
            "hours_status": m.get("hours_status") or "none",
            "vendors": sorted(vendors_of.get(m["market_id"], set()) & included),
            "website": m["website"] or None,
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
            "hours_text": r["hours_text"] or None, "hours": hours_by.get(("access_point", r["access_point_id"]), []),
            "hours_status": r.get("hours_status") or "none",
            "website": r["website"] or None, "phone": r["phone"] or None,
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
                       "market_links": sum(len(p["sells_at"]) for p in producers),
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
