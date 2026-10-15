"""Validate CSA enrichment results and build the finder dataset.

Reads  inputs/csa/targets.json + results/*.json   (or --src)
Writes .cache/build/csa.json  (only farms with offers_csa == true)
       .cache/build/csa_coverage.csv (all targets, one row each, for review)
Run:   python scripts/csa/build_csa.py [--src DIR] [--out DIR]
"""
import os
import csv, json, re, sys
from pathlib import Path

import argparse

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "inputs" / "csa"            # facts-only research (the full version, with quoted evidence, is in the sources repo)
OUT = ROOT / ".cache" / "build"
STATUSES = {"open", "waitlist", "full", "opens_later", "closed_season", "unknown"}
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def problems(r):
    p = []
    if r.get("offers_csa") not in (True, False, "unknown"):
        p.append("offers_csa invalid")
    if r.get("csa_status") not in STATUSES:
        p.append("csa_status invalid")
    for k in ("season_start", "season_end", "signup_opens"):
        if r.get(k) and not ISO.match(str(r[k])):
            p.append(f"{k} not ISO")
    if r.get("season_start") and r.get("season_end") and r["season_start"] > r["season_end"]:
        p.append("season_start after season_end")
    if r.get("signup_url") and not str(r["signup_url"]).startswith("http"):
        p.append("signup_url not http(s)")
    if not isinstance(r.get("pickup_sites") or [], list):
        p.append("pickup_sites not a list")
    return p


def main():
    global SRC, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    SRC, OUT = Path(a.src), Path(a.out)
    targets = json.loads((SRC / "targets.json").read_text(encoding="utf-8"))
    rows, keep, bad, missing = [], [], 0, []
    for t in targets:
        f = SRC / "results" / f"{t['id']}.json"
        if not f.exists():
            missing.append(t["id"]); continue
        r = json.loads(f.read_text(encoding="utf-8"))
        pr = problems(r)
        if pr:
            bad += 1; print("PROBLEM", t["id"], pr)
        pk = r.get("pickup_sites") or []
        dl = r.get("delivery") or {}
        rows.append({
            "id": t["id"], "name": t["name"], "city": t["city"], "tagged": t["tagged"],
            "offers_csa": r.get("offers_csa"), "status": r.get("csa_status"),
            "season_start": r.get("season_start") or "", "season_end": r.get("season_end") or "",
            "season_year": r.get("season_year") or "", "signup_url": r.get("signup_url") or "",
            "pickup_sites": len(pk), "delivery": dl.get("offered"), "price": r.get("price") or "",
            "problems": "; ".join(pr)})
        if r.get("offers_csa") is True:
            keep.append({**r, "lat": t["lat"], "lon": t["lon"], "city": t["city"], "county": t["county"],
                         "address": t["address"], "website": t["website"]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "csa.json").write_text(json.dumps(keep, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(OUT / "csa_coverage.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    n = len(rows)
    c = lambda f: sum(1 for r in rows if f(r))
    print(f"\n{n}/{len(targets)} results read, {len(missing)} missing, {bad} with problems")
    print(f"offers_csa: true={c(lambda r:r['offers_csa'] is True)} false={c(lambda r:r['offers_csa'] is False)} unknown={c(lambda r:r['offers_csa']=='unknown')}")
    t_ = [r for r in rows if r["offers_csa"] is True]
    print(f"of the {len(t_)} confirmed CSAs: season dates={sum(1 for r in t_ if r['season_start'] and r['season_end'])}"
          f"  signup_url={sum(1 for r in t_ if r['signup_url'])}  pickup sites={sum(1 for r in t_ if r['pickup_sites'])}"
          f"  delivery stated={sum(1 for r in t_ if r['delivery'])}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
