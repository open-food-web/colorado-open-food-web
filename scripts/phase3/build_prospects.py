"""Phase 3: build the prospective-farm list from captured market vendor lists.

Inputs
  source-data/phase3/market_vendor_lists/raw/<market-slug>.json
      One file per market, written during vendor-list capture. Fields: market, city,
      publishes_vendor_list, vendor_list_url, list_season, site_status, notes, vendors[]
      where each vendor has name / list_category / location_stated / description_stated,
      exactly as the market's list shows them (no outside research).

Outputs
  source-data/phase3/market_vendor_lists/markets_checked.csv   one row per market
  source-data/phase3/market_vendor_lists/all_vendors.csv       one row per vendor x market
  data-compiled/phase3/prospective_farms.csv                   farm-like vendors, deduped

County columns (saved in both vendor CSVs; rebuilt the same way every run)
  source-data/phase3/market_vendor_lists/county_by_city.csv    city -> county lookup (reused from the
      Phase 2 dataset's Census/FCC-derived counties; hand-keyed rows are marked in Basis)
  source-data/phase3/market_vendor_lists/county_overrides.csv  researched per-vendor corrections
  County Source says where each county came from, in this order of trust:
    manual           county_overrides.csv (a researched fact, e.g. the vendor's own site)
    location_stated  the town the market's list gives for that vendor
    market_city      the market's own town; only a fallback, vendors may be from a neighboring county
    unresolved       no usable town (e.g. "Denver metro" markets)

Farm classification uses only what the list itself says (section heading, the vendor's
name, the list's product blurb). Every prospect is unresearched; "Already Known" only
compares names against datasets already in the repo.

Run: python scripts/phase3/build_prospects.py
"""
import os
import csv
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(os.environ.get("FOODWEB_SOURCES") or (Path(__file__).resolve().parents[2].parent / "colorado-open-food-web-sources"))
RAW = SRC_ROOT / "source-data/phase3/market_vendor_lists/raw"
OUT_SRC = SRC_ROOT / "source-data/phase3/market_vendor_lists"
OUT_COMPILED = SRC_ROOT / "data-compiled/phase3"

KNOWN_SOURCES = [
    ("Phase 1 live", SRC_ROOT / "data-compiled/farm_fresh_directory_mymaps.csv", "Business Name"),
    ("Phase 2 build", SRC_ROOT / "data-compiled/phase2/co_farmers_markets_all_mymaps.csv", "Business Name"),
    ("CO Proud finder", ROOT / "source-data/phase2/colorado_proud_finder/colorado_proud_finder_raw.csv", "name"),
]

# Section headings that mean "this vendor grows or raises food/plants".
FARM_CATEGORY = re.compile(
    r"farm|grower|produce|rancher|ranch|meat|poultry|dairy|egg|honey|apiar|flower|floral|"
    r"orchard|fruit|vegetable|veggie|agricultur|mushroom|microgreen|plant|nursery|seedling|"
    r"cheese|creamery|beef|lamb|pork|bison|garden",
    re.I,
)
# Section headings that clearly aren't farms, even if a farm word sneaks into the name.
NON_FARM_CATEGORY = re.compile(
    r"service|info|non[- ]?profit|community|sponsor|music|entertain|performer|"
    r"food truck|concession|prepared[- ]food|ready[- ]to[- ]eat|craft|artisan|art\b|jewel|"
    r"bod(y|ies)|skincare|apparel|clothing|bak(er|ed|ery)|musician|sponsor|retail|packaged|"
    r"specialty|beverage|drink|pantry|ready[- ]to[- ]consume|wine|spirit|health|wellness|"
    r"beauty|dealer|bread|sweets",
    re.I,
)
FARM_NAME = re.compile(
    r"\b(farms?|ranch(es)?|orchards?|acres|homestead|greenhouses?|gardens?|creamery|dairy|"
    r"apiar(y|ies)|bees|honey|vineyards?|growers?|produce|cattle|beef|poultry|eggs|"
    r"mushrooms?|microgreens?|flowers?|nursery|hives?|meats?|pastures?|fields)\b",
    re.I,
)
# A blurb counts only if it talks about growing/raising, or its product line opens with a
# raw farm product ("Lamb", "Vegetables, specialty tomatoes..."). Bare mentions of fruit or
# honey as ingredients (pickles, pies, mixers) don't.
FARM_DESC = re.compile(
    r"\b(we grow|grown (on|at|in) our|raised (on|at) our|our farm|on (the|our) farm|"
    r"grass[- ]fed|pasture[- ]raised|cut flowers|plant starts|seedlings)\b"
    r"|^\s*(find\s+)?(fresh\s+)?(produce|vegetables|veggies|fruits?|lamb|beef|pork|eggs|honey|"
    r"microgreens|mushrooms|flowers|peaches|apples|garlic|chiles|chilies)\b",
    re.I,
)

FIELDS_MARKETS = ["Market Slug", "Market", "City", "Publishes Vendor List", "Vendor List URL",
                  "List Season", "Site Status", "Vendors Captured", "Checked", "Notes"]
FIELDS_VENDORS = ["Vendor Name", "Market", "Market City", "List Category", "Location Stated",
                  "Description Stated", "List Season", "Vendor List URL", "Farm Signal",
                  "County", "County Source"]
FIELDS_PROSPECTS = ["Prospect Name", "Farm Signal", "Signal Detail", "List Categories",
                    "Locations Stated", "Description Stated", "Market Count", "Markets",
                    "List Seasons", "Already Known", "Known Match", "Possible Match", "Status",
                    "County", "County Source"]


def clean(s):
    if s is None:
        return ""
    s = str(s).replace("�", "'").replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def norm(name):
    """Name key for dedup/matching: case, punctuation, legal suffixes and 'the' removed."""
    s = clean(name).lower().replace("&", " and ").replace("'", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(llc|inc|co|company|ltd|the)\b", " ", s)
    s = re.sub(r"\bfarms\b", "farm", s)
    return re.sub(r"\s+", " ", s).strip()


def farm_signal(v):
    """Return (strength, detail) using only the list's own text."""
    cat, name, desc = clean(v.get("list_category")), clean(v.get("name")), clean(v.get("description_stated"))
    farm_cat = bool(cat and FARM_CATEGORY.search(cat))
    non_farm_cat = bool(cat and NON_FARM_CATEGORY.search(cat))
    if non_farm_cat and not farm_cat:
        return "", ""  # the list itself files it under a non-farm section
    if farm_cat and not non_farm_cat:
        return "strong", f"list section: {cat}"
    # mixed sections ("Packaged Food, Drink, and Honey") fall through to name/description
    if FARM_NAME.search(name):
        return "medium", f"name: {FARM_NAME.search(name).group(0)}"
    if desc and FARM_DESC.search(desc):
        return "weak", f"description: {FARM_DESC.search(desc).group(0)}"
    return "", ""


def load_county_tables():
    by_city, overrides = {}, {}
    with open(OUT_SRC / "county_by_city.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_city[r["City"].strip().lower()] = r["County"].strip()
    path = OUT_SRC / "county_overrides.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                overrides[(norm(r["Vendor Name"]), clean(r["Market"]).lower())] = r["County"].strip()
    return by_city, overrides


def stated_counties(location, by_city):
    """Counties for a 'Town, CO' / 'Town, CO, Town2, CO' / 'X County' location string."""
    counties = []
    for part in re.split(r",\s*(?:CO|Colorado)\b,?\s*", clean(location)):
        part = part.strip(" ,")
        if not part:
            continue
        if part.lower().endswith(" county"):
            c = part[:-7].strip()
        else:
            c = by_city.get(part.lower(), "")
        if c and c not in counties:
            counties.append(c)
    return counties


def vendor_county(name, market, city, location, tables):
    """(county, source) for one vendor at one market."""
    by_city, overrides = tables
    for key in ((norm(name), clean(market).lower()), (norm(name), "")):
        if key in overrides:
            return overrides[key], "manual"
    cs = stated_counties(location, by_city)
    if cs:
        return "; ".join(cs), "location_stated"
    c = by_city.get(clean(city).lower(), "")
    return (c, "market_city") if c else ("", "unresolved")


def load_first_pass():
    """Prospect name -> verdict from the first-pass screen (first_pass.csv), if it exists."""
    path = OUT_SRC / "first_pass.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["Prospect Name"]: r["Verdict"] for r in csv.DictReader(f)}


def load_known():
    known = {}
    for label, path, col in KNOWN_SOURCES:
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                k = norm(row.get(col, ""))
                if k and k not in known:
                    known[k] = f"{label}: {clean(row[col])}"
    return known


def near_match(key, known):
    """Closest existing name for a human to confirm (spelling/suffix variants)."""
    hits = difflib.get_close_matches(key, known.keys(), n=1, cutoff=0.88)
    return known[hits[0]] if hits else ""


def main():
    markets, vendor_rows = [], []
    tables = load_county_tables()
    for p in sorted(RAW.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        vendors = d.get("vendors") or []
        markets.append({
            "Market Slug": d.get("slug") or p.stem, "Market": clean(d.get("market")),
            "City": clean(d.get("city")), "Publishes Vendor List": d.get("publishes_vendor_list", ""),
            "Vendor List URL": d.get("vendor_list_url") or "", "List Season": d.get("list_season") or "",
            "Site Status": d.get("site_status", ""), "Vendors Captured": len(vendors),
            "Checked": d.get("checked", ""), "Notes": clean(d.get("notes")),
        })
        for v in vendors:
            if not clean(v.get("name")):
                continue
            strength, _ = farm_signal(v)
            county, county_src = vendor_county(v["name"], d.get("market"), d.get("city"),
                                               v.get("location_stated"), tables)
            vendor_rows.append({
                "Vendor Name": clean(v["name"]), "Market": clean(d.get("market")),
                "Market City": clean(d.get("city")), "List Category": clean(v.get("list_category")),
                "Location Stated": clean(v.get("location_stated")),
                "Description Stated": clean(v.get("description_stated")),
                "List Season": d.get("list_season") or "", "Vendor List URL": d.get("vendor_list_url") or "",
                "Farm Signal": strength, "County": county, "County Source": county_src, "_v": v,
            })

    rank = {"strong": 3, "medium": 2, "weak": 1, "": 0}
    groups = defaultdict(list)
    for r in vendor_rows:
        if r["Farm Signal"]:
            groups[norm(r["Vendor Name"])].append(r)

    known = load_known()
    first_pass = load_first_pass()
    prospects = []
    for key, rows in groups.items():
        best = max(rows, key=lambda r: rank[r["Farm Signal"]])
        # display the best-capitalised spelling any market used
        display = max((r["Vendor Name"] for r in rows), key=lambda n: sum(c.isupper() for c in n) > 0 and not n.isupper())
        _, detail = farm_signal(best["_v"])
        uniq = lambda field: "; ".join(dict.fromkeys(r[field] for r in rows if r[field]))
        market_names = list(dict.fromkeys(r["Market"] for r in rows))
        desc = max((r["Description Stated"] for r in rows), key=len, default="")
        # Best evidence wins: researched > the vendor's stated town > the markets' towns.
        # market_city counties are only candidates (a vendor may come from a neighboring county).
        for src in ("manual", "location_stated", "market_city"):
            hit = [r["County"] for r in rows if r["County Source"] == src and r["County"]]
            if hit:
                county = "; ".join(dict.fromkeys(c for h in hit for c in h.split("; ")))
                county_src = src
                break
        else:
            county, county_src = "", "unresolved"
        prospects.append({
            "Prospect Name": display, "Farm Signal": best["Farm Signal"],
            "Signal Detail": detail, "List Categories": uniq("List Category"),
            "Locations Stated": uniq("Location Stated"), "Description Stated": desc,
            "Market Count": len(market_names), "Markets": "; ".join(market_names),
            "List Seasons": uniq("List Season"),
            "Already Known": "yes" if key in known else "no", "Known Match": known.get(key, ""),
            "Possible Match": "" if key in known else near_match(key, known),
            "Status": ("first pass: " + first_pass[display].replace("_", " ")) if display in first_pass
                      else "prospect - unresearched",
            "County": county, "County Source": county_src,
        })
    prospects.sort(key=lambda p: (p["Already Known"] == "yes", -rank[p["Farm Signal"]],
                                  -p["Market Count"], p["Prospect Name"].lower()))

    OUT_COMPILED.mkdir(parents=True, exist_ok=True)
    write(OUT_SRC / "markets_checked.csv", FIELDS_MARKETS, markets)
    write(OUT_SRC / "all_vendors.csv", FIELDS_VENDORS,
          [{k: v for k, v in r.items() if k != "_v"} for r in vendor_rows])
    write(OUT_COMPILED / "prospective_farms.csv", FIELDS_PROSPECTS, prospects)

    print("county sources: " + ", ".join(
        f"{s}: {sum(r['County Source'] == s for r in vendor_rows)}"
        for s in ("manual", "location_stated", "market_city", "unresolved")))
    yes = sum(m["Publishes Vendor List"] == "yes" for m in markets)
    new = sum(p["Already Known"] == "no" for p in prospects)
    print(f"markets checked: {len(markets)} | with vendor lists: {yes} | vendor rows: {len(vendor_rows)}")
    print(f"farm prospects: {len(prospects)} ({new} not already in repo data) | "
          + ", ".join(f"{s}: {sum(p['Farm Signal'] == s for p in prospects)}" for s in ("strong", "medium", "weak")))


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
