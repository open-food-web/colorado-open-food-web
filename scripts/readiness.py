#!/usr/bin/env python3
"""How ready is the Food Web's data for a Chaffee Provides style page, statewide?

Reads the canonical tables and counts, per field and per county, what that page needs from a producer:
a town, a product group, a confirmed way to buy, somewhere to find them, and a way to contact them. A
producer is "ready" when it has all five, "near" when it lacks exactly one, and "gap" otherwise. The same
numbers say which fields to research first.

  python scripts/readiness.py                       # whole state, markdown on screen
  python scripts/readiness.py --county 08015        # one county
  python scripts/readiness.py --out docs/readiness.md

Pure counting: it changes no data. Rerun after each snapshot PR to see the gaps close.
"""
import argparse
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(HERE, "..", "data", "colorado")
SKIP_STATUS = {"closed", "removed"}
# Channels that mean a customer can buy without visiting a pin: the page can still say how.
REMOTE_CHANNELS = {"online", "delivery"}
PIN_CHANNELS = {"farm_stand", "u_pick"}
COUNTY_NAMES = {
    "08001": "Adams",
    "08003": "Alamosa",
    "08005": "Arapahoe",
    "08007": "Archuleta",
    "08009": "Baca",
    "08011": "Bent",
    "08013": "Boulder",
    "08014": "Broomfield",
    "08015": "Chaffee",
    "08017": "Cheyenne",
    "08019": "Clear Creek",
    "08021": "Conejos",
    "08023": "Costilla",
    "08025": "Crowley",
    "08027": "Custer",
    "08029": "Delta",
    "08031": "Denver",
    "08033": "Dolores",
    "08035": "Douglas",
    "08037": "Eagle",
    "08039": "Elbert",
    "08041": "El Paso",
    "08043": "Fremont",
    "08045": "Garfield",
    "08047": "Gilpin",
    "08049": "Grand",
    "08051": "Gunnison",
    "08053": "Hinsdale",
    "08055": "Huerfano",
    "08057": "Jackson",
    "08059": "Jefferson",
    "08061": "Kiowa",
    "08063": "Kit Carson",
    "08065": "Lake",
    "08067": "La Plata",
    "08069": "Larimer",
    "08071": "Las Animas",
    "08073": "Lincoln",
    "08075": "Logan",
    "08077": "Mesa",
    "08079": "Mineral",
    "08081": "Moffat",
    "08083": "Montezuma",
    "08085": "Montrose",
    "08087": "Morgan",
    "08089": "Otero",
    "08091": "Ouray",
    "08093": "Park",
    "08095": "Phillips",
    "08097": "Pitkin",
    "08099": "Prowers",
    "08101": "Pueblo",
    "08103": "Rio Blanco",
    "08105": "Rio Grande",
    "08107": "Routt",
    "08109": "Saguache",
    "08111": "San Juan",
    "08113": "San Miguel",
    "08115": "Sedgwick",
    "08117": "Summit",
    "08119": "Teller",
    "08121": "Washington",
    "08123": "Weld",
    "08125": "Yuma",
}
# Fields export_app.py will list under "confirmed by" (FIELD_LABEL there)
CONFIRMABLE = {"phone", "email", "website", "facebook", "instagram", "hours_text", "seasonal_months", "products", "address",
               "city", "zip", "source_categories", "certified_organic", "accepts_snap", "ada_accessible"}
NEEDS = ["town", "product_group", "channel", "place_to_find", "contact"]


def read(tables, name):
    path = os.path.join(tables, name + ".csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def lst(v):
    return [x for x in (v or "").split(";") if x]


def load(tables):
    T = {n: read(tables, n) for n in ("producers", "locations", "producer_locations", "outlets", "markets",
                                      "market_vendors", "hours", "field_sources", "service_areas")}
    T["loc"] = {r["location_id"]: r for r in T["locations"]}
    return T


def county_label(fips):
    return "%s (%s)" % (COUNTY_NAMES[fips], fips) if fips in COUNTY_NAMES else fips


def true(v):
    return (v or "").strip().lower() == "true"


def producer_rows(T):
    """One row per live producer, mirroring how scripts/export_app.py decides what a page can show."""
    plocs = collections.defaultdict(list)
    for r in T["producer_locations"]:
        plocs[r["producer_id"]].append(r)
    # a market link only counts when the market itself is exported (not closed or removed)
    live_markets = {m["market_id"] for m in T["markets"] if m["status"] not in SKIP_STATUS}
    in_market = {r["producer_id"] for r in T["market_vendors"] if r["market_id"] in live_markets}
    has_hours = {r["record_id"] for r in T["hours"] if r["record_type"] == "producer"}
    confirmed = set()
    for r in T["field_sources"]:
        if r["record_type"] != "producer" or r["field"] not in CONFIRMABLE:
            continue
        # the same test as confirmed_by() in export_app.py: a partner, or the business's own site or Facebook page
        if r["verified_by"] == "partner" or r["source"] == "producer_site":
            if r["source"] != "guidestone" and r["field"] in ("facebook", "instagram", "website"):
                continue    # a page "confirming" its own link says nothing
            confirmed.add(r["record_id"])
    out = []
    for p in T["producers"]:
        if p["status"] in SKIP_STATUS:
            continue
        pid = p["producer_id"]
        locs = plocs.get(pid, [])
        home = next((T["loc"].get(l["location_id"]) for l in locs if l["role"] == "home_base"), None) or {}
        channels = set(lst(p["sales_channels"])) - {"agritourism"}   # not a way to buy food
        sells_at_farm = bool(PIN_CHANNELS & channels)
        others = [T["loc"].get(l["location_id"]) or {} for l in locs if l["role"] != "home_base"]
        pinned_other = any(o.get("lat") and o.get("lon") for o in others)
        # export_app.py: the home base is pinned for farm_stand/u_pick or a stated farm pickup (confirmed), or, while no channel is set, as an
        # unconfirmed pin; it needs coordinates and either a street address or a hidden one (pinned at the town).
        home_ok = bool(home.get("lat") and home.get("lon")) and (bool(home.get("address")) or true(home.get("hide_address")))
        # a person's "customers collect orders at the farm" or a stated visit also confirms the home pin (same rule as export_app.py)
        pinned_home = home_ok and (sells_at_farm or true(p["farm_pickup"]) or (p.get("visits") or "").strip().lower() not in ("", "none"))
        pin_unconfirmed = home_ok and not channels
        place = pinned_home or pinned_other or pid in in_market or bool(REMOTE_CHANNELS & channels)
        contact = any(p[k] for k in ("website", "phone", "email", "facebook", "instagram"))
        # visit answers: a person's answer, else what the listing implies (same rules as export_app.py)
        home_id = next((l["location_id"] for l in locs if l["role"] == "home_base"), None)
        home_addr = (home.get("address") or "").strip().lower()
        farm_is_a_spot = any(l["role"] in ("pickup", "farm_stand", "csa_dropoff") and (
            l["location_id"] == home_id
            or (home_addr and ((T["loc"].get(l["location_id"]) or {}).get("address") or "").strip().lower() == home_addr))
            for l in locs)
        dropin_set, pickup_set = p["dropin_visits"] != "", p["farm_pickup"] != ""
        dropin_known = dropin_set or sells_at_farm
        pickup_known = pickup_set or farm_is_a_spot or dropin_known or "Agritourism" in lst(p["source_categories"])
        row = {
            "id": pid, "producer_type": p["producer_type"] or "(none)", "county": home.get("county_fips") or "(none)",
            "town": bool(home.get("city")), "product_group": bool(p["product_groups"]), "products_text": bool(p["products"]),
            "channel": bool(channels), "place_to_find": place, "contact": contact,
            "pin": pinned_home or pinned_other, "pin_unconfirmed": pin_unconfirmed, "market": pid in in_market,
            "website": bool(p["website"]), "phone": bool(p["phone"]), "email": bool(p["email"]),
            "social": bool(p["facebook"] or p["instagram"]),
            "hours": pid in has_hours, "dropin_set": dropin_set, "dropin_known": dropin_known,
            "pickup_set": pickup_set, "pickup_known": pickup_known,
            "confirmed": pid in confirmed, "verified_date": bool(p["last_verified"]),
            "home_geocoded": bool(home.get("lat") and home.get("lon")), "home_address": bool(home.get("address")),
            "hidden_address": true(home.get("hide_address")), "home_county": bool(home.get("county_fips")),
            "claimed": true(p["claimed"]),
        }
        missing = [n for n in NEEDS if not row[n]]
        row["missing"] = missing
        row["tier"] = "ready" if not missing else ("near" if len(missing) == 1 else "gap")
        out.append(row)
    return out


def pct(n, d):
    return "%d%%" % round(100.0 * n / d) if d else "-"


def report(T, county=None):
    rows = producer_rows(T)
    if county:
        rows = [r for r in rows if r["county"] == county]
    n = len(rows)
    L = ["# Statewide readiness" + (" (county %s)" % county if county else ""), "",
         "Counts from `data/colorado`. A producer is **ready** for a Chaffee Provides style page when it has a town, a product group, "
         "a sales channel, a place to find them (a pin, a market, or online/delivery) and a way to contact them. "
         "**Near** lacks exactly one; **gap** lacks more.", ""]
    tiers = collections.Counter(r["tier"] for r in rows)
    L += ["## Producers: %d" % n, "", "| Tier | Producers | Share |", "|---|---|---|"]
    for t in ("ready", "near", "gap"):
        L.append("| %s | %d | %s |" % (t, tiers[t], pct(tiers[t], n)))
    L += ["", "## What is missing, field by field", "", "| Field | Have it | Share | Why the page needs it |", "|---|---|---|---|"]
    why = [("town", "Town on every card and the town filter"), ("product_group", "Product filter chips"),
           ("products_text", "'What they offer' text"), ("channel", "How to buy; drives pins and the ways list"),
           ("place_to_find", "Something to put on the map or a way to buy"), ("pin", "A pin on the map"),
           ("pin_unconfirmed", "Home pin with no channel set yet (drawn lighter)"), ("market", "Linked to a farmers market page"), ("contact", "Any way to reach them"),
           ("website", "Website link"), ("phone", "Phone"), ("email", "Email (only if the business lists it)"),
           ("social", "Facebook or Instagram"), ("hours", "Structured hours"),
           ("dropin_set", "Drop-in answer set by a person"), ("dropin_known", "Drop-in answer set or implied by a farm stand or u-pick"),
           ("pickup_set", "Farm pickup answer set by a person"), ("pickup_known", "Farm pickup answer set or implied"),
           ("claimed", "Claimed by the business"), ("hidden_address", "Address withheld (pin at the nearest town)"),
           ("home_county", "County known (needed for the county filter)"),
           ("confirmed", "'Confirmed by' line (partner or the business's own site)"),
           ("verified_date", "'Checked on' date"), ("home_address", "Street address at the home base"),
           ("home_geocoded", "Coordinates at the home base")]
    for k, w in why:
        c = sum(r[k] for r in rows)
        L.append("| %s | %d | %s | %s |" % (k, c, pct(c, n), w))
    L += ["", "## Only one thing missing (the cheapest wins)", "", "| Missing | Producers |", "|---|---|"]
    near = collections.Counter(r["missing"][0] for r in rows if r["tier"] == "near")
    for k, c in near.most_common():
        L.append("| %s | %d |" % (k, c))
    L += ["", "## By producer type", "", "| Producer type | Producers | Ready | Near | Gap |", "|---|---|---|---|---|"]
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["producer_type"]][r["tier"]] += 1
    for k, c in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
        L.append("| %s | %d | %d | %d | %d |" % (k, sum(c.values()), c["ready"], c["near"], c["gap"]))
    if not county:
        L += ["", "## By county (largest 20)", "", "| County | Producers | Ready | Near | Gap | Ready share |", "|---|---|---|---|---|---|"]
        cb = collections.defaultdict(collections.Counter)
        for r in rows:
            cb[r["county"]][r["tier"]] += 1
        for k, c in sorted(cb.items(), key=lambda kv: -sum(kv[1].values()))[:20]:
            L.append("| %s | %d | %d | %d | %d | %s |" % (county_label(k), sum(c.values()), c["ready"], c["near"], c["gap"], pct(c["ready"], sum(c.values()))))
    # Other record types the page shows
    outs = [o for o in T["outlets"] if o["status"] not in SKIP_STATUS]
    mks = [m for m in T["markets"] if m["status"] not in SKIP_STATUS]
    if county:
        outs = [o for o in outs if (T["loc"].get(o["location_id"]) or {}).get("county_fips") == county]
        mks = [m for m in mks if (T["loc"].get(m["location_id"]) or {}).get("county_fips") == county]
    ok = collections.Counter(o["kind"] for o in outs)
    L += ["", "## Outlets (shops, grocers, dining): %d" % len(outs), "", "| Kind | Count |", "|---|---|"]
    L += ["| %s | %d |" % (k, c) for k, c in ok.most_common()]
    geo = sum(1 for o in outs if (T["loc"].get(o["location_id"]) or {}).get("lat"))
    L += ["", "With coordinates: %d (%s). With a website: %d. With a phone: %d. Supplier links (`outlet_suppliers`): not built yet."
          % (geo, pct(geo, len(outs)), sum(1 for o in outs if o["website"]), sum(1 for o in outs if o["phone"]))]
    mh = {r["record_id"] for r in T["hours"] if r["record_type"] == "market"}
    L += ["", "## Farmers markets: %d" % len(mks), "",
          "With hours: %d. With a website: %d. With coordinates: %d. With vendors linked: %d."
          % (sum(1 for m in mks if m["market_id"] in mh), sum(1 for m in mks if m["website"]),
             sum(1 for m in mks if (T["loc"].get(m["location_id"]) or {}).get("lat")),
             len({r["market_id"] for r in T["market_vendors"]} & {m["market_id"] for m in mks}))]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", default=TABLES)
    ap.add_argument("--county", help="county FIPS, for example 08015")
    ap.add_argument("--out", help="write markdown here instead of printing")
    a = ap.parse_args()
    text = report(load(a.tables), a.county)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote", a.out)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
