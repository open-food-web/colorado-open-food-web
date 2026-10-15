#!/usr/bin/env python3
"""Entity registry: the memory of every business we looked at and what we decided.

The data set lists what we decided to list. This registry remembers the rest: businesses we
investigated and chose NOT to list, ones we listed that closed, folded into another business
or were renamed, owners who opted out, and ones we could not resolve. Automation consults it
before it suggests, adds or re-researches anything, so an old record is never "found" again
and proposed as a new business.

File: inputs/registry/decisions.csv (append-only; the latest row for an entity is
its current decision). Columns:

  decided_on, name, city, website, phone, aliases, decision, reason_code, reason_note,
  successor_name, successor_city, evidence_url, decided_by, recheck_after, origin

  decision     not_listed | closed | merged | renamed | opted_out | on_hold | unresolved | listed
               (listed = reinstated: an earlier decision was reversed on purpose)
  reason_code  see REASONS
  aliases      other names it has gone by, ';'-separated
  recheck_after  ISO date; after it the entity may be re-surfaced for review (never auto-added)

Blocking decisions (BLOCKING) stop an entity being suggested or added again. `on_hold` and
`unresolved` do not block research; they stop duplicate research and carry the notes.

Matching (find): the name key plus the town when both sides have one, or the website domain,
or the phone number. Name alone is never enough when towns differ.

CLI:
  python scripts/scrape/registry.py sync                 seed/refresh from the existing decision files
  python scripts/scrape/registry.py lookup "Name" [city] show decisions for an entity
  python scripts/scrape/registry.py add --name N --city C --decision D --reason R --note "..." [--successor-name S --evidence URL]
  python scripts/scrape/registry.py check FILE.csv        match a CSV of candidates (column "Business Name" or "Prospect Name")
  python scripts/scrape/registry.py report                counts by decision and reason

Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
from collections import Counter
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
PATH = os.path.join(REPO, "inputs", "registry", "decisions.csv")
SOURCE_DIR = os.path.join(REPO, "inputs")
SRC_ROOT = os.environ.get("FOODWEB_SOURCES") or os.path.join(os.path.dirname(REPO), "colorado-open-food-web-sources")

FIELDS = ["decided_on", "name", "city", "website", "phone", "aliases", "decision", "reason_code", "reason_note",
          "successor_name", "successor_city", "evidence_url", "decided_by", "recheck_after", "origin"]

DECISIONS = ("not_listed", "closed", "merged", "renamed", "opted_out", "on_hold", "unresolved", "listed")
BLOCKING = {"not_listed", "closed", "merged", "renamed", "opted_out"}
# Decisions a human can reverse by listing the entity again. Merges and renames are structural
# (dedup_decisions.csv enforces them), so a curated record that matches one is not a reversal.
REVERSIBLE = {"not_listed", "closed", "opted_out"}
REASONS = (
    "not_food_system",        # landscaping, a school, a trade association, knives ...
    "not_colorado",           # operates outside Colorado
    "changed_business",       # same address, now something else (a wedding venue, an event space)
    "closed_permanently",     # confirmed shut down
    "closed_temporarily",     # shut for now; recheck later
    "merged_into",            # folded into another listed business
    "renamed_to",             # now trades under another name
    "duplicate_of",           # the same business as another record
    "wholesale_only",         # sells only wholesale; kept as data, not shown
    "no_public_presence",     # investigated, nothing findable
    "owner_opt_out",          # the owner asked not to be listed
    "did_not_qualify",        # looked at and decided it does not fit
    "reconsidered",           # a business we had declined or closed is listed again, on new evidence
    "other",
)

# Sites that identify an aggregator or a social page, not the business: never a match on their own.
GENERIC_DOMAINS = {
    "facebook.com", "instagram.com", "linktr.ee", "twitter.com", "x.com", "youtube.com", "tiktok.com", "pinterest.com",
    "google.com", "yelp.com", "linkedin.com", "marketspread.com", "localharvest.org", "squarespace.com", "wixsite.com",
    "wix.com", "weebly.com", "godaddysites.com", "barn2door.com", "app.barn2door.com", "square.site", "business.site",
    "localfoodmarketplace.com", "grazecart.com", "shopify.com", "myshopify.com", "wordpress.com", "blogspot.com",
    "mapquest.com", "tripadvisor.com", "usdalocalfoodportal.com", "coloradoproud.com",
}
_STOP = {"llc", "inc", "ltd", "the", "and"}


def name_key(name: str) -> str:
    s = re.sub(r"\(.*?\)", " ", (name or "").lower().replace("&", " and ").replace("'", "").replace("’", ""))
    return "".join(w for w in re.findall(r"[a-z0-9]+", s) if w not in _STOP)


def city_key(city: str) -> str:
    return re.sub(r"[^a-z]", "", (city or "").lower())


def domain_of(url: str) -> str:
    if not url:
        return ""
    u = url.strip()
    if "//" not in u:
        u = "https://" + u
    host = (urlsplit(u).netloc or "").lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    if not host or host in GENERIC_DOMAINS or any(host.endswith("." + g) for g in GENERIC_DOMAINS):
        return ""
    return host


def phone_of(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else ""


class Registry:
    """The current decision per entity, indexed for matching."""

    def __init__(self, rows: Iterable[dict]):
        self.rows: List[dict] = []
        latest: Dict[tuple, dict] = {}
        for r in rows:
            k = (name_key(r.get("name", "")), city_key(r.get("city", "")))
            if not k[0]:
                continue
            prev = latest.get(k)
            if prev:                  # a later decision keeps what the earlier row knew
                r = dict(r)
                for f in ("website", "phone"):
                    if not r.get(f) and prev.get(f):
                        r[f] = prev[f]
                al = [x for x in re.split(r"\s*;\s*", (prev.get("aliases", "") or "") + ";" + (r.get("aliases", "") or "")) if x]
                r["aliases"] = "; ".join(dict.fromkeys(al))
            latest[k] = r            # later rows win: the file is append-only
        self.rows = list(latest.values())
        self.by_name: Dict[str, List[dict]] = {}
        self.by_domain: Dict[str, List[dict]] = {}
        self.by_phone: Dict[str, List[dict]] = {}
        for r in self.rows:
            names = [r.get("name", "")] + [a for a in re.split(r"\s*;\s*", r.get("aliases", "") or "") if a]
            for n in names:
                self.by_name.setdefault(name_key(n), []).append(r)
            d = domain_of(r.get("website", ""))
            if d:
                self.by_domain.setdefault(d, []).append(r)
            p = phone_of(r.get("phone", ""))
            if p:
                self.by_phone.setdefault(p, []).append(r)

    def find(self, name: str = "", city: str = "", website: str = "", phone: str = "", strict: bool = False) -> List[dict]:
        """Decisions matching an entity. `strict` (used when enforcing) needs the town to agree, or a
        shared website domain or phone; a bare name match is only a lookup hint."""
        out: List[dict] = []

        def add(r):
            if r not in out:
                out.append(r)

        nk, ck = name_key(name), city_key(city)
        for r in self.by_name.get(nk, []) if nk else []:
            rc = city_key(r.get("city", ""))
            if ck and rc:
                if ck == rc:
                    add(r)
            elif r.get("website") and website and domain_of(website) and domain_of(website) == domain_of(r["website"]):
                add(r)
            elif not strict and (not ck or not rc):
                # one side has no town: match only if it is the only entity by that name
                if len(self.by_name.get(nk, [])) == 1:
                    add(r)
        d = domain_of(website)
        for r in self.by_domain.get(d, []) if d else []:
            add(r)
        p = phone_of(phone)
        for r in self.by_phone.get(p, []) if p else []:
            add(r)
        return out

    @staticmethod
    def is_blocking(row: dict, today: Optional[str] = None) -> bool:
        if row.get("decision") not in BLOCKING:
            return False
        after = (row.get("recheck_after") or "").strip()
        return not (after and after <= (today or dt.date.today().isoformat()))


def load(path: str = PATH) -> Registry:
    if not os.path.exists(path):
        return Registry([])
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return Registry(list(csv.DictReader(fh)))


def _append(rows: List[dict], path: str = PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({f: r.get(f, "") for f in FIELDS})


def add_decision(name: str, city: str = "", decision: str = "not_listed", reason_code: str = "other", reason_note: str = "",
                 successor_name: str = "", successor_city: str = "", evidence_url: str = "", decided_by: str = "",
                 recheck_after: str = "", origin: str = "manual", website: str = "", phone: str = "", aliases: str = "",
                 decided_on: str = "", path: str = PATH) -> dict:
    assert decision in DECISIONS, decision
    assert reason_code in REASONS, reason_code
    row = {"decided_on": decided_on or dt.date.today().isoformat(), "name": name, "city": city, "website": website, "phone": phone,
           "aliases": aliases, "decision": decision, "reason_code": reason_code, "reason_note": reason_note,
           "successor_name": successor_name, "successor_city": successor_city, "evidence_url": evidence_url,
           "decided_by": decided_by, "recheck_after": recheck_after, "origin": origin}
    _append([row], path)
    return row


def guard(markets: list, registry: Optional[Registry] = None, quiet: bool = False) -> list:
    """Apply the registry to a build's records. Returns the records to keep.

    * closed  -> kept but marked Closed (never shown on the map)
    * not_listed / merged / renamed / opted_out -> dropped when a SOURCE brought the entity back
    Records from the curated research file (source "curated") are never dropped: a human who
    adds a record in curated_records.csv is reconsidering the decision on purpose. Those are
    reported so the registry row can be updated.
    """
    reg = registry or load()
    kept, dropped, closed, reconsidered = [], [], [], []
    for m in markets:
        hits = [r for r in reg.find(m.business_name, m.city, m.website, m.phone, strict=True) if reg.is_blocking(r)]
        # a merged or renamed decision names its successor: the surviving record is not the one to drop
        hits = [r for r in hits if not (r["decision"] in ("merged", "renamed") and r.get("successor_name")
                                        and name_key(r["successor_name"]) == name_key(m.business_name))]
        if not hits:
            kept.append(m)
            continue
        h = hits[0]
        if m.source == "curated":
            if h["decision"] in REVERSIBLE and not (h["decision"] == "closed" and m.status == "Closed"):
                reconsidered.append((m.business_name, h["decision"]))   # a closed record agrees with the registry
            kept.append(m)
        elif h["decision"] == "closed":
            if m.status != "Closed":
                m.status = "Closed"
                closed.append(m.business_name)   # only report ones the registry had to close
            kept.append(m)
        else:
            dropped.append((m.business_name, h["decision"], h.get("reason_code", "")))
    if not quiet:
        if dropped:
            print(f"Registry: suppressed {len(dropped)} re-surfaced entities: "
                  + "; ".join(f"{n} ({d}/{r})" for n, d, r in dropped[:10]) + (" ..." if len(dropped) > 10 else ""))
        if closed:
            print(f"Registry: marked {len(closed)} re-surfaced closed businesses Closed: {', '.join(closed[:10])}")
        if reconsidered:
            print(f"Registry: {len(reconsidered)} curated records contradict a registry decision (curated wins; update the registry): "
                  + "; ".join(f"{n} ({d})" for n, d in reconsidered[:10]))
    return kept


# ---------------------------------------------------------------- seeding from the existing decision files

def _rd(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


_CLOSED = re.compile(r"closed|folded|no longer operat|shut down|out of business|ceased|dissolved|now operates", re.I)
_NOT_FOOD = re.compile(r"trade association|not a place|not a food|not food|association|landscap|nonprofit|non-profit|school|equine|therapy|venue|services", re.I)
_OUT_STATE = re.compile(r"new mexico|aztec|\bnm\b|oregon|texas|michigan|connecticut|wisconsin|new york|not in colorado", re.I)


def seed_rows() -> List[dict]:
    """Decisions already recorded in the repo's other files, as registry rows."""
    rows: List[dict] = []
    today = dt.date.today().isoformat()

    for r in _rd(os.path.join(SOURCE_DIR, "curated_records.csv")):
        st = (r.get("Status") or "").strip().lower()
        base = {"name": r["Business Name"], "city": r.get("City", ""), "website": r.get("Website", ""), "phone": r.get("Phone", ""),
                "decided_on": r.get("Researched") or today, "decided_by": "research", "origin": "curated_records.csv",
                "evidence_url": (r.get("Source URLs") or "").split(";")[0].strip(), "reason_note": (r.get("Notes") or "")[:300]}
        if st == "skip":
            rows.append({**base, "decision": "not_listed", "reason_code": "did_not_qualify"})
        elif st == "closed":
            rows.append({**base, "decision": "closed", "reason_code": "closed_permanently"})
        elif st == "hold":
            rows.append({**base, "decision": "on_hold", "reason_code": "other"})
        elif st in ("call", "unclear"):
            rows.append({**base, "decision": "unresolved", "reason_code": "no_public_presence"})

    for r in _rd(os.path.join(SOURCE_DIR, "overrides.csv")):
        if (r.get("column") or "").strip() == "Status" and (r.get("value") or "").strip().lower() == "closed":
            rows.append({"name": r["name"], "city": r.get("city", ""), "decision": "closed", "reason_code": "closed_permanently",
                         "reason_note": (r.get("note") or "")[:300], "decided_on": r.get("date") or today, "decided_by": "review",
                         "origin": "overrides.csv (Status = Closed)"})
            continue
        if (r.get("mode") or "").strip().lower() != "remove":
            continue
        note = r.get("note", "")
        if _CLOSED.search(note):
            dec, code = "closed", "closed_permanently"
        elif _OUT_STATE.search(note):
            dec, code = "not_listed", "not_colorado"
        elif _NOT_FOOD.search(note):
            dec, code = "not_listed", "not_food_system"
        else:
            dec, code = "not_listed", "changed_business"
        rows.append({"name": r["name"], "city": r.get("city", ""), "decision": dec, "reason_code": code, "reason_note": note[:300],
                     "decided_on": r.get("date") or today, "decided_by": "review", "origin": "overrides.csv (remove)"})

    for r in _rd(os.path.join(SOURCE_DIR, "dedup_decisions.csv")):
        if (r.get("action") or "").strip().lower() != "merge":
            continue
        succ = r.get("keep_name") or r.get("target_name", "")
        if name_key(r["name"]) == name_key(succ) and city_key(r.get("city", "")) == city_key(r.get("target_city", "")):
            continue          # a spelling variant of the same name: not a different business that went away
        rows.append({"name": r["name"], "city": r.get("city", ""), "decision": "merged", "reason_code": "merged_into",
                     "reason_note": (r.get("note") or "")[:300], "successor_name": r.get("keep_name") or r.get("target_name", ""),
                     "successor_city": r.get("target_city", ""), "decided_on": today, "decided_by": "review",
                     "origin": "dedup_decisions.csv"})

    ps = os.path.join(SRC_ROOT, "data-compiled", "phase3", "prospect_status.csv")
    for r in _rd(ps):
        if r.get("Status") == "Out of scope":
            note = (r.get("Notes") or "")
            code = "not_colorado" if _OUT_STATE.search(note) else ("not_food_system" if _NOT_FOOD.search(note) else "did_not_qualify")
            rows.append({"name": r["Prospect Name"], "city": r.get("City", ""), "decision": "not_listed", "reason_code": code,
                         "reason_note": note[:300], "decided_on": today, "decided_by": "research", "origin": "prospect_status.csv"})
    return rows


def _curated_adds() -> List[dict]:
    return [r for r in _rd(os.path.join(SOURCE_DIR, "curated_records.csv")) if (r.get("Status") or "").strip().lower() == "add"]


def sync(path: str = PATH, rows: Optional[List[dict]] = None, adds: Optional[List[dict]] = None) -> int:
    """Append decisions that are not already in the registry, and reversals.

    Seeds come from the repo's decision files (curated skip / closed / hold / call / unclear,
    overrides `remove`, dedup `merge`, out-of-scope prospects). A curated `add` row for an entity
    the registry currently blocks is a deliberate reversal: record it as `listed`, so the
    registry stops reporting it as a contradiction. Idempotent."""
    existing = _rd(path)
    have = {(name_key(r.get("name", "")), city_key(r.get("city", "")), r.get("decision", "")) for r in existing}
    new: List[dict] = []
    for r in (rows if rows is not None else seed_rows()):
        k = (name_key(r["name"]), city_key(r.get("city", "")), r["decision"])
        if k in have or not k[0]:
            continue
        have.add(k)
        new.append(r)
    reg = Registry(existing + new)
    today = dt.date.today().isoformat()
    for a in (adds if adds is not None else _curated_adds()):
        hits = [h for h in reg.find(a["Business Name"], a.get("City", ""), a.get("Website", ""), a.get("Phone", ""), strict=True)
                if h.get("decision") in REVERSIBLE]
        if hits:
            new.append({"name": a["Business Name"], "city": a.get("City", ""), "website": a.get("Website", ""), "phone": a.get("Phone", ""),
                        "decision": "listed", "reason_code": "reconsidered", "decided_on": a.get("Researched") or today,
                        "decided_by": "research", "origin": "curated_records.csv (add)",
                        "reason_note": f"Listed again after an earlier {hits[0]['decision']} decision ({hits[0].get('reason_code', '')})."})
            reg = Registry(existing + new)
    if new:
        _append(new, path)
    return len(new)


# ---------------------------------------------------------------- CLI

def _fmt(r: dict) -> str:
    s = f"{r['decision']} / {r.get('reason_code', '')} on {r.get('decided_on', '')} by {r.get('decided_by', '') or '?'}"
    if r.get("successor_name"):
        s += f" -> {r['successor_name']} ({r.get('successor_city', '')})"
    if r.get("reason_note"):
        s += f": {r['reason_note'][:140]}"
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync")
    lk = sub.add_parser("lookup"); lk.add_argument("name"); lk.add_argument("city", nargs="?", default="")
    ad = sub.add_parser("add")
    ad.add_argument("--name", required=True); ad.add_argument("--city", default="")
    ad.add_argument("--decision", required=True, choices=DECISIONS); ad.add_argument("--reason", default="other", choices=REASONS)
    ad.add_argument("--note", default=""); ad.add_argument("--successor-name", default=""); ad.add_argument("--successor-city", default="")
    ad.add_argument("--evidence", default=""); ad.add_argument("--by", default=""); ad.add_argument("--recheck-after", default="")
    ad.add_argument("--website", default=""); ad.add_argument("--phone", default=""); ad.add_argument("--aliases", default="")
    ck = sub.add_parser("check"); ck.add_argument("file")
    sub.add_parser("report")
    a = ap.parse_args(argv)

    if a.cmd == "sync":
        n = sync()
        print(f"registry: {n} decisions added from the existing files ({PATH})")
    elif a.cmd == "lookup":
        hits = load().find(a.name, a.city)
        print("\n".join(f"{r['name']} ({r.get('city', '')}): {_fmt(r)}" for r in hits) or "no decision on file")
    elif a.cmd == "add":
        add_decision(a.name, a.city, a.decision, a.reason, a.note, a.successor_name, a.successor_city, a.evidence, a.by,
                     a.recheck_after, "manual", a.website, a.phone, a.aliases)
        print("recorded")
    elif a.cmd == "check":
        reg = load()
        rows = _rd(a.file)
        nm = "Business Name" if rows and "Business Name" in rows[0] else "Prospect Name"
        hit = 0
        for r in rows:
            m = [x for x in reg.find(r.get(nm, ""), r.get("City", ""), r.get("Website", ""), r.get("Phone", ""))]
            if m:
                hit += 1
                print(f"{r.get(nm)}: {_fmt(m[0])}{'' if reg.is_blocking(m[0]) else '  [not blocking]'}")
        print(f"{hit} of {len(rows)} candidates already have a registry decision")
    elif a.cmd == "report":
        reg = load()
        print(f"{len(reg.rows)} entities")
        for (d, c), n in sorted(Counter((r['decision'], r.get('reason_code', '')) for r in reg.rows).items()):
            print(f"  {n:4d}  {d:11s} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
