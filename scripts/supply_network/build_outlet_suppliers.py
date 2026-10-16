"""Build data/colorado/outlet_suppliers.csv from the supply-network edges.

Matches each edge's supplier to a producer_id and its buyer to an outlet_id by normalized name,
using the city in nodes.csv to break ties. A name that matches nothing, or more than one record,
is never guessed: the edge goes to inputs/supply-network/outlet_suppliers_review.csv instead.

    python scripts/supply_network/build_outlet_suppliers.py
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NET = ROOT / "inputs" / "supply-network"
DATA = ROOT / "data" / "colorado"
OBSERVED_ON = "2026-10-03"  # research date, inputs/supply-network/README.md
FIELDS = ["outlet_id", "producer_id", "featured_item", "basis", "source_url", "source_dated", "observed_on", "status"]
REVIEW_FIELDS = ["side", "name", "city", "reason", "candidates", "supplier", "buyer", "source"]


def norm(s):
    s = re.sub(r"\s*\((?!closed)[^)]*\)", "", s or "")
    s = s.lower().replace("é", "e").replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"^the ", "", s)


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def index(rows, id_field, cities):
    """norm(name) -> list of (id, city)"""
    idx = {}
    for r in rows:
        idx.setdefault(norm(r["name"]), []).append((r[id_field], cities.get(r[id_field], "")))
    return idx


def resolve(idx, name, city):
    """Return (id, reason, candidates). id is set only for a single clear match."""
    cands = idx.get(norm(name), [])
    if not cands:
        return None, "no match", ""
    if len(cands) > 1 and city:
        cands = [c for c in cands if norm(c[1]) == norm(city)] or cands
    if len(cands) == 1:
        return cands[0][0], "", ""
    return None, "ambiguous", ";".join(c[0] for c in cands)


def source_dated(date):
    return date if re.fullmatch(r"\d{4}(-\d{2})?", date or "") else ""


def basis(edge):
    """Whose page is the source? Only stated when the source domain carries one party's name."""
    if edge["confidence"] != "high":
        return "third_party"
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", edge["source"]).split("/")[0]).split(".")[0]
    hits = {w: norm(edge[w]).replace(" ", "") for w in ("supplier", "buyer")}
    s = bool(hits["supplier"]) and (hits["supplier"] in host or host in hits["supplier"])
    b = bool(hits["buyer"]) and (hits["buyer"] in host or host in hits["buyer"])
    if s and not b:
        return "producer_says"
    if b and not s:
        return "outlet_says"
    return ""


def build(edges, nodes, producers, outlets, locations, ploc):
    city = {n["name"]: n["city"] for n in nodes}
    loc_city = {l["location_id"]: l["city"] for l in locations}
    p_city = {}
    for pl in ploc:
        p_city.setdefault(pl["producer_id"], loc_city.get(pl["location_id"], ""))
    o_city = {o["outlet_id"]: loc_city.get(o["location_id"], "") for o in outlets}
    pidx, oidx = index(producers, "producer_id", p_city), index(outlets, "outlet_id", o_city)
    kept, review, seen = [], [], set()
    for e in edges:
        pid, p_reason, p_c = resolve(pidx, e["supplier"], city.get(e["supplier"], ""))
        oid, o_reason, o_c = resolve(oidx, e["buyer"], city.get(e["buyer"], ""))
        for side, name, rid, reason, cands in (("supplier", e["supplier"], pid, p_reason, p_c),
                                               ("buyer", e["buyer"], oid, o_reason, o_c)):
            if not rid:
                review.append({"side": side, "name": name, "city": city.get(name, ""), "reason": reason,
                               "candidates": cands, "supplier": e["supplier"], "buyer": e["buyer"],
                               "source": e["source"]})
        if pid and oid and (oid, pid) not in seen:
            seen.add((oid, pid))
            kept.append({"outlet_id": oid, "producer_id": pid, "featured_item": "", "basis": basis(e),
                         "source_url": e["source"], "source_dated": source_dated(e["date"]),
                         "observed_on": OBSERVED_ON,
                         "status": "unverified" if e["status"] == "unconfirmed" else "current"})
    return kept, review


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    edges = read(NET / "edges.csv")
    producers = read(DATA / "producers.csv")
    outlets = read(DATA / "outlets.csv")
    kept, review = build(edges, read(NET / "nodes.csv"), producers, outlets,
                         read(DATA / "locations.csv"), read(DATA / "producer_locations.csv"))
    write(DATA / "outlet_suppliers.csv", FIELDS, kept)
    write(NET / "outlet_suppliers_review.csv", REVIEW_FIELDS, review)
    print("edges %d, links kept %d, producers matched %d, outlets matched %d, review rows %d" % (
        len(edges), len(kept), len({k["producer_id"] for k in kept}), len({k["outlet_id"] for k in kept}),
        len(review)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
