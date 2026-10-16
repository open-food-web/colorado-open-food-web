#!/usr/bin/env python3
"""Build the canonical CSV tables (docs/SCHEMA.md) for all of Colorado (or one county) from the raw build.

The Phase 2 raw CSV is one flat row per business. This splits it into the schema's record
types: producers, markets, outlets (each with a location), producer locations, service areas, source
links and field sources. Businesses the schema defers to v2 (food banks, organizations) go to
_deferred_organizations.csv so nothing is lost.

IDs come from data/id_registry.csv: once a business has an ID it keeps it, and IDs are never
reused. Re-running only adds rows for new businesses.

Statewide is the default; `--county Chaffee` builds one county (plus anything from the Chaffee Provides
directory). The raw CSV comes from `python scripts/scrape/build.py` (.cache/build/). Emails are kept only
when the business lists them itself (scrape/contact_policy.py).

Usage:
  python scripts/scrape/build.py
  python scripts/build_tables.py --raw .cache/build/co_farmers_markets_all_raw.csv --out data/colorado \
      --additions data/partner-additions/guidestone_2026-10-13.csv
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
from scrape import contact_policy as cp  # noqa: E402
from scrape import hours as hrs  # noqa: E402
from scrape import vendors as vnd  # noqa: E402
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
                 "CSA Farm", "Roadside Market", "U-Pick", "Winery", "Bakery", "Food Maker", "Agricultural Education", "Wholesale Grower"}
# Outlet categories. Garden Center only makes an outlet row when nothing else says the business
# is a producer (a garlic farm with a greenhouse is a producer, not a garden center).
OUTLET_KIND = {"Restaurant": "restaurant", "Caterer": "caterer", "Grocery Store": "grocery",
               "Farm Store": "farm_store", "Garden Center / Greenhouse": "garden_center",
               "Apothecary": "apothecary"}
# Food access points (v1: community fridges; pantries and meal sites can join this list when wanted).
ACCESS_KIND = {"Community Fridge": "community_fridge"}
BADGES = {"Sells to Schools"}
# Only what a category states outright. "On-Farm / Ranch Sales" is NOT used: Chaffee Provides applies
# it to every farm or ranch, including ones that do not sell on site, so it says what the business
# is, not how it sells. Blank sales_channels means unconfirmed.
CHANNEL = {"Roadside Market": "farm_stand", "U-Pick": "u_pick", "CSA Farm": "csa",
           "Farm Products (online)": "online", "Wholesale Grower": "wholesale"}
RAW_CHANNEL = {"on_farm": "farm_stand", "farm_stand": "farm_stand", "farmers_market": "farmers_market", "csa": "csa",
               "delivery": "delivery", "wholesale": "wholesale", "retail_partners": "retail_partners",
               "online": "online", "u_pick": "u_pick", "pickup": "pickup"}
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
    "producers": ["producer_id", "slug", "name", "kind", "categories", "products", "product_groups", "dropin_visits", "dropin_hours", "farm_pickup", "visit_note", "visits", "seasonal_months",
                  "hours_text", "hours_status", "website", "phone", "email", "facebook", "instagram", "sales_channels",
                  "certified_organic", "accepts_snap", "ada_accessible", "call_first", "status", "claimed",
                  "opted_out_fields", "first_seen", "last_verified"],
    "locations": ["location_id", "name", "kind", "address", "city", "zip", "hide_address", "state", "county_fips",
               "lat", "lon", "geo_source", "google_place_id", "photo_url", "photo_credit", "photo_license"],
    "producer_locations": ["producer_location_id", "producer_id", "location_id", "role", "days", "hours_text", "season_start",
                  "season_end", "status", "confirm_url"],
    "markets": ["market_id", "slug", "name", "location_id", "operator", "days", "hours_text", "hours_status", "website", "phone",
                "email", "facebook", "instagram", "accepts_snap", "ada_accessible", "status", "first_seen",
                "last_verified"],
    "outlets": ["outlet_id", "slug", "name", "kind", "brand", "location_id", "website", "phone", "facebook",
                "instagram", "status", "first_seen", "last_verified"],
    "access_points": ["access_point_id", "slug", "name", "kind", "location_id", "hours_text", "hours_status", "website", "phone",
                      "email", "facebook", "instagram", "status", "first_seen", "last_verified"],
    "service_areas": ["producer_id", "county_fips", "basis", "derived"],
    "hours": ["record_type", "record_id", "day", "opens", "closes", "closes_next_day", "inferred"],
    "market_vendors": ["market_id", "producer_id", "year", "season_label", "days", "season_start", "season_end", "status",
                       "list_source", "source_url", "match_basis"],
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
                  "retail_partners", "none"}   # "none": confirmed, no public sales (not the same as blank = unknown)


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
        self.known = {k.split("|", 1)[1] for k in self.rows}
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


def channels(r, cats):
    """Sales channels: what the raw row states (the Sales Channels column) plus what its categories state outright."""
    stated = [RAW_CHANNEL[c.strip()] for c in (r.get("Sales Channels") or "").split(";") if c.strip() in RAW_CHANNEL]
    derived = [CHANNEL[c] for c in cats if c in CHANNEL]
    return ";".join(sorted(set(stated) | set(derived)))


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


def link_markets(out, stated, vendors_path):
    """Fill market_vendors from the vendor lists and from market names a producer's listing states, and add
    the market's county to each producer's service areas."""
    locs = {r["location_id"]: r for r in out["locations"]}
    lk = vnd.Linker(out["markets"], out["producers"], locs)
    lk.attach_locations(out["producer_locations"])
    rows, unmatched = [], {}
    if os.path.exists(vendors_path):
        with open(vendors_path, encoding="utf-8", newline="") as f:
            rows, unmatched = lk.from_lists(list(csv.DictReader(f)))
    have = {(r["market_id"], r["producer_id"]) for r in rows}
    rows += lk.from_text(stated, have)
    rows.sort(key=lambda r: (r["market_id"], r["producer_id"], r["year"], r["match_basis"]))
    out["market_vendors"] = rows
    present = {(r["producer_id"], r["county_fips"]) for r in out["service_areas"]}
    mk = {m["market_id"]: m for m in out["markets"]}
    for r in rows:
        fips = locs[mk[r["market_id"]]["location_id"]]["county_fips"]
        if fips and (r["producer_id"], fips) not in present:
            present.add((r["producer_id"], fips))
            out["service_areas"].append({"producer_id": r["producer_id"], "county_fips": fips, "basis": "market",
                                         "derived": "true"})
    by_basis = {}
    for r in rows:
        by_basis[r["match_basis"]] = by_basis.get(r["match_basis"], 0) + 1
    print("market_vendors:", len(rows), by_basis, "| vendor rows not linked:", unmatched)


DEAD_MARKET = {"closed", "removed"}
OWN_PAGE_SOURCES = {"producer_site", "producer_facebook"}


def derive_channels(out):
    """Add `farmers_market` to a producer's sales_channels when a live market's vendor list names them, and say so
    in field_sources. Only ever adds: an existing channel is kept, and a producer on no list stays as it was."""
    live = {m["market_id"] for m in out["markets"] if (m["status"] or "").lower() not in DEAD_MARKET}
    by_pid = {p["producer_id"]: p for p in out["producers"]}
    sources = {}
    for v in out["market_vendors"]:
        if v["market_id"] in live and (v["status"] or "").lower() not in DEAD_MARKET and v["producer_id"] in by_pid:
            sources.setdefault(v["producer_id"], {}).setdefault((v["list_source"], v["source_url"]), v)
    added = 0
    for pid, srcs in sorted(sources.items()):
        p = by_pid[pid]
        have = channel_list(p["sales_channels"])
        if "farmers_market" in have:
            continue
        p["sales_channels"] = ";".join(sorted(have | {"farmers_market"}))
        added += 1
        for (src, url), v in sorted(srcs.items()):
            out["field_sources"].append({"record_type": "producer", "record_id": pid, "field": "sales_channels",
                                         "source": src, "source_url": url, "verified_by": "source", "verified_on": ""})
    print("farmers_market channel derived from live vendor lists:", added)


def derive_last_verified(out):
    """`last_verified` = the latest dated field_sources row where the business's own page (producer_site,
    producer_facebook) or a partner confirmed a field. No dated row, no date."""
    latest = {}
    for fs in out["field_sources"]:
        if fs["record_type"] == "producer" and fs["verified_on"] and (
                fs["verified_by"] == "partner" or fs["source"] in OWN_PAGE_SOURCES):
            latest[fs["record_id"]] = max(latest.get(fs["record_id"], ""), fs["verified_on"])
    n = 0
    for p in out["producers"]:
        if p["producer_id"] in latest and not p["last_verified"]:
            p["last_verified"] = latest[p["producer_id"]]
            n += 1
    print("producers with last_verified:", n)


def confirm_url(x, website):
    """The business's own page that confirms it sells at this place: the `source` of a locations.csv row, when it
    is a link on the business's own website (a market's vendor list or a directory does not count)."""
    u = (x.get("source") or "").strip()
    if not u.lower().startswith(("http://", "https://")) or not (website or "").strip():
        return ""
    host = lambda v: ".".join(re.sub(r"^https?://", "", v.strip().lower()).split("/")[0].split(":")[0].split(".")[-2:])
    return u if host(u) == host(website) else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--vendors", default=os.path.join(HERE, "..", "inputs", "market_vendor_lists.csv"),
                    help="market vendor lists (market, market_city, vendor, list_year, list_url)")
    ap.add_argument("--county", default=None, help="limit to one county (default: all of Colorado)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--additions", nargs="*", default=[],
                    help="partner CSVs in the raw layout; a row replaces the raw row with the same Source ID")
    ap.add_argument("--locations", help="inputs/locations.csv: extra places to buy (pickup points, markets) per producer")
    ap.add_argument("--overrides", help="inputs/overrides.csv, read only to credit partner-confirmed fields")
    ap.add_argument("--kinds", help="inputs/producer_kinds.csv: how a producer labels itself (farm, ranch, maker...) and what it offers")
    ap.add_argument("--registry", default=REGISTRY, help="ID registry CSV (default: data/id_registry.csv)")
    a = ap.parse_args()
    fips = FIPS[a.county] if a.county else ""
    emails = cp.Table()

    sells_here = set()      # businesses based elsewhere that sell here (a place in inputs/locations.csv)
    if a.locations and os.path.exists(a.locations):
        with open(a.locations, encoding="utf-8-sig", newline="") as f:
            sells_here = {re.sub(r"[^a-z0-9]+", "", (lr["name"] or "").lower()) for lr in csv.DictReader(f)}
    with open(a.raw, encoding="utf-8-sig", newline="") as f:
        raw = [r for r in csv.DictReader(f)
               if not a.county or (r["County"] or "").strip().lower() == a.county.lower()
               or "chaffee_provides" in (r["Source"] or "")
               or re.sub(r"[^a-z0-9]+", "", (r["Business Name"] or "").lower()) in sells_here]
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
    def kind_groups(name):
        return [g.strip() for g in ((kinds_by_name.get(nkey(name)) or {}).get("product_groups") or "").split(";") if g.strip()]
    pending_market_pickups = []
    reg = Registry(a.registry)
    out = {k: [] for k in COLS}
    deferred, slugs, used = [], set(), set()
    stated = {}

    def prefixes_for(typ, cats_main):
        """The ID prefixes a row will take, so two rows only collide when they would share an actual ID."""
        if typ == "market":
            return ["co-m"]
        if typ == "access":
            return ["co-ap"]
        out_ = ["co-p"] if typ == "producer" else []
        if any(c in OUTLET_KIND and (typ == "outlet" or c != "Garden Center / Greenhouse") for c in cats_main):
            out_.append("co-o")
        return out_ or ["co-p"]

    def entity_key(r, name, prefixes):
        """A permanent key for the registry. A source ID when there is one; otherwise the name, plus the town
        when the plain name is new (two "Farmers Market"s in different towns are different businesses).
        A key already in the registry keeps its ID, and a repeated key within one run gets a suffix."""
        base = r["Source ID"] or slugify(name)
        key = base
        if not r["Source ID"] and base not in reg.known:
            key = base + "|" + slugify(r["City"] or "")
        n = 1
        while any((p_, key) in used for p_ in prefixes):
            n += 1
            key = "%s|%d" % (base, n)
        used.update((p_, key) for p_ in prefixes)
        return key

    def publishable_email(r):
        kept = [e for e in cp.split_emails(r["Email"]) if cp.publishable(e, r["Website"], emails)]
        return "; ".join(kept)

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
        sid = entity_key(r, name, prefixes_for(classify(cats_main), cats_main))
        if "guidestone_review" not in (r["Source"] or ""):   # a partner file states its own contact details
            r["Email"] = publishable_email(r)
        status = "closed" if (r.get("Status") or "").strip().lower() == "closed" else "unverified"
        parsed = hrs.parse(r["Hours"])
        hs = parsed.status
        dys = ";".join(sorted({sl.day for sl in parsed.slots}, key=hrs.DAY_ORDER.index))
        typ = classify(cats_main)
        if typ == "deferred" and (kinds_by_name.get(nkey(name)) or {}).get("kind"):
            typ = "producer"      # a person has said what it is (a mushroom grower, a honey maker...)
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
                                   "operator": "", "days": dys, "hours_text": r["Hours"], "hours_status": hs, "email": r["Email"],
                                   "accepts_snap": tri(r["SNAP"]), "ada_accessible": tri(r["ADA Accessible"]),
                                   "status": status, "first_seen": "", "last_verified": "", **common})
            rec_ids.append(("market", mid))
        elif typ == "access":
            kind = next(ACCESS_KIND[c] for c in cats_main if c in ACCESS_KIND)
            apid = reg.get("co-ap", sid)
            out["access_points"].append({"access_point_id": apid, "slug": new_slug(name), "name": name, "kind": kind,
                                         "location_id": location_id, "hours_text": r["Hours"], "hours_status": hs, "email": r["Email"],
                                         "status": status, "first_seen": "", "last_verified": "", **common})
            rec_ids.append(("access_point", apid))
        else:
            if typ == "producer":
                pid = reg.get("co-p", sid)
                out["producers"].append({
                    "producer_id": pid, "slug": new_slug(name), "name": name,
                    "kind": (kinds_by_name.get(nkey(name)) or {}).get("kind") or producer_kind(name, cats_main),
                    "dropin_visits": {"yes": "true", "no": "false"}.get(
                        ((kinds_by_name.get(nkey(name)) or {}).get("dropin_visits") or "").strip().lower(), ""),
                    "dropin_hours": (kinds_by_name.get(nkey(name)) or {}).get("dropin_hours") or "",
                    "farm_pickup": {"yes": "true", "no": "false"}.get(
                        ((kinds_by_name.get(nkey(name)) or {}).get("farm_pickup") or "").strip().lower(), ""),
                    "visit_note": (kinds_by_name.get(nkey(name)) or {}).get("visit_note") or "",
                    "visits": (kinds_by_name.get(nkey(name)) or {}).get("visits") or "",
                    "product_groups": ";".join(PRODUCTS.union(
                        PRODUCTS.from_text(r["Products"], " ".join(cats_main), name)
                        or [g for g in kind_groups(name) if not g.startswith("+")],
                        [g[1:] for g in kind_groups(name) if g.startswith("+")])),     # "+herbs": added to what the text shows
                    "categories": ";".join(c for c in cats if c in PRODUCER_CATS),
                    "products": r["Products"].replace(", ", ";"),
                    "seasonal_months": ";".join(months), "hours_text": r["Hours"], "hours_status": hs, "email": r["Email"],
                    "sales_channels": ";".join(sorted(set(filter(None, channels(r, cats).split(";")))
                                                      | set().union(*[channel_list(x.get("sales_channels")) for x in home_rows]))),
                    "certified_organic": tri(r["Certified Organic"]), "accepts_snap": tri(r["SNAP"]),
                    "ada_accessible": tri(r["ADA Accessible"]), "call_first": tri(r["Call first?"]),
                    "status": status, "claimed": "false", "opted_out_fields": "",
                    "first_seen": "", "last_verified": "", **common})
                out["producer_locations"].append({"producer_location_id": reg.get("co-ploc", sid + "|home"), "producer_id": pid,
                                         "location_id": location_id, "role": "home_base", "days": dys,
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
                        pending_market_pickups.append((pid, sid, x, r["Website"]))
                        continue
                    lk = "loc|%s|%s|%s" % (nkey(name), role, nkey(x.get("place_name")))
                    xloc = reg.get("co-loc", lk)
                    xfips = FIPS.get((x.get("county") or "").strip(), rfips)
                    out["locations"].append({
                        "location_id": xloc, "name": x.get("place_name") or "",
                        "kind": "public_venue" if role == "pickup" else ("outlet_site" if role == "store" else "farm"), "address": x.get("address") or "",
                        "city": x.get("place_city") or "", "zip": x.get("zip") or "", "hide_address": "false",
                        "state": "CO", "county_fips": xfips, "lat": x.get("lat") or "", "lon": x.get("lon") or "",
                        "geo_source": x.get("geo_source") or "manual", "google_place_id": "", "photo_url": "",
                        "photo_credit": "", "photo_license": ""})
                    out["producer_locations"].append({
                        "producer_location_id": reg.get("co-ploc", lk), "producer_id": pid, "location_id": xloc,
                        "role": role, "days": (x.get("days") or "").replace(", ", ";"),
                        "hours_text": x.get("hours_text") or "",
                        "season_start": x.get("season_start") or "", "season_end": x.get("season_end") or "",
                        "status": "listed", "confirm_url": confirm_url(x, r["Website"])})
                    if xfips and not any(sa["producer_id"] == pid and sa["county_fips"] == xfips
                                         for sa in out["service_areas"]):
                        out["service_areas"].append({"producer_id": pid, "county_fips": xfips,
                                                     "basis": "store" if role == "store" else "pickup", "derived": "true"})
            kinds = [OUTLET_KIND[c] for c in cats_main if c in OUTLET_KIND
                     and (typ == "outlet" or c != "Garden Center / Greenhouse")]
            if kinds:
                oid = reg.get("co-o", sid)
                out["outlets"].append({"outlet_id": oid, "slug": new_slug(name + " outlet"), "name": name,
                                       "kind": kinds[0], "brand": "", "location_id": location_id,
                                       "status": status, "first_seen": "", "last_verified": "", **common})
                rec_ids.append(("outlet", oid))

        for rtype, rid in rec_ids:
            if rtype in ("producer", "market", "access_point"):
                for sl in parsed.slots:
                    out["hours"].append({"record_type": rtype, "record_id": rid, "day": sl.day, "opens": sl.opens,
                                         "closes": sl.closes, "closes_next_day": "true" if sl.closes_next_day else "false",
                                         "inferred": "true" if sl.inferred else "false"})
            if rtype == "producer":
                stated[rid] = (r.get("Sales Locations") or "") + " ; " + (r["Hours"] or "") + " ; " + (r.get("Where to Get It") or "")

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
    for pid, sid, x, site in pending_market_pickups:
        mloc = market_loc.get(nkey(x["market_ref"]))
        if not mloc:
            print("  location not applied (market not in this build): %s -> %s" % (x["name"], x["market_ref"]))
            continue
        out["producer_locations"].append({
            "producer_location_id": reg.get("co-ploc", "loc|%s|pickup|market|%s" % (nkey(x["name"]), nkey(x["market_ref"]))),
            "producer_id": pid, "location_id": mloc, "role": (x.get("role") or "pickup").strip(),
            "days": (x.get("days") or "").replace(", ", ";"), "hours_text": x.get("hours_text") or "",
            "season_start": x.get("season_start") or "", "season_end": x.get("season_end") or "", "status": "listed",
            "confirm_url": confirm_url(x, site)})

    link_markets(out, stated, a.vendors)
    derive_channels(out)
    derive_last_verified(out)

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
