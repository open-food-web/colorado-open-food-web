"""Offerings: the one explicit list of ways to find each producer, and the reconciled market links.

An offering is one way to find a producer: a channel (farm stand, online orders, a market...), optionally at a place or at a market, with
its own text. This is where a place is tied to the channel it serves, and where "this producer sells at that market" lives, once.

Market links have two sides that must agree:
  - the market side: vendor lists (market_vendors, from inputs/market_vendor_lists.csv)
  - the producer side: what the producer's own page says (inputs/market_links.csv)
Each (producer, market) pair becomes one offering row with `confirmed_by_market` and `confirmed_by_producer`, a derived `link_state`, a manual
`resolution` (keep | drop) and a note. A conflict (the market lists the producer, but the producer's page lists markets and omits this one)
is hidden by default, because the producer's own page wins, and is written to the review report for a person to resolve.
"""
import csv
import os

OFFERING_COLS = ["offering_id", "producer_id", "channel", "location_id", "market_id", "text", "confirm_url", "basis", "status", "shown",
                 "confirmed_by_market", "confirmed_by_producer", "market_list_years", "market_list_url", "producer_page_url",
                 "producer_checked_on", "link_state", "resolution", "link_note"]

ON_FARM = ("farm_stand", "farm_visit", "u_pick", "tour", "stay", "volunteer")
DEAD_MARKET = {"closed", "removed"}
LINK_COLS = ["producer", "producer_city", "market", "market_city", "on_producer_page", "producer_page_url", "checked_on", "resolution", "note"]


def read_links(path):
    """inputs/market_links.csv. A row with no market is the check of the producer's own page: on_producer_page is `lists_markets` (the page
    names markets), `no_markets` (it names none) or `unreadable`. A row with a market says whether the producer's page lists it (yes | no)."""
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]


def _role_channel(role, chans):
    if role == "pickup":
        return "online" if "online" in chans else ("csa" if "csa" in chans else "pickup")
    return {"store": "retail_partners", "csa_dropoff": "csa", "farm_stand": "farm_stand"}.get(role, role)


def reconcile(out, rows, nkey, warn=print):
    """One link per (producer, market) from both sides. Returns {(producer_id, market_id): link dict}."""
    pids, mids = {}, {}
    for p in out["producers"]:
        pids.setdefault(nkey(p["name"]), p["producer_id"])
    for m in out["markets"]:
        mids.setdefault(nkey(m["name"]), m["market_id"])
    market_status = {m["market_id"]: (m["status"] or "").lower() for m in out["markets"]}

    market_side = {}
    for v in out["market_vendors"]:
        d = market_side.setdefault((v["producer_id"], v["market_id"]), {"years": set(), "urls": []})
        if v["year"]:
            d["years"].add(v["year"])
        if v["source_url"] and v["source_url"] not in d["urls"]:
            d["urls"].append(v["source_url"])

    checks, producer_side = {}, {}
    for r in rows:
        pid = pids.get(nkey(r["producer"]))
        if not pid:
            warn("  market link not applied (producer not in this build): %s" % r["producer"])
            continue
        if not r["market"]:
            checks[pid] = r
            continue
        mid = mids.get(nkey(r["market"]))
        if not mid:
            warn("  market link not applied (market not in this build): %s -> %s" % (r["producer"], r["market"]))
            continue
        producer_side[(pid, mid)] = r

    links = {}
    for key in sorted(set(market_side) | set(producer_side)):
        pid, mid = key
        m, l, c = market_side.get(key), producer_side.get(key), checks.get(pid)
        if l and l["on_producer_page"] == "yes":
            producer = "yes"
        elif l and l["on_producer_page"] == "no":
            producer = "no"
        elif c and c["on_producer_page"] == "lists_markets":
            producer = "no"        # the page was checked and names markets, but not this one
        else:
            producer = ""          # unchecked, or checked and it names no markets: it says nothing either way
        if m and producer == "yes":
            state = "confirmed_both"
        elif producer == "yes":
            state = "producer_only"
        elif m and producer == "no":
            state = "conflict"
        elif m:
            state = "market_only"
        else:
            state = "unconfirmed"
        resolution = (l or {}).get("resolution", "").lower()
        if resolution == "drop" or market_status.get(mid) in DEAD_MARKET:
            shown = False
        elif resolution == "keep":
            shown = True
        else:
            shown = state in ("confirmed_both", "producer_only", "market_only")      # a conflict is hidden: the producer's page wins
        years = ";".join(sorted(m["years"])) if m else ""
        page_url = (l or {}).get("producer_page_url") or (c or {}).get("producer_page_url", "")
        checked_on = (l or {}).get("checked_on") or (c or {}).get("checked_on", "")
        notes = []
        if (l or {}).get("note"):
            notes.append(l["note"])
        if state == "conflict":
            notes.append("On the market's vendor list (%s) but not on the producer's own page, checked %s%s" % (
                years or "no year", checked_on or "(date not recorded)",
                "; kept by a person" if resolution == "keep" else "; hidden unless kept (the producer's page wins)"))
        elif state == "market_only" and c and c["on_producer_page"] == "no_markets":
            notes.append("The producer's own page, checked %s, names no markets" % (checked_on or "(date not recorded)"))
        links[key] = {
            "confirmed_by_market": "true" if m else "false", "confirmed_by_producer": "true" if producer == "yes" else "false",
            "market_list_years": years, "market_list_url": (m or {}).get("urls", [""])[0] if m and m["urls"] else "",
            "producer_page_url": page_url, "producer_checked_on": checked_on, "link_state": state,
            "resolution": resolution, "link_note": "; ".join(notes), "shown": "true" if shown else "false"}
    return links


def build(out, links, reg, channel_list, details_of):
    """Fill out["offerings"]: one row per way to find a producer. A place is tied to a channel either by a person (`stated`, the channels on its
    row in inputs/locations.csv) or, where no one has said, by its role (`role`); an on-farm channel sits at the producer's farm stand or home."""
    plocs = {}
    for r in out["producer_locations"]:
        plocs.setdefault(r["producer_id"], []).append(r)
    rows = []

    def add(pid, channel, **kw):
        row = {c: "" for c in OFFERING_COLS}
        row.update(kw)
        row.update({"producer_id": pid, "channel": channel, "status": "listed"})
        row.setdefault("shown", "true")
        if not row.get("shown"):
            row["shown"] = "true"
        row["offering_id"] = reg.get("co-off", "|".join([pid, channel, row["location_id"], row["market_id"]]))
        rows.append(row)
        return row

    for p in out["producers"]:
        pid = p["producer_id"]
        chans = channel_list(p["sales_channels"])
        details = details_of(p.get("channel_details", ""))
        places = plocs.get(pid, [])
        home = next((r for r in places if r["role"] == "home_base"), None)
        stand = next((r for r in places if r["role"] == "farm_stand"), None)
        placed = {}
        for r in places:
            if r["role"] == "home_base":
                continue
            stated = sorted(channel_list(r.get("channels")))
            for ch in (stated or [_role_channel(r["role"], chans)]):
                placed.setdefault(ch, []).append(add(pid, ch, location_id=r["location_id"], confirm_url=r.get("confirm_url", ""),
                                                     basis="stated" if stated else "role"))
        for ch in sorted(chans):
            if ch in ("farmers_market", "none"):
                continue
            if ch in placed:
                placed[ch][0]["text"] = details.get(ch, "")
            elif ch in ON_FARM:
                place = stand or home
                add(pid, ch, location_id=place["location_id"] if place else "", text=details.get(ch, ""), basis="derived")
            else:
                add(pid, ch, text=details.get(ch, ""), basis="channel")
    for (pid, mid), link in sorted(links.items()):
        add(pid, "farmers_market", market_id=mid, basis="link", **link)
    rows.sort(key=lambda r: r["offering_id"])
    out["offerings"] = rows


def write_report(path, out, links, nkey):
    """reports/market-link-conflicts.md: the links a person should look at."""
    pn = {p["producer_id"]: p["name"] for p in out["producers"]}
    mn = {m["market_id"]: m["name"] for m in out["markets"]}
    by_state = {}
    for key, l in links.items():
        by_state.setdefault(l["link_state"], []).append((pn.get(key[0], key[0]), mn.get(key[1], key[1]), l))
    lines = ["# Market links to review", "",
             "Generated by `scripts/build_tables.py` from the vendor lists and `inputs/market_links.csv`. Resolve a conflict by adding a row to",
             "`inputs/market_links.csv` with `resolution` set to `keep` or `drop` and a note. The producer's own page wins unless a person decides otherwise.", ""]
    counts = {s: len(v) for s, v in by_state.items()}
    lines.append("Links by state: " + ", ".join("%s %d" % (s, counts[s]) for s in sorted(counts)))
    lines.append("")
    lines.append("## Conflicts (hidden unless kept)")
    lines.append("")
    conflicts = sorted(by_state.get("conflict", []), key=lambda t: (t[0], t[1]))
    if not conflicts:
        lines.append("None.")
    for pname, mname, l in conflicts:
        lines.append("- **%s** at **%s**: %s (%s)" % (pname, mname, l["link_note"], "shown" if l["shown"] == "true" else "hidden"))
    lines += ["", "## Listed by the producer's page only", ""]
    for pname, mname, l in sorted(by_state.get("producer_only", []), key=lambda t: (t[0], t[1])):
        lines.append("- **%s** at **%s** (page checked %s)" % (pname, mname, l["producer_checked_on"] or "date not recorded"))
    lines += ["", "## Listed by a market's vendor list, producer's page not checked or silent", ""]
    for pname, mname, l in sorted(by_state.get("market_only", []), key=lambda t: (t[0], t[1])):
        if l["link_note"]:
            lines.append("- **%s** at **%s**: %s" % (pname, mname, l["link_note"]))
    lines.append("")
    lines.append("(%d market-list-only links have no note: the producer's page has not been checked yet.)" % sum(
        1 for t in by_state.get("market_only", []) if not t[2]["link_note"]))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines) + "\n")
