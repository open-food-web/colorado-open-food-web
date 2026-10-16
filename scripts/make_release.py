#!/usr/bin/env python3
"""Assemble a Food Web release from the last build: the public directory plus a manifest.

  python scripts/scrape/build.py          # snapshots + inputs -> .cache/build/
  python scripts/make_release.py --version v2026.10.1 --out release/

Writes, in --out:
  directory.csv     the public flat directory: one row per listing, the 23 My Maps columns that apps already
                    read, with the release rules applied (closed businesses left out, hidden addresses
                    withheld, descriptions not included, emails only if the business lists them)
  csa.json          confirmed CSAs (season, sign-up link, pickup sites, delivery), facts only
  tables.zip        the canonical tables (producers, markets, outlets, locations and the link tables)
  open-food-web.json  the statewide app export (docs/EXPORTS.md): the only file an app needs; it filters it to its
                    own scope (county, categories, outlet kinds, pins) when it syncs
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

    # The one app export: statewide, unscoped, release rules applied (docs/EXPORTS.md). Apps pin this file and
    # apply their own scope (county, categories, pins) on their side.
    import subprocess
    app_json = os.path.join(a.out, "open-food-web.json")
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "export_app.py"), "--tables", TABLES, "--out", app_json,
                    "--release", a.version, "--statewide", "--all-outlet-kinds", "--unconfirmed-home-pins", "hide",
                    "--generated", dt.date.today().isoformat()], check=True, stdout=subprocess.DEVNULL)
    assets["open-food-web.json"] = app_json

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
- `open-food-web.json` (the statewide app export; apps filter it to their own scope), `tables.zip` (the canonical tables), `csa.json`, `places.json`, `supply-network-nodes.csv`, `supply-network-edges.csv`.
- `MANIFEST.json`: counts, sources, and the sha256 of each file.

Rules applied: facts only (no descriptions), closed businesses and hidden addresses left out, emails only
when the business lists them itself. Apps should pin this version and verify the sha256.
""")
    print(f"{a.version}: {len(rows)} listings -> {a.out}")
    print("sha256", manifest["files"]["directory.csv"]["sha256"])


if __name__ == "__main__":
    main()
