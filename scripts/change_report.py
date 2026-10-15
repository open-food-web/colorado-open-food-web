#!/usr/bin/env python3
"""Describe what changed between two builds of a county's tables, in plain language.

This is the monthly change report in miniature: partners get it with every release, and a pull
request's description is built from it. It reads two table folders and, optionally, the two
app exports, and prints Markdown.

Usage:
  python scripts/change_report.py --before <old tables dir> --after data/colorado \
      [--export-before old.json --export-after exports/chaffee-provides.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

FIELDS = ["address", "city", "zip", "phone", "email", "website", "facebook", "instagram", "hours_text",
          "categories", "sales_channels", "status"]


def read(d, name):
    path = os.path.join(d, name + ".csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load(d):
    loc = {r["location_id"]: r for r in read(d, "locations")}
    prod = {r["producer_id"]: r for r in read(d, "producers")}
    pls = {}
    for r in read(d, "producer_locations"):
        pls.setdefault(r["producer_id"], []).append(r)
    for pid, p in prod.items():
        h = next((x for x in pls.get(pid, []) if x["role"] == "home_base"), None)
        L = loc.get(h["location_id"]) if h else None
        for k in ("address", "city", "zip"):
            p[k] = (L or {}).get(k, "")
    mname = {r["location_id"]: r["name"] for r in read(d, "markets")}
    for lid, n in mname.items():
        if lid in loc:
            loc[lid] = dict(loc[lid], name=n)
    return {"producers": prod, "locations": loc, "pls": pls,
            "markets": {r["market_id"]: r for r in read(d, "markets")},
            "access": {r["access_point_id"]: r for r in read(d, "access_points")}}


def where(b, pid):
    out = []
    for x in b["pls"].get(pid, []):
        L = b["locations"].get(x["location_id"], {})
        label = L.get("name") or ", ".join(v for v in (L.get("address"), L.get("city")) if v) or x["location_id"]
        when = x["hours_text"] or x["days"]
        out.append("%s: %s%s%s" % (x["role"].replace("_", " "), label, " (hidden address)" if L.get("hide_address") == "true" else "",
                                   " — " + when if when else ""))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--export-before")
    ap.add_argument("--export-after")
    a = ap.parse_args()
    B, A = load(a.before), load(a.after)
    lines = []

    bp, ap_ = B["producers"], A["producers"]
    added = [ap_[i] for i in ap_ if i not in bp]
    gone = [bp[i] for i in bp if i not in ap_]
    lines.append("### Counts")
    lines.append("")
    lines.append("| | Before | After |")
    lines.append("|---|---|---|")
    lines.append("| Producers | %d | %d |" % (len(bp), len(ap_)))
    lines.append("| Locations | %d | %d |" % (len(B["locations"]), len(A["locations"])))
    lines.append("| Markets | %d | %d |" % (len(B["markets"]), len(A["markets"])))
    lines.append("| Food access points | %d | %d |" % (len(B["access"]), len(A["access"])))
    if a.export_before and a.export_after:
        xb, xa = json.load(open(a.export_before, encoding="utf-8")), json.load(open(a.export_after, encoding="utf-8"))
        lines.append("| Producers on the Chaffee Provides site | %d | %d |" % (len(xb["producers"]), len(xa["producers"])))
        lines.append("| Map pins on the Chaffee Provides site | %d | %d |" % (
            xb["export"]["counts"]["pins"], xa["export"]["counts"]["pins"]))
    lines.append("")

    if added:
        lines += ["### Added", ""]
        for p in sorted(added, key=lambda x: x["name"]):
            lines.append("- **%s** (%s). %s" % (p["name"], p["kind"], "; ".join(where(A, p["producer_id"])) or "no location"))
        lines.append("")
    if gone:
        lines += ["### Removed", ""]
        for p in sorted(gone, key=lambda x: x["name"]):
            lines.append("- **%s**" % p["name"])
        lines.append("")

    changed = []
    for pid in ap_:
        if pid not in bp:
            continue
        diffs = [(f, bp[pid].get(f, ""), ap_[pid].get(f, "")) for f in FIELDS if bp[pid].get(f, "") != ap_[pid].get(f, "")]
        wb, wa = where(B, pid), where(A, pid)
        if diffs or wb != wa:
            changed.append((ap_[pid]["name"], diffs, wb, wa))
    if changed:
        lines += ["### Changed", ""]
        for name, diffs, wb, wa in sorted(changed):
            lines.append("- **%s**" % name)
            for f, o, n in diffs:
                lines.append("  - %s: %s → %s" % (f.replace("_", " "), o or "(blank)", n or "(blank)"))
            for w in wa:
                if w not in wb:
                    lines.append("  - new place to buy — %s" % w)
            for w in wb:
                if w not in wa:
                    lines.append("  - no longer listed — %s" % w)
        lines.append("")

    m_added = [A["markets"][i]["name"] for i in A["markets"] if i not in B["markets"]]
    f_added = [A["access"][i]["name"] for i in A["access"] if i not in B["access"]]
    if m_added or f_added:
        lines += ["### Other additions", ""] + ["- %s" % n for n in sorted(m_added + f_added)] + [""]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
