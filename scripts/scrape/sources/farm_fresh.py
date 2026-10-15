"""Source: the live Phase 1 map data — Colorado Proud Farm Fresh, as maintained.

`data-compiled/farm_fresh_directory_mymaps.csv` is what the live site is built from
(`scripts/fetch_farm_data.py` pulls Colorado Proud; hand fixes are made on top of it:
corrected hours, multi-category labels and CATEGORY_CORRECTIONS, Wholesale Grower
"Where to Get It" lists). Phase 2's own Colorado Proud pull keeps only farmers'
markets, so without this source a cutover would drop ~100 live farms.

Reading the maintained file (rather than re-pulling Colorado Proud) carries every
hand fix into Phase 2 and keeps the build offline. It's refreshed the Phase 1 way:
re-run fetch_farm_data.py / edit the CSV, then rebuild.
"""
from __future__ import annotations

import csv
import os
from typing import List

from ..normalize import clean_url, facebook_url, instagram_url, yesno
from ..schema import Market

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LIVE_CSV = os.path.join(REPO, "inputs", "farm_fresh_legacy.csv")
SOURCE = "colorado_proud_farm_fresh"


def parse(rows) -> List[Market]:
    out: List[Market] = []
    for r in rows:
        g = lambda k: (r.get(k) or "").strip()
        name = g("Business Name")
        if not name:
            continue
        m = Market(source=SOURCE, category=g("Category"))
        m.set("business_name", name, SOURCE)
        m.set("address", g("Address"), SOURCE)
        m.set("city", g("City"), SOURCE)
        m.set("county", g("County"), SOURCE)
        m.set("zip", g("Zip"), SOURCE)
        m.set("phone", g("Phone"), SOURCE)
        m.call_first = yesno(g("Call first?"))
        m.set("website", clean_url(g("Website")), SOURCE)
        m.set("email", g("Email"), SOURCE)
        m.set("facebook", facebook_url(g("Facebook")), SOURCE)
        m.set("instagram", instagram_url(g("Instagram")), SOURCE)
        m.set("hours", g("Hours"), SOURCE)
        m.set("months_open", g("Months Open"), SOURCE)
        m.set("products", g("Products"), SOURCE)
        m.set("certified_organic", yesno(g("Certified Organic")), SOURCE)
        m.set("snap", yesno(g("SNAP")), SOURCE)
        m.set("ada_accessible", yesno(g("ADA Accessible")), SOURCE)
        m.set("notes", g("Notes"), SOURCE)
        m.set("where_to_get", g("Where to Get It"), SOURCE)
        try:
            m.latitude, m.longitude = float(g("Latitude")), float(g("Longitude"))
            m.geo_source = "source"
        except ValueError:
            pass
        out.append(m)
    return out


def fetch(path: str = LIVE_CSV) -> List[Market]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return parse(csv.DictReader(fh))
