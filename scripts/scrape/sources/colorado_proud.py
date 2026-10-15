"""Source: Colorado Proud / Farm Fresh Directory (ArcGIS Feature Service).

This is the same public feature service the repo already uses (see DATA.md /
scripts/fetch_farm_data.py). It is the highest-confidence source per record, so in
the merge it wins field conflicts. Here we keep only records whose Operation type
includes a farmers market, and map them into the normalized Market schema.
"""
from __future__ import annotations

import json
import urllib.request
from typing import List

from ..normalize import clean_url, facebook_url, instagram_url, phone, pipes, yesno, zipcode
from ..schema import Market
from ..useragent import USER_AGENT

FS = ("https://services3.arcgis.com/DgjqnJA1rgO92Soi/arcgis/rest/services/"
      "Farm_Fresh_Directory/FeatureServer/0/query")
QUERY = "?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=json"
SOURCE = "colorado_proud"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PROD_FIELDS = [
    "Produce Categories 1", "Produce Categories 2", "Produce Categories 3",
    "Produce Categories (other)", "Meat Categories", "Game", "Fish", "Meat (other)",
    "Miscellaneous 1", "Miscellaneous 2", "Miscellaneous (Other)", "Wines",
]


def fetch_raw(url: str = FS + QUERY) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def parse(data: dict) -> List[Market]:
    """Map an ArcGIS query response to Market records (farmers markets only)."""
    alias_to_name = {f.get("alias", f["name"]): f["name"] for f in data["fields"]}

    def g(ft, label):
        return (ft["attributes"].get(alias_to_name.get(label, ""), "") or "").strip()

    out: List[Market] = []
    for ft in data.get("features", []):
        optype = g(ft, "Operation type")
        if "farmers" not in optype.lower() or "market" not in optype.lower():
            continue  # markets only

        addr = g(ft, "Address Line 1")
        line2 = g(ft, "Address Line 2")
        if line2:
            addr = (addr + " " + line2).strip()

        hours = "; ".join(
            f"{d[:3]}: {g(ft, 'Hours on ' + d)}" for d in DAYS if g(ft, "Hours on " + d)
        )
        products = ", ".join(
            v for v in (pipes(g(ft, f)) for f in PROD_FIELDS) if v
        )

        m = Market(source=SOURCE)
        m.set("business_name", g(ft, "Business Name"), SOURCE)
        m.set("address", addr, SOURCE)
        m.set("city", g(ft, "City"), SOURCE)
        m.set("county", g(ft, "County"), SOURCE)
        m.set("zip", zipcode(g(ft, "Zip")), SOURCE)
        m.set("phone", phone(g(ft, "Telephone Number")), SOURCE)
        m.set("call_first", yesno(g(ft, "Should the customer call first?")), SOURCE)
        m.set("website", clean_url(g(ft, "Website")), SOURCE)
        m.set("email", g(ft, "Email Address"), SOURCE)
        m.set("facebook", facebook_url(g(ft, "Facebook")), SOURCE)
        m.set("instagram", instagram_url(g(ft, "Instagram")), SOURCE)
        m.set("hours", hours, SOURCE)
        m.set("months_open", pipes(g(ft, "Months open for business")), SOURCE)
        m.set("products", products, SOURCE)
        m.set("certified_organic", yesno(g(ft, "Certified organic")), SOURCE)
        m.set("snap", yesno(g(ft, "SNAP accepted")), SOURCE)
        m.set("ada_accessible", yesno(g(ft, "ADA accessible")), SOURCE)
        m.set("notes", g(ft, "Additional information"), SOURCE)

        geom = ft.get("geometry") or {}
        if geom.get("y") and geom.get("x"):
            m.latitude, m.longitude = float(geom["y"]), float(geom["x"])
            m.geo_source = "source"
        out.append(m)
    return out


def fetch() -> List[Market]:
    return parse(fetch_raw())
