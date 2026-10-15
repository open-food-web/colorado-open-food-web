#!/usr/bin/env python3
"""Reconcile the Phase 3 farm prospects into one current status each.

Joins, for every prospect on data-compiled/phase3/prospective_farms.csv:
  * the data set today (source-data/phase2/co_farmers_markets_all_raw.csv), by name;
  * the first-pass status already on the prospect list;
  * the web research pass (prospect_research.csv: fit and confidence);
  * the site verification (prospect_verification.csv: promote / review / reject);
  * the research log in curated_records.csv (add / skip / market-only / call / hold / closed).

Writes data-compiled/phase3/prospect_status.csv: one row per prospect with a Status and a
Next Action, so nothing is researched twice and it is clear what is left.

Run from the repo root:  python scripts/phase3/reconcile_prospects.py
Stdlib only. Re-run after any of the inputs change.

Scope (see docs/CATEGORIES.md): any food production, making, distribution or consumption can
be in the data set, so flower farms, nurseries, seed companies, cottage food, resellers and
processors are in scope. What stays out: not in Colorado, closed, or not part of the food
system at all (landscaping, knives, a school).
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

import os
REPO = Path(__file__).resolve().parent.parent.parent
SRC_ROOT = Path(os.environ.get("FOODWEB_SOURCES") or (REPO.parent / "colorado-open-food-web-sources"))
P3 = SRC_ROOT / "data-compiled" / "phase3"
RAW = REPO / ".cache" / "build" / "co_farmers_markets_all_raw.csv"
CURATED = REPO / "inputs" / "curated_records.csv"
OUT = P3 / "prospect_status.csv"

SUFFIX = {"llc", "inc", "ltd", "co", "company", "corp", "the", "and", "of", "dba"}
GENERIC = SUFFIX | {"farm", "farms", "ranch", "ranches", "garden", "gardens", "homestead", "orchard", "orchards",
                    "produce", "foods", "food", "market", "honey", "beef", "meats", "creek", "valley", "mountain", "acres",
                    "family", "organic", "natural"}


def rd(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def key(s):
    s = re.sub(r"\(.*?\)", " ", (s or "").lower().replace("&", " and ").replace("'", "").replace("’", ""))
    return "".join(w for w in re.findall(r"[a-z0-9]+", s) if w not in {"llc", "inc", "ltd", "the", "and"})


def loose(s):
    """Distinctive-token key; None when the name has too little to match on."""
    s = re.sub(r"\(.*?\)", " ", (s or "").lower().replace("&", " and ").replace("'", "").replace("’", ""))
    toks = [w.rstrip("s") if len(w) > 4 else w for w in re.findall(r"[a-z0-9]+", s) if w not in GENERIC]
    return "".join(sorted(toks)) if toks else None


# Names the verified records were stored under
ALIAS = {"pope farm's produce": "Pope Farms Produce & Garden Center", "elephant rock farms": "Elephant Rock Farm",
         "pipers lane flowers": "Piper's Lane Flowers", "bamber beef ranch": "Bamber Ranch",
         "sandy seed farm llc": "Sandy Seed Farm", "the stone fruit company llc": "Stone Fruit Company"}

OUT_OF_SCOPE_WORDS = re.compile(
    r"new mexico|aztec|\bnm\b|wisconsin|oregon|texas|michigan|connecticut|new york|not in colorado|landscap|knife|knives|guns|leatherwork|"
    r"school|nonprofit|non-profit|organizing|equine|therapy|candle|soap maker|dog treat|dog chew|not food", re.I)
NOTE_RESCOPE = re.compile(r"flower|nursery|seed|reseller|cottage|cheese|processor|plant|houseplant|dip|bakery|dessert|ice cream|salmon|matcha|tea\b|mushroom", re.I)

ORDER = ["In the data set", "Probably in the data: confirm", "Closed", "Needs your call", "Verified: add as a market vendor", "Likely: verify next", "Now in scope: verify",
         "Unclear: needs a lookup", "Needs a call", "Site guess was wrong: still unresolved", "Out of scope", "Not researched"]


def main():
    prospects = rd(P3 / "prospective_farms.csv")
    research = {key(r["Prospect Name"]): r for r in rd(P3 / "prospect_research.csv")}
    verify = {key(r["Prospect Name"]): r for r in rd(P3 / "prospect_verification.csv")}
    curated = {}
    for r in rd(CURATED):
        curated.setdefault(key(r["Business Name"]), r)
    raw = rd(RAW)
    by_key, by_loose = {}, {}
    for r in raw:
        by_key.setdefault(key(r["Business Name"]), r)
        lk = loose(r["Business Name"])
        if lk:
            by_loose.setdefault(lk, []).append(r)

    rows = []
    for p in prospects:
        name = p["Prospect Name"]
        k = key(name)
        res, ver, cur = research.get(k, {}), verify.get(k, {}), curated.get(k, {})
        alias = ALIAS.get(name.lower())
        rec = by_key.get(k) or (by_key.get(key(alias)) if alias else None)
        possible = ""
        if not rec:
            lk = loose(name)
            cands = by_loose.get(lk, []) if lk else []
            if len(cands) >= 1 and len(lk) >= 6:
                possible = "; ".join(f"{c['Business Name']} ({c['City']})" for c in cands[:3])
        fit = (res.get("Fit") or "").lower()
        conf = (res.get("Confidence") or "").lower()
        first = p.get("Status", "")
        action = ver.get("Action", "")
        cstat = (cur.get("Status") or "").lower()
        evid = " ".join([res.get("Evidence", ""), res.get("Note", ""), ver.get("Notes", ""), cur.get("Notes", "")])

        known_as = p.get("Known Match", "")
        if rec or p.get("Already Known") == "yes" or first == "first pass: already in dataset":
            status, nxt = "In the data set", "None. Keep details current."
        elif cstat == "closed":
            status, nxt = "Closed", "None. Kept marked Closed so it is not researched again."
        elif action == "Promote":
            status, nxt = "In the data set", "Promoted from prospect_verification.csv; check the record shows."
        elif action == "Review before promoting":
            status, nxt = "Needs your call", "Decide scope (see the verification notes)."
        elif cstat == "market-only":
            status, nxt = "Verified: add as a market vendor", "Add as a Market Vendor record (no pin); it sells only at markets or online."
        elif cstat == "call":
            status, nxt = "Needs a call", "On docs/CALL_LIST.md: confirm whether it operates."
        elif action.startswith("Reject"):
            status, nxt = "Site guess was wrong: still unresolved", "Find the real site (Google through Chrome) or ask the market manager."
        elif fit == "likely":
            status, nxt = "Likely: verify next", "Verify from its own pages, then promote."
        elif fit == "unlikely":
            if OUT_OF_SCOPE_WORDS.search(evid) and not NOTE_RESCOPE.search(res.get("Note", "")):
                status, nxt = "Out of scope", "None unless the facts change (not Colorado, or not part of the food system)."
            else:
                status, nxt = "Now in scope: verify", "Was marked unlikely only for not being a farm; in scope under the food-system rule. Verify."
        elif fit == "unclear" or first == "first pass: unclear" or cstat in ("unclear", "hold"):
            status, nxt = "Unclear: needs a lookup", "Google it (Chrome) or ask the market manager."
        elif first == "first pass: not qualified" or cstat == "skip":
            if NOTE_RESCOPE.search(evid):
                status, nxt = "Now in scope: verify", "Skipped earlier; may qualify under the food-system scope. Re-check."
            else:
                status, nxt = "Out of scope", "Skipped in the first pass."
        elif first == "first pass: qualified":
            status, nxt = "Likely: verify next", "Qualified in the first pass; verify and promote."
        else:
            status, nxt = "Not researched", "Research it."

        if possible and status in ("Likely: verify next", "Now in scope: verify", "Unclear: needs a lookup"):
            status, nxt = "Probably in the data: confirm", "Looks like an existing record (see Possible Match In Data); confirm it is the same business."
        rows.append({
            "Prospect Name": name, "Status": status, "Next Action": nxt,
            "In Data As": f"{rec['Business Name']} ({rec['City']})" if rec else (known_as or alias or ""),
            "Possible Match In Data": possible,
            "Research Fit": fit, "Research Confidence": conf, "First Pass Status": first,
            "Verification": action or ver.get("Verified", ""), "Curated Log Status": cstat,
            "County": p.get("County", ""), "Market Count": p.get("Market Count", ""), "Markets": p.get("Markets", ""),
            "Website": ver.get("Candidate Site", "") if action and not action.startswith("Reject") else res.get("Website", ""),
            "City": ver.get("Town (site)", "") or res.get("City", "") or p.get("Locations Stated", ""),
            "Products": ver.get("Products", "") or res.get("Products", ""),
            "Notes": (ver.get("Notes", "") or res.get("Note", "") or cur.get("Notes", ""))[:240],
        })

    rows.sort(key=lambda r: (ORDER.index(r["Status"]), r["Prospect Name"].lower()))
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    c = Counter(r["Status"] for r in rows)
    print(f"{len(rows)} prospects -> {OUT.relative_to(REPO)}")
    for s in ORDER:
        if c[s]:
            print(f"  {c[s]:4d}  {s}")
    print(f"  possible (unconfirmed) matches in the data: {sum(1 for r in rows if r['Possible Match In Data'] and r['Status'] != 'In the data set')}")


if __name__ == "__main__":
    sys.exit(main())
