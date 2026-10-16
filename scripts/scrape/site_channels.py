"""Propose sales channels from a producer's own website (pilot).

Reads the home page and up to 4 same-site pages that look like they describe selling (shop, CSA,
farm stand, visit, wholesale...), and records, per channel, the page that mentions it and a short
matched phrase (under 15 words, a factual pointer, not copied prose). Output is a PROPOSAL file in
inputs/enrichment/; nothing is written to sales_channels. A channel with no evidence stays unknown;
absence of a phrase never means "none". A negated phrase ("no farm stand") is not evidence.

    python -m scripts.scrape.site_channels --county 08013 [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import html as htmllib
import os
import re
import time
import urllib.parse
from typing import Dict, List, Tuple

from . import contact_policy as cp

REPO = cp.REPO
OUT_DIR = os.path.join(REPO, "inputs", "enrichment")
FIELDS = ["producer_id", "channel", "evidence_url", "confidence", "matched_phrase"]
STATUS_FIELDS = ["producer_id", "website", "status", "pages", "channels", "seconds"]
DELAY = 1.5
MAX_PAGES = 5      # home + 4

PAGE_LINK = re.compile(r"shop|store|csa|share|u-?pick|pick-?your|farm-?stand|farm-?store|visit|order|buy|"
                       r"deliver|wholesale|market|products|purchase|where", re.I)

# (channel, confidence, regex). "high" = the phrase names the channel itself; "medium" = suggestive.
RULES: List[Tuple[str, str, "re.Pattern"]] = [(c, conf, re.compile(rx, re.I)) for c, conf, rx in [
    ("farm_stand", "high", r"farm[\s-]?stand|farmstand|farm[\s-]?store|farm[\s-]?shop|on[\s-]farm (?:store|stand|sales|shop)|roadside stand"),
    ("u_pick", "high", r"\bu[\s-]?pick\b|\byou[\s-]?pick\b|pick[\s-]your[\s-]own|\bPYO\b"),
    ("csa", "high", r"\bCSA\b|community[\s-]supported agriculture|farm share|harvest share|(?:veggie|vegetable|flower|meat|egg) share"),
    ("online", "high", r"online (?:store|shop|ordering|orders?)|order online|shop online|add to cart|web ?store|buy online"),
    ("pickup", "high", r"(?:order|curbside|farm|csa|share|local) pick[\s-]?up|pick[\s-]?up (?:location|day|site|time|window)s?"),
    ("delivery", "high", r"(?:home|local|free|weekly|doorstep) delivery|we deliver|delivery (?:available|area|day|zone)s?|delivers? (?:to|within)"),
    ("wholesale", "high", r"wholesale"),
    ("farmers_market", "medium", r"(?:find us|sell|selling|vendors?|booth|sold|available|join us|see us) (?:at|in) (?:the |our |several |local |these )?(?:[\w'’-]+ ){0,3}farmers[’']?\s?markets?|farmers[’']?\s?markets? (?:schedule|vendor|booth)"),
]]
NEGATION = re.compile(r"\b(?:no|not|never|without|n['’]t|isn['’]t|don['’]t|doesn['’]t|aren['’]t|longer|closed|cancel(?:l)?ed|sold out|waitlist|full)\b", re.I)


def to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", page)
    page = re.sub(r"(?is)<!--.*?-->", " ", page)
    text = re.sub(r"<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()


def phrase_around(text: str, m: "re.Match", pad: int = 3, cap: int = 14) -> str:
    before = text[:m.start()].split()[-pad:]
    after = text[m.end():].split()[:pad]
    words = before + m.group(0).split() + after
    if len(words) > cap:
        words = m.group(0).split()[:cap]
    return " ".join(words)


def find_evidence(text: str) -> Dict[str, Tuple[str, str]]:
    """channel -> (confidence, matched phrase) for the first non-negated mention."""
    out: Dict[str, Tuple[str, str]] = {}
    for channel, conf, rx in RULES:
        for m in rx.finditer(text):
            before = re.split(r"[.!?]", text[max(0, m.start() - 40):m.start()])[-1]
            after = re.split(r"[.!?]", text[m.end():m.end() + 25])[0]
            if NEGATION.search(before + " " + after):
                continue
            out[channel] = (conf, phrase_around(text, m))
            break
    return out


def candidate_pages(home_url: str, home_html: str) -> List[str]:
    base = urllib.parse.urlparse(home_url)
    seen, found = {home_url.rstrip("/")}, []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', home_html, re.I | re.S):
        href, label = m.group(1).strip(), re.sub(r"<[^>]+>", " ", m.group(2))
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        u = urllib.parse.urljoin(home_url, href).split("#")[0]
        p = urllib.parse.urlparse(u)
        if p.netloc.replace("www.", "") != base.netloc.replace("www.", ""):
            continue
        if re.search(r"\.(?:jpe?g|png|gif|pdf|webp|zip)$", p.path, re.I):
            continue
        if PAGE_LINK.search(p.path) or PAGE_LINK.search(label):
            key = u.rstrip("/")
            if key not in seen:
                seen.add(key)
                found.append(u)
    return found[: MAX_PAGES - 1]


def classify_site(website: str, fetch=cp._get, allowed=cp._allowed, sleep=time.sleep,
                  delay: float = DELAY) -> Tuple[str, int, Dict[str, Tuple[str, str, str]]]:
    """-> (status, pages_read, {channel: (confidence, evidence_url, phrase)})."""
    w = website.strip()
    if "//" not in w:
        w = "http://" + w
    if not allowed(w):
        return "robots_blocked", 0, {}
    html = fetch(w)
    if html is None and w.startswith("http://"):
        sleep(delay)
        html = fetch("https://" + w[len("http://"):])
        if html is not None:
            w = "https://" + w[len("http://"):]
    if html is None:
        return "unreachable", 0, {}
    found: Dict[str, Tuple[str, str, str]] = {}
    pages = 1

    def absorb(url: str, page: str) -> None:
        for ch, (conf, phrase) in find_evidence(to_text(page)).items():
            if ch not in found or (found[ch][0] == "medium" and conf == "high"):
                found[ch] = (conf, url, phrase)

    absorb(w, html)
    for u in candidate_pages(w, html):
        if not allowed(u):
            continue
        sleep(delay)
        page = fetch(u)
        pages += 1
        if page:
            absorb(u, page)
    return "ok", pages, found


def producers_in_county(fips: str, repo: str = REPO) -> List[dict]:
    d = os.path.join(repo, "data", "colorado")

    def rd(name):
        with open(os.path.join(d, name), encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    county = {r["location_id"]: r["county_fips"] for r in rd("locations.csv")}
    ids = {r["producer_id"] for r in rd("producer_locations.csv") if county.get(r["location_id"]) == fips}
    return [p for p in rd("producers.csv") if p["producer_id"] in ids and p["website"].strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", required=True, help="county FIPS, e.g. 08013")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--all", action="store_true", help="include producers that already have sales_channels")
    a = ap.parse_args()
    prods = [p for p in producers_in_county(a.county) if a.all or not p["sales_channels"].strip()]
    prods = prods[: a.limit] if a.limit else prods
    os.makedirs(OUT_DIR, exist_ok=True)
    out_p = os.path.join(OUT_DIR, f"site_channels_{a.county}.csv")
    st_p = os.path.join(OUT_DIR, f"site_channels_{a.county}_status.csv")
    with open(out_p, "w", encoding="utf-8", newline="") as fo, open(st_p, "w", encoding="utf-8", newline="") as fs:
        wo = csv.DictWriter(fo, FIELDS, lineterminator="\n")
        wo.writeheader()
        ws = csv.DictWriter(fs, STATUS_FIELDS, lineterminator="\n")
        ws.writeheader()
        for i, p in enumerate(prods, 1):
            t0 = time.time()
            status, pages, found = classify_site(p["website"])
            for ch, (conf, url, phrase) in sorted(found.items()):
                wo.writerow({"producer_id": p["producer_id"], "channel": ch, "evidence_url": url,
                             "confidence": conf, "matched_phrase": phrase})
            ws.writerow({"producer_id": p["producer_id"], "website": p["website"], "status": status,
                         "pages": pages, "channels": ";".join(sorted(found)), "seconds": round(time.time() - t0, 1)})
            fo.flush()
            fs.flush()
            print(f"{i}/{len(prods)} {p['name']}: {status} {sorted(found)}", flush=True)


if __name__ == "__main__":
    main()
