#!/usr/bin/env python3
"""Assemble a Food Web release from the last build: the public directory plus a manifest.

  python scripts/scrape/build.py          # snapshots + inputs -> .cache/build/
  python scripts/make_release.py --version v2026.10.1 --out release/

Writes, in --out:
  directory.csv     the public flat directory: one row per listing, the 23 My Maps columns that apps already
                    read, with the release rules applied (closed businesses left out, hidden addresses
                    withheld, descriptions not included, emails only if the business lists them)
  csa.json          confirmed CSAs (season, sign-up link, pickup sites, delivery), facts only
  colorado-farm-trail.json   the statewide app export for the Colorado Farm Trail (format: docs/EXPORTS.md): visits,
                    hours, sales channels and producer detail, with the release rules applied
  tables.zip        the canonical tables (producers, markets, outlets, locations and the link tables)
  places.json       Census place and ZIP centre points, for "near a town or ZIP" searches (public domain)
  supply-network-nodes.csv, supply-network-edges.csv   who supplies which restaurant or store, with sources
  MANIFEST.json     version, date, record counts, per-source counts, the sha256 of each file, and the schema
                    version, so an app can pin a release and check it
  RELEASE.md        human-readable notes

Apps pin a release (a tag such as v2026.10.1 and its sha256) and read directory.csv; they never run the
pipeline. See docs/RELEASES.md.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scrape import contact_policy as cp  # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, ".."))
BUILD = os.path.join(REPO, ".cache", "build")
FORMAT_VERSION = 1
PLACES = os.path.join(REPO, "inputs", "places", "co_places.json")
TABLES = os.path.join(REPO, "data", "colorado")
SUPPLY = os.path.join(REPO, "inputs", "supply-network")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def nkey(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower().replace("’", "'").replace("�", "'").replace("'", "")).strip()


def attach_ids(rows, export):
    """Add a `Food Web ID` column: the stable ID of the producer, market or outlet each listing is, so an app can
    join the flat directory to the export. A name that appears once gets its record; a repeated name is settled by
    town, then by distance to one of the record's places; anything still ambiguous is left blank."""
    recs = {}
    for kind in ("producers", "markets", "outlets", "access_points"):
        for e in export.get(kind, []):
            locs = e.get("locations") or ([e["location"]] if e.get("location") else [])
            recs.setdefault(nkey(e["name"]), []).append((e["id"], locs))
    for r in rows:
        cands = recs.get(nkey(r["Business Name"]), [])
        pick = cands[0][0] if len(cands) == 1 else ""
        if len(cands) > 1:
            by_town = [c for c in cands if any(nkey(l.get("city")) == nkey(r["City"]) and r["City"] for l in c[1])]
            if len(by_town) == 1:
                pick = by_town[0][0]
            elif r["Latitude"] and r["Longitude"]:
                lat, lon = float(r["Latitude"]), float(r["Longitude"])
                near = [c for c in cands if any(l.get("lat") is not None and abs(l["lat"] - lat) < 0.01
                                                and abs(l["lon"] - lon) < 0.01 for l in c[1])]
                if len(near) == 1:
                    pick = near[0][0]
        if not pick:      # the same business as a producer and an outlet (a farm with a shop): the producer
            prod = [c for c in cands if c[0].startswith("co-p-")]
            if len(prod) == 1:
                pick = prod[0][0]
        r["Food Web ID"] = pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="release tag, e.g. v2026.10.1")
    ap.add_argument("--out", default=os.path.join(REPO, "release"))
    a = ap.parse_args()
    if not re.match(r"^v\d{4}\.\d{2}\.\d+$", a.version):
        sys.exit("version must look like v2026.10.1")

    src = os.path.join(BUILD, "co_farmers_markets_all_mymaps.csv")
    raw = os.path.join(BUILD, "co_farmers_markets_all_raw.csv")
    if not os.path.exists(src):
        sys.exit("run scripts/scrape/build.py first")
    rows = read(src)
    table = cp.Table()

    # Release rules, enforced again here so a release can never carry a stray address or description.
    for r in rows:
        r["Notes"] = ""
        kept = [e for e in cp.split_emails(r["Email"]) if cp.publishable(e, r["Website"], table)]
        r["Email"] = "; ".join(kept)

    os.makedirs(a.out, exist_ok=True)
    # The statewide export for the Colorado Farm Trail, built from the same tables (docs/EXPORTS.md). Unconfirmed
    # farm homes are not pinned: many are private residences.
    export_path = os.path.join(a.out, "colorado-farm-trail.json")
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "export_app.py"), "--tables", TABLES, "--out", export_path,
                    "--release", a.version.lstrip("v"), "--statewide", "--unconfirmed-home-pins", "hide",
                    "--config", os.path.join(REPO, "exports", "colorado-farm-trail.config.json")],
                   check=True, stdout=subprocess.DEVNULL)
    with open(export_path, encoding="utf-8") as fh:
        attach_ids(rows, json.load(fh))
    out_csv = os.path.join(a.out, "directory.csv")
    with open(out_csv, "w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    import shutil
    csa = os.path.join(BUILD, "csa.json")
    if not os.path.exists(csa):
        sys.exit("run scripts/csa/build_csa.py first")
    assets = {"csa.json": csa, "places.json": PLACES,
              "supply-network-nodes.csv": os.path.join(SUPPLY, "nodes.csv"),
              "supply-network-edges.csv": os.path.join(SUPPLY, "edges.csv")}
    for name, path in assets.items():
        shutil.copyfile(path, os.path.join(a.out, name))

    import zipfile
    tables_zip = os.path.join(a.out, "tables.zip")
    with zipfile.ZipFile(tables_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(TABLES)):
            if fn.endswith(".csv"):
                z.write(os.path.join(TABLES, fn), fn)
    assets["tables.zip"] = tables_zip
    assets["colorado-farm-trail.json"] = export_path

    by_source = {}
    for r in read(raw):
        for s in (r.get("Source") or "").split("+"):
            if s:
                by_source[s] = by_source.get(s, 0) + 1
    manifest = {
        "name": "Colorado Open Food Web directory",
        "version": a.version,
        "format_version": FORMAT_VERSION,
        "released": dt.date.today().isoformat(),
        "license": "CC BY 4.0",
        "attribution": "Colorado Open Food Web, https://github.com/open-food-web/colorado-open-food-web",
        "files": {"directory.csv": {"rows": len(rows), "sha256": sha256(out_csv),
                                    "columns": list(rows[0].keys())},
                  **{n: {"sha256": sha256(os.path.join(a.out, n))} for n in assets}},
        "counts": {"listings": len(rows,),
                   "with_email": sum(1 for r in rows if r["Email"]),
                   "with_website": sum(1 for r in rows if r["Website"]),
                   "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1]))},
        "rules": ["facts only: no descriptions (the Notes column is empty)",
                  "closed businesses are not included",
                  "hidden addresses are withheld",
                  "an email appears only if the business lists it on its own website or Facebook page"],
    }
    with open(os.path.join(a.out, "MANIFEST.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(a.out, "RELEASE.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"""# Colorado Open Food Web {a.version}

Released {manifest['released']}. Data CC BY 4.0: credit "Colorado Open Food Web".

- `directory.csv`: {len(rows)} listings ({manifest['counts']['with_email']} with a confirmed email,
  {manifest['counts']['with_website']} with a website).
- `colorado-farm-trail.json` (statewide app export), `tables.zip` (the canonical tables), `csa.json`, `places.json`, `supply-network-nodes.csv`, `supply-network-edges.csv`.
- `MANIFEST.json`: counts, sources, and the sha256 of each file.

Rules applied: facts only (no descriptions), closed businesses and hidden addresses left out, emails only
when the business lists them itself. Apps should pin this version and verify the sha256.
""")
    print(f"{a.version}: {len(rows)} listings -> {a.out}")
    print("sha256", manifest["files"]["directory.csv"]["sha256"])


if __name__ == "__main__":
    main()
