"""Link producers to the markets they sell at, as structured rows.

Two kinds of evidence, both public and both recorded with their basis:

  vendor_list  a market's own published vendor list names the business (inputs/market_vendor_lists.csv:
               market, town, vendor name, list year, list URL; descriptions are not kept)
  stated_text  the producer's own listing says it sells at a market ("Sells at Montrose Farmers Market ...")

A match is made only when it is unambiguous: one market, one producer. Names that fit several records are left
unlinked rather than guessed. Nothing here copies a description; a row holds IDs, the year, and where the claim
came from.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Tuple

GENERIC = re.compile(r"\b(llc|inc|ltd|co|company|corp|the|and|of|dba|farm|farms|ranch|gardens?|market|markets|farmers?)\b")


def norm(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def loose(s: str) -> str:
    return " ".join(GENERIC.sub(" ", norm(s)).split())


def year_of(label: str) -> Tuple[str, str]:
    """'2026' -> ('2026', ''); '2025-26 winter' -> ('2025', '2025-26 winter'); '' -> ('', '')."""
    m = re.match(r"\s*(\d{4})", label or "")
    if not m:
        return "", ""
    return m.group(1), ("" if (label or "").strip() == m.group(1) else label.strip())


class Linker:
    def __init__(self, markets: List[dict], producers: List[dict], locations: Dict[str, dict]):
        self.markets = markets
        self.locations = locations
        self.by_market_key: Dict[Tuple[str, str], dict] = {}
        self.by_market_name: Dict[str, List[dict]] = defaultdict(list)
        for m in markets:
            city = norm(locations[m["location_id"]]["city"])
            self.by_market_key[(norm(m["name"]), city)] = m
            self.by_market_name[norm(m["name"])].append(m)
        self.prod_exact: Dict[str, List[dict]] = defaultdict(list)
        self.prod_loose: Dict[str, List[dict]] = defaultdict(list)
        for p in producers:
            self.prod_exact[norm(p["name"])].append(p)
            if loose(p["name"]):
                self.prod_loose[loose(p["name"])].append(p)
        self.prod_loc: Dict[str, dict] = {}

    def attach_locations(self, producer_locations: List[dict]):
        for pl in producer_locations:
            self.prod_loc.setdefault(pl["producer_id"], self.locations[pl["location_id"]])

    def market_for(self, name: str, city: str):
        m = self.by_market_key.get((norm(name), norm(city)))
        if m:
            return m
        one = self.by_market_name.get(norm(name), [])
        return one[0] if len(one) == 1 else None

    def producer_for(self, vendor: str, market: dict):
        """-> (producer, basis) or (None, reason)."""
        c = self.prod_exact.get(norm(vendor), [])
        if len(c) == 1:
            return c[0], "exact_name"
        if len(c) > 1:
            return None, "ambiguous"
        key = loose(vendor)
        c = self.prod_loose.get(key, []) if key else []
        if len(c) > 1:
            return None, "ambiguous"
        if len(c) == 1:
            p = c[0]
            loc, mloc = self.prod_loc.get(p["producer_id"], {}), self.locations[market["location_id"]]
            same_place = (loc.get("county_fips") and loc.get("county_fips") == mloc.get("county_fips")) or \
                         (norm(loc.get("city", "")) and norm(loc.get("city", "")) == norm(mloc.get("city", "")))
            if same_place or len(key.split()) >= 2:
                return p, "normalized_name"
        return None, "no_match"

    def from_lists(self, rows: List[dict]):
        links, unmatched = {}, defaultdict(int)
        for r in rows:
            m = self.market_for(r["market"], r["market_city"])
            if not m:
                unmatched["market:" + r["market"]] += 1
                continue
            p, basis = self.producer_for(r["vendor"], m)
            if not p:
                unmatched[basis] += 1
                continue
            yr, label = year_of(r["list_year"])
            key = (m["market_id"], p["producer_id"], yr, label)
            links.setdefault(key, {"market_id": m["market_id"], "producer_id": p["producer_id"], "year": yr,
                                   "season_label": label, "days": "", "season_start": "", "season_end": "",
                                   "status": "listed", "list_source": "vendor list: %s" % m["name"],
                                   "source_url": r["list_url"], "match_basis": basis})
        return list(links.values()), dict(unmatched)

    def from_text(self, producer_texts: Dict[str, str], have: set):
        """Market names a producer's own listing states outright."""
        out = []
        names = sorted(((norm(m["name"]), m) for m in self.markets if len(norm(m["name"]).split()) >= 2),
                       key=lambda t: -len(t[0]))
        for pid, text in producer_texts.items():
            t = " " + norm(text) + " "
            if not t.strip():
                continue
            seen = set()
            for nm, m in names:
                if (" " + nm + " ") in t and m["market_id"] not in seen and (m["market_id"], pid) not in have:
                    if len(self.by_market_name.get(nm, [])) != 1:
                        continue          # the same name for several markets: not unambiguous
                    seen.add(m["market_id"])
                    out.append({"market_id": m["market_id"], "producer_id": pid, "year": "", "season_label": "",
                                "days": "", "season_start": "", "season_end": "", "status": "listed",
                                "list_source": "stated in the producer's listing", "source_url": "",
                                "match_basis": "stated_text"})
        return out
