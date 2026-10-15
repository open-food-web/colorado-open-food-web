"""Deduplicate + merge markets across sources into one row per real market.

Priority: sources are folded in the order given (put the most trustworthy first —
Colorado Proud, then USDA, then CFMA, then curated). The first source to fill a
field wins; later sources only fill gaps. Provenance is preserved per field.

Dedup key: normalized-name + city. A light second pass also merges two groups whose
coordinates sit within ~200 m of each other (catches name spelling drift), so long
as they are in the same city AND share a distinctive name word - dense directories
(the Colorado Proud member finder) put unrelated businesses on the same block.
"""
from __future__ import annotations

import csv
import math
import os
from typing import Dict, List, Set, Tuple

from .normalize import name_key
from .schema import ATTR_TO_COLUMN, Market

MERGE_METERS = 200
# Words too common to show two names are the same business (on top of name_key's stops).
GENERIC_NAME_WORDS = {"farm", "farms", "ranch", "ranches", "and", "company", "csa",
                      "family", "organic", "organics", "garden", "gardens", "u", "pick"}


def _shares_name_word(a: Market, b: Market) -> bool:
    """Proximity alone doesn't make two records one business: dense directories (the
    Colorado Proud member finder) put unrelated businesses on the same block. A shared
    town name alone counts only between the same kind of place: "Boulder County Farmers'
    Market" is "Boulder Farmers Market", but "Salida Community Center" (a food bank) is
    not "Salida Farmers Market"."""
    shared = ((set(name_key(a.business_name).split()) - GENERIC_NAME_WORDS)
              & (set(name_key(b.business_name).split()) - GENERIC_NAME_WORDS))
    town = set(name_key(a.city).split()) | set(name_key(b.city).split())
    if shared and shared <= town:
        cats = lambda m: {c.strip() for c in m.category.split(",") if c.strip()}
        return bool(cats(a) & cats(b))
    return bool(shared)


def _haversine_m(a: Market, b: Market) -> float:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return math.inf
    r = 6371000.0
    p1, p2 = math.radians(a.latitude), math.radians(b.latitude)
    dp = math.radians(b.latitude - a.latitude)
    dl = math.radians(b.longitude - a.longitude)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _fold(base: Market, other: Market) -> None:
    """Fill base's empty fields from other, carrying other's provenance."""
    for attr, col in ATTR_TO_COLUMN.items():
        if getattr(base, attr) in ("", None) and getattr(other, attr) not in ("", None):
            setattr(base, attr, getattr(other, attr))
            base.provenance[col] = other.provenance.get(col, other.source)
    base.add_categories(other.categories)  # a farm in two directories keeps both
    if base.latitude is None and other.latitude is not None:
        base.latitude, base.longitude = other.latitude, other.longitude
        base.geo_source = other.geo_source or other.source
    if not base.source_id and other.source_id:
        # keep the source's stable id + update stamp for change detection
        base.source_id, base.source_updated = other.source_id, other.source_updated
    # other may itself be a merged record ("official-site+usda"), so add label by label
    labels = [s for s in base.source.split("+") if s]
    for s in other.source.split("+"):
        if s and s not in labels:
            labels.append(s)
    base.source = "+".join(labels)


def _rkey(name: str, city: str) -> tuple:
    return (name_key(name), city.strip().lower())


def load_decisions(path: str) -> List[dict]:
    """Human dedup decisions (source-data/phase2/dedup_decisions.csv). Columns:
    action (merge | distinct), name, city, target_name, target_city, keep_name, note.
    Missing file -> no decisions."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("action") or "").strip()]


def apply_decisions(markets: List[Market], decisions: List[dict]) -> Tuple[List[Market], Set[frozenset]]:
    """Apply reviewed decisions so they survive every rebuild.

    merge    -> fold record (name, city) into (target_name, target_city): the target
                keeps its values, gaps fill from the other, categories union. If
                keep_name is set it becomes the Business Name (with provenance).
    distinct -> the pair is confirmed different; returned so flag_possible_dups skips it.

    A decision whose records aren't in this build is reported, not fatal (sources
    drop listings; see UPDATE_ENGINE principle 4)."""
    index = {_rkey(m.business_name, m.city): m for m in markets}
    removed, distinct = set(), set()
    for d in decisions:
        action = d["action"].strip().lower()
        a = _rkey(d.get("name", ""), d.get("city", ""))
        b = _rkey(d.get("target_name", ""), d.get("target_city", "") or d.get("city", ""))
        if action == "distinct":
            distinct.add(frozenset((a, b)))
            continue
        if action != "merge":
            print(f"  dedup decision: unknown action {action!r} for {d.get('name')}")
            continue
        src, dst = index.get(a), index.get(b)
        if src is None or dst is None or src is dst:
            print(f"  dedup decision not applied (record missing): "
                  f"{d.get('name')} -> {d.get('target_name')}")
            continue
        _fold(dst, src)
        keep = (d.get("keep_name") or "").strip()
        if keep:
            dst.business_name = keep
            dst.provenance["Business Name"] = "dedup-decision"
        removed.add(id(src))
        index[a] = dst  # later decisions naming the merged-away record follow it
    kept = [m for m in markets if id(m) not in removed]
    # keys may have changed via keep_name; distinct pairs are matched on current names
    return kept, distinct


def load_overrides(path: str) -> List[dict]:
    """Curated corrections (source-data/phase2/overrides.csv). Columns: name, city,
    column (a My Maps column label, e.g. Category / Notes / Hours), mode (set |
    prepend | clear | remove), value, note, date. Missing file -> none."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("name") or "").strip()]


def apply_overrides(markets: List[Market], overrides: List[dict]) -> None:
    """Apply human corrections last, so they beat every source (UPDATE_ENGINE.md
    principle 5: manual beats automatic, permanently). `set` replaces the value;
    `prepend` puts the value in front of what the sources said (for status notes that
    should sit above a provider's own description); `clear` empties the field (e.g. a
    website that now points somewhere unsafe); `remove` drops the whole record (e.g. a
    trade association listed as a food hub; column is ignored). Provenance becomes
    "override". `markets` is modified in place.
    A row whose record isn't in this build is reported, not fatal."""
    col_attr = {col: attr for attr, col in ATTR_TO_COLUMN.items()}
    col_attr["Category"] = "category"
    # Coordinates for places no geocoder can find (rural roads); value is a number.
    col_attr["Latitude"], col_attr["Longitude"] = "latitude", "longitude"
    index = {_rkey(m.business_name, m.city): m for m in markets}
    for o in overrides:
        m = index.get(_rkey(o["name"], o.get("city", "")))
        mode = (o.get("mode") or "set").strip().lower()
        if mode == "remove":
            if m is None:
                print(f"  override not applied (record missing): {o['name']} / remove")
            elif m in markets:
                markets.remove(m)
            continue
        attr = col_attr.get((o.get("column") or "").strip())
        if m is None or attr is None:
            print(f"  override not applied ({'record missing' if m is None else 'unknown column'}): "
                  f"{o['name']} / {o.get('column')}")
            continue
        value = "" if mode == "clear" else (o.get("value") or "").strip()
        if mode == "prepend" and getattr(m, attr):
            value = f"{value} {getattr(m, attr)}"
        if attr in ("latitude", "longitude"):
            try:
                value = float(value) if value else None
            except ValueError:
                print(f"  override not applied (not a number): {o['name']} / {o['column']} = {value!r}")
                continue
            m.geo_source = "override"
        setattr(m, attr, value)
        m.provenance[o["column"].strip()] = "override"


def flag_possible_dups(markets: List[Market], radius_m: int = 150,
                       distinct: Set[frozenset] = frozenset()) -> None:
    """Non-destructive: set m.dup_hint to a sibling's name when two markets in the
    same city look like the same place — one name is a token-subset of the other
    (the strong signal), or they sit almost on top of each other (<= radius_m).
    Surfaced for human review, NOT merged — auto-merging would wrongly collapse
    distinct seasonal / East-West listings that share a name stem. Pairs a human
    already confirmed as different (`distinct`, from apply_decisions) are skipped."""
    for i, a in enumerate(markets):
        for b in markets[i + 1:]:
            if a.city.strip().lower() != b.city.strip().lower():
                continue
            if frozenset((_rkey(a.business_name, a.city),
                          _rkey(b.business_name, b.city))) in distinct:
                continue
            ta = set(name_key(a.business_name).split())
            tb = set(name_key(b.business_name).split())
            subset = ta and tb and (ta <= tb or tb <= ta)
            close = _haversine_m(a, b) <= radius_m
            if subset or close:
                a.dup_hint = a.dup_hint or b.business_name
                b.dup_hint = b.dup_hint or a.business_name


def merge(records: List[Market]) -> List[Market]:
    """Fold an ordered list of records (highest priority first) into unique markets."""
    groups: Dict[tuple, Market] = {}
    for rec in records:
        key = (name_key(rec.business_name), rec.city.strip().lower())
        if key in groups:
            _fold(groups[key], rec)
            continue
        # second-chance merge on coordinate proximity within the same city
        merged = False
        for (nk, city), base in groups.items():
            if city == key[1] and _haversine_m(base, rec) <= MERGE_METERS                     and _shares_name_word(base, rec):
                _fold(base, rec)
                merged = True
                break
        if not merged:
            groups[key] = rec
    return list(groups.values())
