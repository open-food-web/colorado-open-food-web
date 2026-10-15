"""Orchestrate all sources -> dedupe/merge -> geocode gaps -> write CSVs.

Outputs (new files; Farm Fresh CSVs are left untouched):
  data/co_farmers_markets_all_mymaps.csv  : the 23 My Maps columns, import-ready
  data/co_farmers_markets_all_raw.csv     : same + source/geo_source/provenance audit

Run (offline; reads the saved source snapshots, never the network for source data):
  python scripts/scrape/build.py
Check sources for new data on purpose, separately (writes snapshots + a change report):
  python scripts/scrape/refresh_sources.py [source ...]
The USDA key is read from the git-ignored .env at the repo root (USDA_API_KEY=...);
a real environment variable of the same name overrides it. No key -> keyless fallback.
"""
from __future__ import annotations

import csv
import dataclasses
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape import geocode, normalize, snapshots
from scrape.merge import (apply_decisions, apply_overrides, flag_possible_dups,
                          load_decisions, load_overrides, merge)
from scrape.normalize import in_colorado
from scrape.schema import COLUMNS, Market
from scrape.sources import curated, enrichment, farm_fresh

# PHASE 2 (in development — NOT the live product). Outputs are isolated under phase2/
# so they never touch the live Phase 1 file data-compiled/farm_fresh_directory_mymaps.csv.
# Canonical split: compiled map-ready CSV -> data-compiled/phase2/;
# full raw+provenance export -> source-data/phase2/.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
INPUT_DIR = os.path.join(REPO, "inputs")
BUILD_DIR = os.path.join(REPO, ".cache", "build")
COMPILED_DIR = SOURCE_DIR = BUILD_DIR


def load_env(path: str = os.path.join(REPO, ".env")) -> None:
    """Load KEY=VALUE lines from the git-ignored .env at the repo root (secrets like
    USDA_API_KEY live there, never in git). Real environment variables win; missing
    file is fine. Lines starting with # are comments."""
    try:
        fh = open(path, encoding="utf-8")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v


def collect(snapshot_dir: str = snapshots.SNAPSHOT_DIR) -> list:
    """Gather records in priority order, offline: local inputs plus the saved source
    snapshots. Network sources are only contacted by refresh_sources.py."""
    # Order = field-value priority (first source to fill a field wins):
    # official-site enrichment > Colorado Proud (vetted) > CFMA (rich, member-maintained)
    # > Chaffee Provides (community-maintained, Chaffee County) > curated research
    # > USDA (broad, thin). See README "Field-value priority".
    records = []

    enr = enrichment.fetch()
    if enr:
        print(f"Official-site enrichment: {len(enr)} records (top priority)", flush=True)
        records += enr

    for name in snapshots.NETWORK_SOURCES:
        if name == "colorado_proud_finder":
            # Hand-researched businesses no directory carries (curated_records.csv).
            # Ranked above the member finder (self-reported) and USDA (broad, thin).
            cur = curated.fetch()
            if cur:
                print(f"Curated new records: {len(cur)}", flush=True)
                records += cur
        recs, fetched = snapshots.load(name, snapshot_dir)
        if fetched is None:
            print(f"{name}: no snapshot (run refresh_sources.py {name})", flush=True)
            continue
        print(f"{name}: {len(recs)} records (snapshot {fetched})", flush=True)
        records += recs
        if name == "colorado_proud":
            # The live map's Colorado Proud Farm Fresh data with its hand fixes (the
            # snapshot above is markets-only). Same authority, so same priority slot.
            ff = farm_fresh.fetch()
            print(f"Colorado Proud Farm Fresh (live map data): {len(ff)} records", flush=True)
            records += ff
    # Some sources ship UTF-8 text mis-decoded as cp1252 ("Salidaâ€™s"); repair every
    # text field before merging, so names and cities also match their clean spellings.
    for r in records:
        for f in dataclasses.fields(r):
            v = getattr(r, f.name)
            if isinstance(v, str) and v:
                setattr(r, f.name, normalize.fix_mojibake(v))
    return records


def fill_geography(markets: list, cache=None) -> None:
    """Geocode missing coordinates and backfill county. Derived coords are flagged
    geo_source='census-geocoder'; source-provided coords are left as-is. Lookups go
    through a persistent GeoCache, so only records new since the last build hit the
    network (GEOCODE_REFRESH=1 redoes them all)."""
    own_cache = cache is None
    if own_cache:
        refresh = os.environ.get("GEOCODE_REFRESH", "").strip().lower() in ("1", "true", "yes")
        cache = geocode.GeoCache(refresh=refresh)
    for m in markets:
        if m.latitude is None or not in_colorado(m.latitude, m.longitude):
            r = cache.geocode_address(m.address, m.city, m.zip)
            if r and in_colorado(r[0], r[1]):
                m.latitude, m.longitude, county = r
                m.geo_source = "census-geocoder"
                if not m.county and county:
                    m.set("county", county, "census-geocoder")
        if not m.county and m.latitude is not None:
            county = cache.county_for(m.latitude, m.longitude)
            if county:
                m.set("county", county, "census-geocoder")
    if own_cache:
        cache.save()
        print(f"Geography: {cache.hits} cached answers, {cache.lookups} network lookups.")


def write(markets: list) -> None:
    os.makedirs(COMPILED_DIR, exist_ok=True)
    os.makedirs(SOURCE_DIR, exist_ok=True)
    mymaps = os.path.join(COMPILED_DIR, "co_farmers_markets_all_mymaps.csv")
    raw = os.path.join(SOURCE_DIR, "co_farmers_markets_all_raw.csv")

    with open(mymaps, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for m in markets:
            w.writerow(m.to_mymaps_row())

    extra = ["Source", "Geo Source", "Possible Dup Of", "Provenance",
             "Source ID", "Source Updated",
             "Public Listing", "Hide Address", "Local Sales Channel", "Sales Channels", "Sales Locations"]
    with open(raw, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS + extra)
        w.writeheader()
        for m in markets:
            row = m.to_mymaps_row(public=False)   # the raw data keeps hidden addresses
            row["Source"] = m.source
            row["Geo Source"] = m.geo_source
            row["Possible Dup Of"] = m.dup_hint
            row["Provenance"] = json.dumps(m.provenance, separators=(",", ":"))
            row["Source ID"] = m.source_id
            row["Source Updated"] = m.source_updated
            row["Public Listing"] = m.public_listing
            row["Hide Address"] = m.hide_address
            row["Local Sales Channel"] = m.local_sales_channel
            row["Sales Channels"] = m.sales_channels
            row["Sales Locations"] = m.sales_locations
            w.writerow(row)

    print(f"Wrote {len(markets)} markets:\n  {mymaps}\n  {raw}")


def main() -> None:
    load_env()
    records = collect()
    markets = merge(records)
    # An enrichment result that merged with nothing has drifted from its target's
    # name+city key (e.g. it filled in a town the directory record lacks) and would
    # ship as a coordinate-less duplicate. Surface it loudly.
    orphans = [m.business_name for m in markets if m.source == enrichment.SOURCE]
    if orphans:
        print(f"WARNING: {len(orphans)} official-site results matched no directory record "
              f"(check name/city in enrichment/results): {orphans}")
    # Reviewed dedup decisions (merge / confirmed-distinct) — applied every build so a
    # human call is never undone by a rebuild.
    decisions = load_decisions(os.path.join(INPUT_DIR, "dedup_decisions.csv"))
    markets, distinct = apply_decisions(markets, decisions)
    if decisions:
        print(f"Applied {len(decisions)} dedup decisions.")
    fill_geography(markets)
    # Curated corrections win over every source and survive every rebuild.
    overrides = load_overrides(os.path.join(INPUT_DIR, "overrides.csv"))
    apply_overrides(markets, overrides)
    if overrides:
        print(f"Applied {len(overrides)} curated overrides.")
    flag_possible_dups(markets, distinct=distinct)
    markets.sort(key=lambda m: (m.city.lower(), m.business_name.lower()))
    write(markets)
    dups = sum(1 for m in markets if m.dup_hint)
    if dups:
        print(f"{dups} markets flagged 'Possible Dup Of' for review (see raw CSV).")


if __name__ == "__main__":
    main()
