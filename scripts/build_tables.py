#!/usr/bin/env python3
"""Build the canonical CSV tables (docs/SCHEMA.md) for one county from the Phase 2 raw CSV.

The Phase 2 raw CSV is one flat row per business. This splits it into the schema's record
types: producers, markets, outlets (each with a location), producer locations, service areas, source
links and field sources. Businesses the schema defers to v2 (food banks, organizations) go to
_deferred_organizations.csv so nothing is lost.

IDs come from data/id_registry.csv: once a business has an ID it keeps it, and IDs are never
reused. Re-running only adds rows for new businesses.

Usage:
  python scripts/build_tables.py --raw ../colorado-farm-trail/source-data/phase2/co_farmers_markets_all_raw.csv \
      --county Chaffee --out data/chaffee-county
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import products as PRODUCTS  # noqa: E402
REGISTRY = os.path.join(HERE, "..", "data", "id_registry.csv")

# Colorado county FIPS (state 08).
FIPS = {c: "08%03d" % n for n, c in [
    (1, "Adams"), (3, "Alamosa"), (5, "Arapahoe"), (7, "Archuleta"), (9, "Baca"), (11, "Bent"),
    (13, "Boulder"), (14, "Broomfield"), (15, "Chaffee"), (17, "Cheyenne"), (19, "Clear Creek"),
    (21, "Conejos"), (23, "Costilla"), (25, "Crowley"), (27, "Custer"), (29, "Delta"),
    (31, "Denver"), (33, "Dolores"), (35, "Douglas"), (37, "Eagle"), (39, "Elbert"),
    (41, "El Paso"), (43, "Fremont"), (45, "Garfield"), (47, "Gilpin"), (49, "Grand"),
    (51, "Gunnison"), (53, "Hinsdale"), (55, "Huerfano"), (57, "Jackson"), (59, "Jefferson"),
    (61, "Kiowa"), (63, "Kit Carson"), (65, "Lake"), (67, "La Plata"), (69, "Larimer"),
    (71, "Las Animas"), (73, "Lincoln"), (75, "Logan"), (77, "Mesa"), (79, "Mineral"),
    (81, "Moffat"), (83, "Montezuma"), (85, "Montrose"), (87, "Morgan"), (89, "Otero"),
    (91, "Ouray"), (93, "Park"), (95, "Phillips"), (97, "Pitkin"), (99, "Prowers"),
    (101, "Pueblo"), (103, "Rio Blanco"), (105, "Rio Grande"), (107, "Routt"), (109, "Saguache"),
    (111, "San Juan"), (113, "San Miguel"), (115, "Sedgwick"), (117, "Summit"), (119, "Teller"),
    (121, "Washington"), (123, "Weld"), (125, "Yuma")]}

MARKET = "Farmers' Market"
PRODUCER_CATS = {"On-Farm / Ranch Sales", "Meat Producer & Packer", "Farm Products (online)", "Agritourism",
                 "CSA Farm", "Roadside Market", "U-Pick", "Winery", "Bakery", "Food Maker", "Wholesale Grower"}
# Outlet categories. Garden Center only makes an outlet row when nothing else says the business
# is a producer (a garlic farm with a greenhouse is a producer, not a garden center).
OUTLET_KIND = {"Restaurant": "restaurant", "Caterer": "caterer", "Grocery Store": "grocery",
               "Farm Store": "farm_store", "Garden Center / Greenhouse": "garden_center"}
# Food access points (v1: community fridges; pantries and meal sites can join this list when wanted).
ACCESS_KIND = {"Community Fridge": "community_fridge"}
BADGES = {"Sells to Schools"}
# Only what a category states outright. "On-Farm / Ranch Sales" is NOT used: Chaffee Provides applies
# it to every farm or ranch, including ones that do not sell on site, so it says what the business
# is, not how it sells. Blank sales_channels means unconfirmed.
CHANNEL = {"Roadside Market": "farm_stand", "U-Pick": "u_pick", "CSA Farm": "csa",
           "Farm Products (online)": "online", "Wholesale Grower": "wholesale"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
SOURCE_NAME = {"chaffee_provides": "chaffee_provides", "colorado_proud": "colorado_proud",
               "colorado_proud_farm_fresh": "colorado_proud", "colorado_proud_finder": "colorado_proud",
               "cfma": "cfma", "usda": "usda_lfd", "official-site": "producer_site",
               "curated": "curated", "dedup-decision": "reviewed", "census-geocoder": "census_geocoder",
               "override": "maintainer", "maintainer": "maintainer", "guidestone_review": "guidestone",
               "producer_facebook": "producer_facebook"}
FIELD_MAP = {"Phone": "phone", "Email": "email", "Website": "website", "Facebook": "facebook",
             "Instagram": "instagram", "Hours": "hours_text", "Months Open": "seasonal_months",
             "Products": "products", "Certified Organic": "certified_organic", "SNAP": "accepts_snap",
             "ADA Accessible": "ada_accessible", "Address": "address", "City": "city", "Zip": "zip",
             "County": "county_fips", "Category": "categories"}

COLS = {
    "producers": ["producer_id", "slug", "name", "kind", "categories", "products", "product_groups", "dropin_visits", "farm_pickup", "visit_note", "seasonal_months",
                  "hours_text", "website", "phone", "email", "facebook", "instagram", "sales_channels",
                  "certified_organic", "accepts_snap", "ada_accessible", "call_first", "status", "claimed",
                  "opted_out_fields", "first_seen", "last_verified"],
    "locations": ["location_id", "name", "kind", "address", "city", "zip", "hide_address", "state", "county_fips",
               "lat", "lon", "geo_source", "google_place_id", "photo_url", "photo_credit", "photo_license"],
    "producer_locations": ["producer_location_id", "producer_id", "location_id", "role", "days", "hours_text", "season_start",
                  "season_end", "status"],
    "markets": ["market_id", "slug", "name", "location_id", "operator", "days", "hours_text", "website", "phone",
                "email", "facebook", "instagram", "accepts_snap", "ada_accessible", "status", "first_seen",
                "last_verified"],
    "outlets": ["outlet_id", "slug", "name", "kind", "brand", "location_id", "website", "phone", "facebook",
                "instagram", "status", "first_seen", "last_verified"],
    "access_points": ["access_point_id", "slug", "name", "kind", "location_id", "hours_text", "website", "phone",
                      "email", "facebook", "instagram", "status", "first_seen", "last_verified"],
    "service_areas": ["producer_id", "county_fips", "basis", "derived"],
    "source_links": ["record_type", "record_id", "source", "url", "source_record_id", "last_seen", "link_status"],
    "field_sources": ["record_type", "record_id", "field", "source", "source_url", "verified_by", "verified_on"],
}


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", re.sub("['’]", "", s.lower().replace("&", " and "))).strip("-")
    return s or "unnamed"


def nkey(s: str) -> str:
    """Name key for matching across files: letters and digits only, so apostrophes, dashes and the
    broken characters some sources carry do not matter."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


CHANNEL_ALIAS = {"on_farm": "farm_stand"}
CHANNEL_VALUES = {"farm_stand", "u_pick", "csa", "farmers_market", "pickup", "delivery", "online", "wholesale",
                  "retail_partners"}


def channel_list(text: str) -> set:
    out = set()
    for c in re.split(r"[;,]", text or ""):
        c = CHANNEL_ALIAS.get(c.strip().lower(), c.strip().lower())
        if c in CHANNEL_VALUES:
            out.add(c)
    return out


def tri(v: str) -> str:
    return {"yes": "true", "no": "false"}.get((v or "").strip().lower(), "")


class Registry:
    """Stable IDs. Key = '<prefix>|<source id>'; new keys get the next number for their prefix."""

    def __init__(self, path):
        self.path, self.rows = path, {}
        if os.path.exists(path):
            with open(path, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    self.rows[r["key"]] = r["id"]
        self.next = {}
        for i in self.rows.values():
            pre, n = i.rsplit("-", 1)
            self.next[pre] = max(self.next.get(pre, 0), int(n))

    def get(self, prefix, key):
        k = prefix + "|" + key
        if k not in self.rows:
            self.next[prefix] = self.next.get(prefix, 0) + 1
            self.rows[k] = "%s-%06d" % (prefix, self.next[prefix])
        return self.rows[k]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["key", "id"])
            for k, v in sorted(self.rows.items(), key=lambda kv: kv[1]):
                w.writerow([k, v])


def classify(cats):
    if MARKET in cats:
        return "market"
    if any(c in ACCESS_KIND for c in cats):
        return "access"
    if any(c in PRODUCER_CATS for c in cats):
        return "producer"
    if any(c in OUTLET_KIND for c in cats):
        return "outlet"
    return "deferred"


def producer_kind(name, cats):
    if "Winery" in cats:
        return "winery"
    if any(c in ("Bakery", "Food Maker") for c in cats) and "On-Farm / Ranch Sales" not in cats:
        return "maker"
    if "Meat Producer & Packer" in cats or re.search(r"\b(ranch|cattle|beef)\b", name, re.I):
        return "ranch"
    return "farm"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--county", default="Chaffee")
    ap.add_argument("--out", required=True)
    ap.add_argument("--additions", nargs="*", default=[],
                    help="partner CSVs in the raw layout; a row replaces the raw row with the same Source ID")
    ap.add_argument("--locations", help="inputs/locations.csv: extra places to buy (pickup points, markets) per producer")
    ap.add_argument("--overrides", help="inputs/overrides.csv, read only to credit partner-confirmed fields")
    ap.add_argument("--kinds", help="inputs/producer_kinds.csv: how a producer labels itself (farm, ranch, maker...) and what it offers")
    ap.add_argument("--registry", default=REGISTRY, help="ID registry CSV (default: data/id_registry.csv)")
    a = ap.parse_args()
    fips = FIPS[a.county]

    with open(a.raw, encoding="utf-8-sig", newline="") as f:
        raw = [r for r in csv.DictReader(f) if (r["County"] or "").strip().lower() == a.county.lower()
               or "chaffee_provides" in (r["Source"] or "")]
    for path in a.additions:
        with open(path, encoding="utf-8-sig", newline="") as f:
            add = list(csv.DictReader(f))
        raw = [r for r in raw if r["Source ID"] not in {x["Source ID"] for x in add}] + add
    extra_locs = {}
    if a.locations and os.path.exists(a.locations):
        with open(a.locations, encoding="utf-8-sig", newline="") as f:
            for lr in csv.DictReader(f):
                extra_locs.setdefault(nkey(lr["name"]), []).append(lr)
    partner_fields = {}
    if a.overrides and os.path.exists(a.overrides):
        with open(a.overrides, encoding="utf-8-sig", newline="") as f:
            for orow in csv.DictReader(f):
                note = orow.get("note") or ""
                m = re.search(r"partner:(\w+)", note)
                v = re.search(r"via:(facebook|website)(?:\s+(https?://\S+))?", note)
                key = (nkey(orow["name"]), (orow.get("column") or "").strip())
                if m:      # confirmed by a partner such as Guidestone
                    partner_fields[key] = (m.group(1), "partner", orow.get("date") or "", "")
                elif v:    # confirmed from the business's own Facebook page or website
                    partner_fields[key] = ({"facebook": "producer_facebook", "website": "producer_site"}[v.group(1)],
                                           "source", orow.get("date") or "", v.group(2) or "")
    kinds_by_name = {}
    if a.kinds and os.path.exists(a.kinds):
        with open(a.kinds, encoding="utf-8-sig", newline="") as f:
            for kr in csv.DictReader(f):
                kinds_by_name[nkey(kr["name"])] = kr
    pending_market_pickups = []
    reg = Registry(a.registry)
    out = {k: [] for k in COLS}
    deferred, slugs = [], set()

    def new_slug(name):
        base = slugify(name)
        s, n = base, 2
        while s in slugs:
            s, n = "%s-%d" % (base, n), n + 1
        slugs.add(s)
        return s

    for r in sorted(raw, key=lambda r: r["Business Name"].lower()):
        name = r["Business Name"].replace("�", "'").strip()
        cats = [c.strip() for c in r["Category"].split(",") if c.strip()]
        cats_main = [c for c in cats if c not in BADGES]
        sid = r["Source ID"] or slugify(name)
        typ = classify(cats_main)
        prov = json.loads(r["Provenance"]) if r["Provenance"] else {}
        srcs = [SOURCE_NAME.get(s, s) for s in (r["Source"] or "").split("+") if s]
        if typ == "deferred":
            deferred.append({"name": name, "categories": "; ".join(cats), "address": r["Address"],
                             "city": r["City"], "phone": r["Phone"], "website": r["Website"],
                             "lat": r["Latitude"], "lon": r["Longitude"], "source": "+".join(srcs)})
            continue

        # One location per business. A business with coordinates but no street address is a hidden
        # address (Chaffee Provides' "hide address" flag): keep county, round the pin to the town.
        mine = extra_locs.get(nkey(name), [])
        home_rows = [x for x in mine if (x.get("role") or "").strip() == "home_base"]
        hidden = (bool(r["Latitude"]) and not r["Address"].strip() and "chaffee_provides" in (r["Source"] or "")) \
            or (r.get("Hide Address") or "").strip().lower() == "yes" \
            or any((x.get("hide_address") or "").strip().lower() in ("yes", "true") for x in home_rows)
        rfips = FIPS.get((r["County"] or "").strip(), fips if not r["County"].strip() else "")
        lkind = {"market": "market_site", "producer": "farm", "outlet": "outlet_site", "access": "access_site"}[typ]
        location_id = reg.get("co-loc", "%s|%s" % (typ, sid))
        out["locations"].append({"location_id": location_id, "name": "", "kind": lkind, "address": r["Address"],
                              "city": r["City"], "zip": r["Zip"], "hide_address": "true" if hidden else "false",
                              "state": r["State"] or "CO", "county_fips": rfips, "lat": r["Latitude"],
                              "lon": r["Longitude"], "geo_source": r["Geo Source"], "google_place_id": "",
                                 "photo_url": "", "photo_credit": "", "photo_license": ""})
        months = [str(MONTHS.index(m.strip()) + 1) for m in (r["Months Open"] or "").split(",")
                  if m.strip() in MONTHS]
        common = {"website": r["Website"], "phone": r["Phone"], "facebook": r["Facebook"],
                  "instagram": r["Instagram"]}
        rec_ids = []

        if typ == "market":
            mid = reg.get("co-m", sid)
            out["markets"].append({"market_id": mid, "slug": new_slug(name), "name": name, "location_id": location_id,
                                   "operator": "", "days": "", "hours_text": r["Hours"], "email": r["Email"],
                                   "accepts_snap": tri(r["SNAP"]), "ada_accessible": tri(r["ADA Accessible"]),
                                   "status": "unverified", "first_seen": "", "last_verified": "", **common})
            rec_ids.append(("market", mid))
        elif typ == "access":
            kind = next(ACCESS_KIND[c] for c in cats_main if c in ACCESS_KIND)
            apid = reg.get("co-ap", sid)
            out["access_points"].append({"access_point_id": apid, "slug": new_slug(name), "name": name, "kind": kind,
                                         "location_id": location_id, "hours_text": r["Hours"], "email": r["Email"],
                                         "status": "unverified", "first_seen": "", "last_verified": "", **common})
            rec_ids.append(("access_point", apid))
        else:
            if typ == "producer":
                pid = reg.get("co-p", sid)
                out["producers"].append({
                    "producer_id": pid, "slug": new_slug(name), "name": name,
                    "kind": (kinds_by_name.get(nkey(name)) or {}).get("kind") or producer_kind(name, cats_main),
                    "dropin_visits": {"yes": "true", "no": "false"}.get(
                        ((kinds_by_name.get(nkey(name)) or {}).get("dropin_visits") or "").strip().lower(), ""),
                    "farm_pickup": {"yes": "true", "no": "false"}.get(
                        ((kinds_by_name.get(nkey(name)) or {}).get("farm_pickup") or "").strip().lower(), ""),
                    "visit_note": (kinds_by_name.get(nkey(name)) or {}).get("visit_note") or "",
                    "product_groups": ";".join(
                        PRODUCTS.from_text(r["Products"], " ".join(cats_main), name)
                        or [g for g in ((kinds_by_name.get(nkey(name)) or {}).get("product_groups") or "").split(";") if g]),
                    "categories": ";".join(c for c in cats if c in PRODUCER_CATS),
                    "products": r["Products"].replace(", ", ";"),
                    "seasonal_months": ";".join(months), "hours_text": r["Hours"], "email": r["Email"],
                    "sales_channels": ";".join(sorted(
                        {CHANNEL[c] for c in cats if c in CHANNEL} | channel_list(r.get("Sales Channels"))
                        | set().union(*[channel_list(x.get("sales_channels")) for x in home_rows]))),
                    "certified_organic": tri(r["Certified Organic"]), "accepts_snap": tri(r["SNAP"]),
                    "ada_accessible": tri(r["ADA Accessible"]), "call_first": tri(r["Call first?"]),
                    "status": "unverified", "claimed": "false", "opted_out_fields": "",
                    "first_seen": "", "last_verified": "", **common})
                out["producer_locations"].append({"producer_location_id": reg.get("co-ploc", sid + "|home"), "producer_id": pid,
                                         "location_id": location_id, "role": "home_base", "days": "",
                                         "hours_text": r["Hours"], "season_start": "", "season_end": "",
                                         "status": "listed"})
                if rfips:
                    out["service_areas"].append({"producer_id": pid, "county_fips": rfips,
                                                 "basis": "home_base", "derived": "true"})
                rec_ids.append(("producer", pid))
                for x in mine:
                    role = (x.get("role") or "").strip()
                    if role == "home_base":
                        continue
                    if (x.get("market_ref") or "").strip():
                        pending_market_pickups.append((pid, sid, x))
                        continue
                    lk = "loc|%s|%s|%s" % (nkey(name), role, nkey(x.get("place_name")))
                    xloc = reg.get("co-loc", lk)
                    xfips = FIPS.get((x.get("county") or "").strip(), rfips)
                    out["locations"].append({
                        "location_id": xloc, "name": x.get("place_name") or "",
                        "kind": "public_venue" if role == "pickup" else "farm", "address": x.get("address") or "",
                        "city": x.get("place_city") or "", "zip": x.get("zip") or "", "hide_address": "false",
                        "state": "CO", "county_fips": xfips, "lat": x.get("lat") or "", "lon": x.get("lon") or "",
                        "geo_source": x.get("geo_source") or "manual", "google_place_id": "", "photo_url": "",
                        "photo_credit": "", "photo_license": ""})
                    out["producer_locations"].append({
                        "producer_location_id": reg.get("co-ploc", lk), "producer_id": pid, "location_id": xloc,
                        "role": role, "days": (x.get("days") or "").replace(", ", ";"),
                        "hours_text": x.get("hours_text") or "",
                        "season_start": x.get("season_start") or "", "season_end": x.get("season_end") or "",
                        "status": "listed"})
                    if xfips and not any(sa["producer_id"] == pid and sa["county_fips"] == xfips
                                         for sa in out["service_areas"]):
                        out["service_areas"].append({"producer_id": pid, "county_fips": xfips,
                                                     "basis": "pickup", "derived": "true"})
            kinds = [OUTLET_KIND[c] for c in cats_main if c in OUTLET_KIND
                     and (typ == "outlet" or c != "Garden Center / Greenhouse")]
            if kinds:
                oid = reg.get("co-o", sid)
                out["outlets"].append({"outlet_id": oid, "slug": new_slug(name + " outlet"), "name": name,
                                       "kind": kinds[0], "brand": "", "location_id": location_id,
                                       "status": "unverified", "first_seen": "", "last_verified": "", **common})
                rec_ids.append(("outlet", oid))

        partner = "guidestone" in srcs
        if partner:  # every populated field in a partner file is partner-verified on the file's date
            prov = {col: "guidestone_review" for col in FIELD_MAP if r.get(col)}
        for rtype, rid in rec_ids:
            for s in srcs:
                url = r["Website"] if s == "producer_site" else ""
                out["source_links"].append({"record_type": rtype, "record_id": rid, "source": s, "url": url,
                                            "source_record_id": sid if s == "chaffee_provides" else "",
                                            "last_seen": "", "link_status": "unchecked"})
            for col, fld in FIELD_MAP.items():
                if col in prov and r.get(col):
                    src, _, url = prov[col].partition(":")
                    who, when = ("partner", r["Source Updated"]) if partner else ("source", "")
                    pf = partner_fields.get((nkey(name), col)) if src == "override" else None
                    if pf:
                        src, who, when = pf[0], pf[1], pf[2]
                        url = pf[3] or url
                    out["field_sources"].append({"record_type": rtype, "record_id": rid, "field": fld,
                                                 "source": SOURCE_NAME.get(src, src), "source_url": url,
                                                 "verified_by": who, "verified_on": when})

    market_loc = {nkey(m["name"]): m["location_id"] for m in out["markets"]}
    for pid, sid, x in pending_market_pickups:
        mloc = market_loc.get(nkey(x["market_ref"]))
        if not mloc:
            print("  location not applied (market not in this build): %s -> %s" % (x["name"], x["market_ref"]))
            continue
        out["producer_locations"].append({
            "producer_location_id": reg.get("co-ploc", "loc|%s|pickup|market|%s" % (nkey(x["name"]), nkey(x["market_ref"]))),
            "producer_id": pid, "location_id": mloc, "role": (x.get("role") or "pickup").strip(),
            "days": (x.get("days") or "").replace(", ", ";"), "hours_text": x.get("hours_text") or "",
            "season_start": x.get("season_start") or "", "season_end": x.get("season_end") or "", "status": "listed"})

    os.makedirs(a.out, exist_ok=True)
    for name, cols in COLS.items():
        with open(os.path.join(a.out, name + ".csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            w.writerows(out[name])
    dcols = ["name", "categories", "address", "city", "phone", "website", "lat", "lon", "source"]
    with open(os.path.join(a.out, "_deferred_organizations.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=dcols, lineterminator="\n")
        w.writeheader()
        w.writerows(deferred)
    reg.save()
    print({k: len(v) for k, v in out.items()}, "deferred:", len(deferred))


if __name__ == "__main__":
    main()
