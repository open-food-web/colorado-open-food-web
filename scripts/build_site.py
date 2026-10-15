#!/usr/bin/env python3
"""Prepare the data the project site shows (site/data/) from a release and the supply-network inputs.

  python scripts/build_site.py --release-dir release        # a folder with the release files
  (the Pages workflow downloads the latest release into that folder first)

Writes site/data/MANIFEST.json (copied) and site/data/web.json: the "food web" as nodes (businesses) and
edges (who supplies whom, with the source of each claim), joined to the directory for each business's website.
"""
import argparse
import csv
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(REPO, "site", "data")


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def key(name, city=""):
    return (re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip(), (city or "").lower().strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release-dir", default=os.path.join(REPO, "release"))
    a = ap.parse_args()
    rd = a.release_dir
    os.makedirs(OUT, exist_ok=True)
    shutil.copyfile(os.path.join(rd, "MANIFEST.json"), os.path.join(OUT, "MANIFEST.json"))

    sites = {}
    for r in rows(os.path.join(rd, "directory.csv")):
        w = (r["Website"] or "").strip()
        if w:
            sites[key(r["Business Name"], r["City"])] = w
            sites.setdefault(key(r["Business Name"]), w)

    nodes_in = rows(os.path.join(rd, "supply-network-nodes.csv"))
    edges_in = rows(os.path.join(rd, "supply-network-edges.csv"))
    idx, nodes = {}, []
    for n in nodes_in:
        idx[n["name"]] = len(nodes)
        site = sites.get(key(n["name"], n["city"])) or sites.get(key(n["name"])) or ""
        nodes.append({"id": len(nodes), "name": n["name"], "type": n["type"], "city": n["city"], "site": site})
    edges = []
    for e in edges_in:
        s, t = idx.get(e["supplier"]), idx.get(e["buyer"])
        if s is None or t is None:
            continue
        edges.append({"s": s, "t": t, "src": e["source"], "ok": (e.get("status") or "") != "unconfirmed",
                      "conf": e.get("confidence") or ""})
    with open(os.path.join(OUT, "web.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"nodes": nodes, "edges": edges}, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"web.json: {len(nodes)} businesses, {len(edges)} connections")


if __name__ == "__main__":
    main()
