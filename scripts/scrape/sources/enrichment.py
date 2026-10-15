"""Source: per-market official-website enrichment (produced by Sonnet subagents).

Each subagent enriches one market from its own official site (+ search fallback) and
writes a JSON result to data/enrichment/results/<id>.json. This module loads those
results and turns them into Market records tagged source="official-site".

In build.py this is folded FIRST, so per the field-value priority rule a clearly-stated
official-site value wins over every directory. Records are keyed by the same name+city
as the target rows, so they merge into (not duplicate) the directory records — which
supply coordinates/county the enrichment doesn't carry.
"""
from __future__ import annotations

import json
import os
from typing import List

from ..normalize import clean_url, facebook_url, instagram_url, phone, yesno
from ..schema import Market

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
# PHASE 2 enrichment inputs (collected by the Sonnet subagents) live under source-data/phase2.
ENRICH_DIR = os.path.join(REPO, "inputs", "enrichment")
RESULTS_DIR = os.path.join(ENRICH_DIR, "results")
TARGETS = os.path.join(ENRICH_DIR, "targets.json")
SOURCE = "official-site"

# result column -> Market attribute
COL_ATTR = {
    "Business Name": "business_name", "Address": "address", "City": "city",
    "Zip": "zip", "Phone": "phone", "Website": "website", "Email": "email",
    "Facebook": "facebook", "Instagram": "instagram", "Hours": "hours",
    "Months Open": "months_open", "Products": "products",
    "Certified Organic": "certified_organic", "SNAP": "snap",
    "ADA Accessible": "ada_accessible", "Notes": "notes",
}
NORMALIZE = {"phone": phone, "website": clean_url, "facebook": facebook_url,
             "instagram": instagram_url, "snap": yesno, "certified_organic": yesno,
             "ada_accessible": yesno}


def _targets_by_id() -> dict:
    if not os.path.exists(TARGETS):
        return {}
    return {t["id"]: t for t in json.load(open(TARGETS, encoding="utf-8"))}


def parse(results: List[dict], targets_by_id: dict) -> List[Market]:
    out = []
    for res in results:
        tid = res.get("id")
        t = targets_by_id.get(tid, {})
        name = res.get("name") or t.get("name", "")
        city = res.get("city") or t.get("city", "")
        if not name:
            continue
        m = Market(source=SOURCE, category="")  # enrichment states no category
        m.business_name, m.city = name, city  # merge key (not counted as provenance)
        fields = res.get("fields", {})
        for col, attr in COL_ATTR.items():
            if attr in ("business_name", "city"):
                continue
            cell = fields.get(col)
            val = cell.get("value") if isinstance(cell, dict) else cell
            if attr in NORMALIZE and val:
                val = NORMALIZE[attr](val)
            # label provenance by the field's own source url when available
            label = SOURCE
            if isinstance(cell, dict) and cell.get("source_url"):
                label = f"{SOURCE}:{cell['source_url']}"
            m.set(attr, val, label)
        out.append(m)
    return out


def load_results() -> List[dict]:
    if not os.path.isdir(RESULTS_DIR):
        return []
    res = []
    for fn in sorted(os.listdir(RESULTS_DIR)):
        if fn.endswith(".json"):
            try:
                res.append(json.load(open(os.path.join(RESULTS_DIR, fn), encoding="utf-8")))
            except (ValueError, OSError):
                pass
    return res


def fetch() -> List[Market]:
    return parse(load_results(), _targets_by_id())
