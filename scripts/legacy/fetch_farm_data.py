#!/usr/bin/env python3
"""Re-pull the Colorado Proud Farm Fresh Directory from ArcGIS and rebuild both CSVs.

Source: the public ArcGIS Feature Service behind the map on
https://coloradoproud.com/find-farm-fresh-favorites/ (see DATA.md for how it was traced).

Outputs (into ../data/):
  - colorado_proud_farm_fresh_directory_raw.csv : all 47 fields + Latitude/Longitude
  - farm_fresh_directory_mymaps.csv             : cleaned, Google My Maps import-ready

Usage:
  python scripts/fetch_farm_data.py
"""
import csv
import json
import os
import urllib.request

FS = ("https://services3.arcgis.com/DgjqnJA1rgO92Soi/arcgis/rest/services/"
      "Farm_Fresh_Directory/FeatureServer/0/query")
QUERY = "?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=json"

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

# Colorado Proud "Operation type" is pipe-separated and multi-valued. Each value maps
# exactly to one of our Category labels; this list's order is the priority order, and
# the first match is the record's primary category (it sets the map pin's color/icon).
# Values that aren't a way to buy from the farm ("Centennial Farm/Ranch" is a heritage
# designation, "Community Gardens") are dropped. Exception: a Centennial ranch with no
# other type (e.g. Princess Beef, which sells beef direct) is On-Farm / Ranch Sales,
# since it is listed in a farm-direct directory. Nothing mapped at all -> "Other".
PRIORITY = [
    ("Winery", "Winery"), ("U-pick", "U-Pick"), ("Farmers' Market", "Farmers' Market"),
    ("CSA Farm", "CSA Farm"), ("Roadside Market", "Roadside Market"),
    ("Greenhouse", "Garden Center / Greenhouse"), ("Garden Center", "Garden Center / Greenhouse"),
    ("Agritourism", "Agritourism"), ("Restaurant", "Restaurant"),
    ("On-Farm/Ranch sales", "On-Farm / Ranch Sales"),
    ("Sell to Schools", "Sells to Schools"),
]
CATEGORY_SEP = ", "  # Category column joins multiple labels, primary first

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PROD_FIELDS = [
    "Produce Categories 1", "Produce Categories 2", "Produce Categories 3",
    "Produce Categories (other)", "Meat Categories", "Game", "Fish", "Meat (other)",
    "Miscellaneous 1", "Miscellaneous 2", "Miscellaneous (Other)", "Wines",
]


def pipes(s):
    return ", ".join(p.strip() for p in (s or "").split("|") if p.strip())


def categories(op):
    """'U-pick|On-Farm/Ranch sales' -> ['U-Pick', 'On-Farm / Ranch Sales'] (priority order)."""
    values = {p.strip().lower() for p in (op or "").split("|") if p.strip()}
    out = []
    for key, label in PRIORITY:
        if key.lower() in values and label not in out:
            out.append(label)
    if not out and "centennial farm/ranch" in values:
        out.append("On-Farm / Ranch Sales")
    return out or ["Other"]


# Hand-checked corrections to Colorado Proud's operation types, reapplied on every
# re-fetch so a refresh can't undo them. Keyed by business name (trimmed).
CATEGORY_CORRECTIONS = {
    # Year-round nonprofit local-food store with daily hours; CP files it as a
    # farmers' market. Its farm-to-table dinners keep the Agritourism label.
    "Yampa Valley Foods": ["Grocery Store", "Agritourism"],
    # CP has no store type; it's listed only as "Retail Market" in the free-text field.
    "Mountain Market & Supply": ["Grocery Store"],
}


# Hand-checked field corrections, keyed by Colorado Proud's business name and
# reapplied on every re-fetch (same idea as CATEGORY_CORRECTIONS). Only fixes a
# listing's own official source confirms.
FIELD_CORRECTIONS = {
    # Colorado Proud lists the organizer and its mailing PO box (pinned in Denver).
    # denverceliacs.org/event/gluten-free-farmers-market-8/ (checked 2026-10-04):
    # "Gluten Free Farmers Market", 333 W Hampden Ave, Englewood, 2nd Saturday
    # monthly June-October, 9am-1pm.
    "National Celiac Association of Denver": {
        "Business Name": "Gluten Free Farmers Market",
        "Address": "333 W Hampden Ave (north parking lot next to Chase Tower)",
        "City": "Englewood", "County": "Arapahoe", "Zip": "80110",
        "Hours": "Second Saturday of each month, 9:00 AM - 1:00 PM",
        "Notes": "Colorado's only gluten-free farmers market, run by NCA Denver Celiacs "
                 "(National Celiac Association of Denver). Food trucks, small businesses, "
                 "produce, crafts, art, herbs, house plants, canned goods, prepared foods, "
                 "flowers and more.",
        "Latitude": 39.653348996279, "Longitude": -104.991625229897,
    },
}


def corrected(row):
    fix = FIELD_CORRECTIONS.get((row.get("Business Name") or "").strip())
    if fix:
        row.update(fix)
    return row


def categories_for(name, op):
    return CATEGORY_CORRECTIONS.get((name or "").strip()) or categories(op)


def fetch():
    req = urllib.request.Request(FS + QUERY, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def write_raw(d, path):
    fields = [f for f in d["fields"] if f["name"] != "ObjectID"]
    names = [f["name"] for f in fields]
    alias = {f["name"]: f.get("alias", f["name"]) for f in fields}
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow([alias[n] for n in names] + ["Latitude", "Longitude"])
        for ft in d["features"]:
            a = ft.get("attributes", {})
            g = ft.get("geometry") or {}
            w.writerow([a.get(n, "") for n in names] + [g.get("y", ""), g.get("x", "")])


def a(ft, alias_to_name, alias):
    """Get an attribute by its alias label."""
    return (ft["attributes"].get(alias_to_name.get(alias, ""), "") or "").strip()


def write_mymaps(d, path):
    # map alias -> raw field name so we can read by human label
    alias_to_name = {f.get("alias", f["name"]): f["name"] for f in d["fields"]}

    def get(ft, label):
        return (ft["attributes"].get(alias_to_name.get(label, ""), "") or "").strip()

    def addr(ft):
        line1 = get(ft, "Address Line 1")
        line2 = get(ft, "Address Line 2")
        return (line1 + " " + line2).strip() if line2 else line1

    def hours(ft):
        parts = [f"{day[:3]}: {get(ft, 'Hours on ' + day)}"
                 for day in DAYS if get(ft, "Hours on " + day)]
        return "; ".join(parts)

    def products(ft):
        vals = [pipes(get(ft, f)) for f in PROD_FIELDS]
        return ", ".join(v for v in vals if v)

    cols = ["Business Name", "Category", "Address", "City", "County", "State", "Zip",
            "Phone", "Call first?", "Website", "Email", "Facebook", "Instagram",
            "Hours", "Months Open", "Products", "Certified Organic", "SNAP",
            "ADA Accessible", "Notes", "Where to Get It", "Latitude", "Longitude"]

    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for ft in d["features"]:
            g = ft.get("geometry") or {}
            w.writerow(corrected({
                "Business Name": get(ft, "Business Name"),
                "Category": CATEGORY_SEP.join(categories_for(get(ft, "Business Name"), get(ft, "Operation type"))),
                "Address": addr(ft), "City": get(ft, "City"), "County": get(ft, "County"),
                "State": get(ft, "State"), "Zip": get(ft, "Zip"),
                "Phone": get(ft, "Telephone Number"),
                "Call first?": get(ft, "Should the customer call first?"),
                "Website": get(ft, "Website"), "Email": get(ft, "Email Address"),
                "Facebook": get(ft, "Facebook"), "Instagram": get(ft, "Instagram"),
                "Hours": hours(ft), "Months Open": pipes(get(ft, "Months open for business")),
                "Products": products(ft),
                "Certified Organic": get(ft, "Certified organic"),
                "SNAP": get(ft, "SNAP accepted"),
                "ADA Accessible": get(ft, "ADA accessible"),
                "Notes": get(ft, "Additional information"),
                "Where to Get It": "",  # hand-curated for wholesale growers; not in Colorado Proud
                "Latitude": g.get("y", ""), "Longitude": g.get("x", ""),
            }))


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    d = fetch()
    n = len(d["features"])
    write_raw(d, os.path.join(DATA_DIR, "colorado_proud_farm_fresh_directory_raw.csv"))
    write_mymaps(d, os.path.join(DATA_DIR, "farm_fresh_directory_mymaps.csv"))
    print(f"Pulled {n} farms. Rebuilt both CSVs in {os.path.normpath(DATA_DIR)}.")


if __name__ == "__main__":
    main()
