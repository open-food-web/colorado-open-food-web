"""Source: Colorado Proud member directory (coloradoproud.com/product-finder/).

This is the FULL Colorado Proud membership (~1,550 businesses of every type), not the
Farm Fresh ArcGIS layer that sources/colorado_proud.py reads. The finder is WordPress
with everything server-rendered; there is no JSON API behind it.

Two passes:
1. Listing - `/product-finder/?query&address_query&filter=Business_Type&paged=N`, 300
   cards per page. Each card is `<a href="/business/?bid=business_profile_N"
   class="featuredBusiness ..." data-filter="..." data-lat data-lng>` with name,
   street, "City, Colorado ZIP" and phone. The class/data-filter tokens are CamelCase
   slugs (e.g. "FarmRanch"), so they are kept only as a fallback.
2. Profile - `/business/?bid=...` gives human-readable labels in `.prettyArray` divs
   grouped under headings: Business Type, Products, Product Attributes, Payment
   Methods, Business Attributes; plus website, socials and a description.

Phase 2 source (maintainer decision 2026-10-04: Colorado Proud members belong in Phase 2;
this replaces the Phase 3 hold in PR #20). Only in-scope types (TYPE_CATEGORIES) become
records; build.py ranks it after curated research and before USDA.

Refresh (network): python scripts/scrape/refresh_sources.py colorado_proud_finder
  Re-reads the 6 listing pages and fetches profiles only for members it has never seen
  (.cache/colorado_proud_finder/profiles.jsonl; CPF_REFRESH=1 recrawls all ~1,550,
  ~40 min). Writes the snapshot plus full-membership reports (every type, in scope or
  not) to source-data/phase2/colorado_proud_finder/.

Parsers are pure (regex over the very regular markup) so they can be tested offline.
"""
from __future__ import annotations

import html as htmllib
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict, Iterable, List, Optional

from ..normalize import (facebook_url, in_colorado, instagram_url, name_key,
                         phone, website_url, zipcode)
from ..schema import Market
from ..useragent import USER_AGENT

SOURCE = "colorado_proud_finder"
BASE = "https://coloradoproud.com"
LIST_URL = BASE + "/product-finder/?query&address_query&filter=Business_Type&paged={page}"
PROFILE_URL = BASE + "/business/?bid={bid}"
HDR = {"User-Agent": USER_AGENT}
CRAWL_DELAY = 1.5  # robots.txt is empty; stay polite anyway

PROFILE_GROUPS = {
    "Business Type": "business_types",
    "Products": "products",
    "Product Attributes": "product_attributes",
    "Payment Methods": "payment_methods",
    "Business Attributes": "business_attributes",
}

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
CACHE_PATH = os.path.join(REPO, ".cache", SOURCE, "profiles.jsonl")
REPORT_DIR = os.path.join(REPO, ".cache", "reports", SOURCE)

# Scope: which Colorado Proud business types go on the trail, and as what site category.
# Order = priority, so a multi-type business gets its most farm-like label first.
# Decided with the maintainer 2026-10-04: farm-direct + markets + wineries, plus local
# food shops and makers/eateries. Out: breweries, distilleries, manufacturers,
# wholesalers/distributors, ag suppliers, food trucks, coffee/bars, institutions.
TYPE_CATEGORIES = [
    ("Farmers Market", "Farmers' Market"),
    ("Farm / Ranch", "On-Farm / Ranch Sales"),
    ("Farm Market", "On-Farm / Ranch Sales"),
    ("Livestock Producer", "On-Farm / Ranch Sales"),
    ("Orchard", "On-Farm / Ranch Sales"),
    ("Apiary", "On-Farm / Ranch Sales"),
    ("Dairy", "On-Farm / Ranch Sales"),
    ("Cheeserie", "On-Farm / Ranch Sales"),
    ("Grazer", "On-Farm / Ranch Sales"),
    ("Fishery", "On-Farm / Ranch Sales"),
    ("Farm / Roadside Stand", "Roadside Market"),
    ("Produce Market", "Roadside Market"),
    ("Winery", "Winery"),
    ("Cider Mill / Press", "Agritourism"),
    ("Dude Ranch", "Agritourism"),
    ("Bed & Breakfast", "Agritourism"),
    ("Tourism", "Agritourism"),
    ("Meat & Poultry Market", "Meat Producer & Packer"),
    ("Meat Packer / Processor", "Meat Producer & Packer"),
    ("Food Bank", "Food Bank"),
    ("Grocery Store", "Grocery Store"),
    ("Cooperative Grocery Store", "Grocery Store"),
    ("Specialty Food Store", "Grocery Store"),
    ("Bakery", "Bakery"),
    ("Cottage Food", "Food Maker"),
    ("Value-Added Producer / Processor", "Food Maker"),
    ("Restaurant", "Restaurant"),
    ("Caterer", "Caterer"),
]
# Source junk: not a business.
EXCLUDE_BIDS = {"business_profile_703"}  # "Accessibility Test"
# Some members' address is the form's placeholder; treat it as unknown.
PLACEHOLDER_STREET = re.compile(r"^12345 Test St", re.I)


# ---- fetching -----------------------------------------------------------------

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=HDR)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(CRAWL_DELAY * 4 * (attempt + 1))
    raise RuntimeError("unreachable")


# ---- parsing ------------------------------------------------------------------

def _text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return htmllib.unescape(s).strip()


def _lines(s: str) -> List[str]:
    return [re.sub(r"\s+", " ", ln).strip() for ln in _text(s).split("\n") if ln.strip()]


CARD_RE = re.compile(
    r'<a href="/business/\?bid=(?P<bid>[^"]+)" class="featuredBusiness(?P<cls>[^"]*)"'
    r'\s+data-filter="(?P<filter>[^"]*)"\s+data-lat="(?P<lat>[^"]*)"\s+data-lng="(?P<lng>[^"]*)">'
    r'(?P<body>.*?)</a>', re.S)
CITY_RE = re.compile(r"^(?P<city>[^,\d]+?),\s*(?P<state>[A-Za-z ]+?)"
                     r"(?:\s+(?P<zip>\d{5})(?:-\d{4})?)?$")
PHONE_RE = re.compile(r"^\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")


def parse_listing(page_html: str) -> List[Dict]:
    out = []
    for m in CARD_RE.finditer(page_html):
        body = m.group("body")
        name = re.search(r'<h2 class="bnameacc">(.*?)</h2>', body, re.S)
        addr = re.search(r'<div class="businessAddress">(.*?)</div>', body, re.S)
        logo = re.search(r"background-image: url\(([^)]*)\)", body)
        rec = {
            "bid": m.group("bid"),
            "name": _text(name.group(1)) if name else "",
            "street": "", "city": "", "state": "", "zip": "", "phone": "",
            "lat": m.group("lat"), "lng": m.group("lng"),
            "logo": logo.group(1) if logo else "",
            "type_tokens": m.group("filter").split("  ")[0].split(),
            "class_tokens": m.group("cls").split(),
        }
        for ln in _lines(addr.group(1)) if addr else []:
            c = CITY_RE.match(ln)
            if c:
                rec.update(city=c.group("city").strip(), state=c.group("state").strip(),
                           zip=c.group("zip") or "")
            elif PHONE_RE.match(ln):
                rec["phone"] = ln
            elif not rec["city"]:
                rec["street"] = (rec["street"] + ", " + ln).strip(", ")
        out.append(rec)
    return out


def has_next_page(page_html: str) -> bool:
    return "Next Page" in page_html


def parse_profile(page_html: str) -> Dict:
    main = page_html[page_html.find('<main'):page_html.find('</main>')]
    rec: Dict = {v: [] for v in PROFILE_GROUPS.values()}
    # Each group: a "headlineSmall" heading followed by prettyArray divs up to the next
    # heading (the description block after the last group has no prettyArray divs).
    parts = re.split(r'<div class="headlineSmall">(.*?)</div>', main, flags=re.S)
    for heading, seg in zip(parts[1::2], parts[2::2]):
        key = PROFILE_GROUPS.get(_text(heading))
        if key:
            rec[key] = [_text(v) for v in
                        re.findall(r'<div class="prettyArray">(.*?)</div>', seg, re.S)]
    t = re.search(r'<h1 class="entry-title">(.*?)</h1>', main, re.S)
    rec["name"] = _text(t.group(1)) if t else ""
    addr = re.search(r'<div class="businessFullAddress">\s*<div>(.*?)</div>', main, re.S)
    rec["address_lines"] = _lines(addr.group(1)) if addr else []
    w = re.search(r'fa-globe-americas"></i>\s*<a href="([^"]*)"', main)
    rec["website"] = htmllib.unescape(w.group(1)).strip() if w else ""
    e = re.search(r'href="mailto:([^"]+)"', main)
    rec["email"] = htmllib.unescape(e.group(1)).strip() if e else ""
    p = re.search(r'href="tel:([^"]+)"', main)
    rec["phone_digits"] = p.group(1) if p else ""
    rec["social"] = {}
    soc = re.search(r'<div class="businessSocial">(.*?)</div>', main, re.S)
    if soc:
        for href, title in re.findall(r'<a href="([^"]*)"[^>]*title="([^"]*)"', soc.group(1)):
            if href.strip():
                rec["social"][title.lower()] = htmllib.unescape(href).strip()
    d = re.search(r'<div class="entry-content">\s*<div[^>]*>(.*?)</div>', main, re.S)
    rec["description"] = _text(d.group(1)) if d else ""
    return rec


# ---- crawl --------------------------------------------------------------------

def fetch_listing(max_pages: int = 50, log=print) -> List[Dict]:
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        h = _get(LIST_URL.format(page=page))
        cards = parse_listing(h)
        new = [c for c in cards if c["bid"] not in seen]
        seen.update(c["bid"] for c in new)
        out.extend(new)
        log(f"listing page {page}: {len(cards)} cards ({len(out)} total)")
        if not cards or not has_next_page(h):
            break
        time.sleep(CRAWL_DELAY)
    return out


def load_cache(path: str) -> Dict[str, Dict]:
    cache = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    r = json.loads(ln)
                    cache[r["bid"]] = r
    return cache


def fetch_profiles(bids: Iterable[str], cache_path: str, log=print) -> Dict[str, Dict]:
    cache = load_cache(cache_path)
    todo = [b for b in bids if b not in cache]
    log(f"profiles: {len(cache)} cached, {len(todo)} to fetch")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "a", encoding="utf-8") as f:
        for i, bid in enumerate(todo, 1):
            try:
                rec = parse_profile(_get(PROFILE_URL.format(bid=bid)))
                rec["bid"] = bid
            except Exception as ex:  # keep going; failures are retried next run
                log(f"  FAIL {bid}: {ex}")
                time.sleep(CRAWL_DELAY)
                continue
            cache[bid] = rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0:
                log(f"  {i}/{len(todo)} profiles fetched")
            time.sleep(CRAWL_DELAY)
    return cache


# ---- mapping to the Phase 2 schema ----------------------------------------------

_TYPE_ORDER = [t for t, _ in TYPE_CATEGORIES]
_TYPE_LABEL = dict(TYPE_CATEGORIES)
# "4895 E. 41st ave, Denver, CO, Colorado 80216" - a whole address typed into line 1.
_COMBINED = re.compile(r"^(?P<street>[^,]*\d[^,]*),\s*(?P<city>[A-Za-z .'-]+?),\s*(?:CO|Colorado)\b"
                       r"[^\d]*(?P<zip>\d{5})?")


# "Farmers' Market" means a recurring gathering of several vendors (maintainer, 2026-10-04).
# Colorado Proud's "Farmers Market" business type is also ticked by members who *sell at*
# markets (salsa makers, ranches, a bird-seed company), so it only counts for a member
# that is itself a market: its name says so, or it's named below. Organizers count too,
# since dedup merges them into the market they run.
_MARKET_NAME = re.compile(r"\b(market|marketplace|mercado|mercadillo|bazaar)s?\b", re.I)
MARKET_ORGANIZERS = {
    "Grateful Garden LLC",            # runs the Green Valley Ranch NE Denver Farmers Market
    "Rocky Mountain Events, LLC.",    # runs the Breckenridge Sunday Market
    "Wildcraft Farmers Markets",
}
NOT_MARKETS = {
    "Young's Market & Garden Center",  # a garden center that sells produce
    "The Farmers Market, LLC",         # an online store (FarmersMarket.store)
}
# Members whose only in-scope type was "Farmers Market" but who are a place to visit.
NON_MARKET_CATEGORY = {
    "Young's Market & Garden Center": "Garden Center / Greenhouse",
    "the LOCAL": "Grocery Store",      # Parker local-goods shop run by the Parker market's owners
}


def is_market(name: str) -> bool:
    name = (name or "").strip()
    if name in NOT_MARKETS:
        return False
    return name in MARKET_ORGANIZERS or bool(_MARKET_NAME.search(name))


def categories_for(types: List[str], name: str = "") -> List[str]:
    out = []
    for t in sorted((t for t in types if t in _TYPE_LABEL), key=_TYPE_ORDER.index):
        if t == "Farmers Market" and not is_market(name):
            continue
        if _TYPE_LABEL[t] not in out:
            out.append(_TYPE_LABEL[t])
    if not out and "Farmers Market" in types and name.strip() in NON_MARKET_CATEGORY:
        out.append(NON_MARKET_CATEGORY[name.strip()])
    return out


def to_market(card: Dict, prof: Dict) -> Optional[Market]:
    """One listing card + its profile -> Market, or None when out of scope."""
    if card["bid"] in EXCLUDE_BIDS:
        return None
    if card.get("state") and card["state"].strip().lower() not in ("colorado", "co"):
        return None
    cats = categories_for(prof.get("business_types", []), card["name"] or prof.get("name", ""))
    if not cats:
        return None
    m = Market(category=", ".join(cats), source=SOURCE, source_id=card["bid"])
    m.set("business_name", card["name"] or prof.get("name", ""), SOURCE)

    street, city, zp = card.get("street", ""), card.get("city", ""), card.get("zip", "")
    if not city:
        c = _COMBINED.match(street)
        if c:
            street, city, zp = c.group("street"), c.group("city"), c.group("zip") or ""
    lat = lng = None
    if PLACEHOLDER_STREET.match(street):
        street = city = zp = ""      # placeholder address; its coordinates are too
    else:
        try:
            lat, lng = float(card["lat"]), float(card["lng"])
        except (TypeError, ValueError, KeyError):
            pass
    m.set("address", street, SOURCE)
    m.set("city", city, SOURCE)
    m.set("zip", zipcode(zp), SOURCE)
    if lat is not None and in_colorado(lat, lng):
        m.latitude, m.longitude, m.geo_source = lat, lng, "source"

    m.set("phone", phone(card.get("phone") or prof.get("phone_digits", "")), SOURCE)
    m.set("website", website_url(prof.get("website", "")), SOURCE)
    social = prof.get("social", {})
    m.set("facebook", facebook_url(social.get("facebook", "")), SOURCE)
    m.set("instagram", instagram_url(social.get("instagram", "")), SOURCE)
    m.set("products", ", ".join(prof.get("products", [])), SOURCE)
    attrs = set(prof.get("product_attributes", [])) | set(prof.get("business_attributes", []))
    if "Organic (Certified)" in attrs:
        m.set("certified_organic", "Yes", SOURCE)
    if "Call For Hours" in attrs:
        m.set("call_first", "Yes", SOURCE)
    if "EBT / SNAP" in prof.get("payment_methods", []):
        m.set("snap", "Yes", SOURCE)     # stated; absence is not a "No"
    m.set("notes", prof.get("description", ""), SOURCE)
    return m


def fetch(log=print) -> List[Market]:
    """Network: listing + new profiles -> full reports + in-scope Market records."""
    if os.environ.get("CPF_REFRESH", "").strip().lower() in ("1", "true", "yes") \
            and os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
    listing = fetch_listing(log=log)
    profiles = fetch_profiles([c["bid"] for c in listing], CACHE_PATH, log=log)
    missing = [c["bid"] for c in listing if c["bid"] not in profiles]
    if missing:  # don't snapshot a partial crawl as if those businesses were gone
        raise RuntimeError(f"{len(missing)} profiles failed to fetch; re-run to retry")
    write_reports(report_rows(listing, profiles), log=log)
    return [m for m in (to_market(c, profiles[c["bid"]]) for c in listing) if m]


# ---- full-membership reports (every type, in scope or not) ------------------------

REPORT_COLS = ["bid", "name", "in_scope", "site_categories", "business_types", "products",
               "product_attributes", "business_attributes", "payment_methods", "street",
               "city", "state", "zip", "lat", "lng", "phone", "website", "facebook",
               "instagram", "other_social", "description", "logo", "profile_url"]


def report_rows(listing: List[Dict], profiles: Dict[str, Dict]) -> List[Dict]:
    rows = []
    for L in listing:
        P = profiles.get(L["bid"], {})
        soc = dict(P.get("social", {}))
        m = to_market(L, P) if P else None
        row = {k: L.get(k, "") for k in ("bid", "name", "street", "city", "state", "zip",
                                         "lat", "lng", "phone", "logo")}
        for k in PROFILE_GROUPS.values():
            row[k] = " | ".join(P.get(k, []))
        row.update(
            in_scope="yes" if m else "no", site_categories=m.category if m else "",
            website=P.get("website", ""),
            facebook=soc.pop("facebook", ""), instagram=soc.pop("instagram", ""),
            other_social=" | ".join(f"{k}: {v}" for k, v in soc.items()),
            description=P.get("description", ""),
            profile_url=PROFILE_URL.format(bid=L["bid"]),
        )
        rows.append(row)
    return rows


def write_reports(rows: List[Dict], out_dir: str = REPORT_DIR, log=print) -> None:
    import csv
    from collections import Counter
    os.makedirs(out_dir, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["name"].lower(), r["bid"]))
    wide = os.path.join(out_dir, "colorado_proud_finder_raw.csv")
    with open(wide, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    counts: Counter = Counter()
    with open(os.path.join(out_dir, "colorado_proud_finder_by_category.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["business_type", "site_category", "bid", "name", "city", "zip",
                    "website", "profile_url"])
        for r in rows:
            for t in [t for t in r["business_types"].split(" | ") if t] or ["(none)"]:
                counts[t] += 1
                w.writerow([t, _TYPE_LABEL.get(t, ""), r["bid"], r["name"], r["city"],
                            r["zip"], r["website"], r["profile_url"]])
    with open(os.path.join(out_dir, "category_counts.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["business_type", "site_category", "count"])
        w.writerows((t, _TYPE_LABEL.get(t, ""), n) for t, n in counts.most_common())
    log(f"  {len(rows)} members ({sum(r['in_scope'] == 'yes' for r in rows)} in scope), "
        f"{len(counts)} types -> {out_dir}")
