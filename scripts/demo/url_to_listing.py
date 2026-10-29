"""Demo: turn a producer's website URL into a Food Web style listing, and notice when it changes.

    python -m scripts.demo.url_to_listing https://example-farm.com
    python -m scripts.demo.url_to_listing https://example-farm.com --html card.html
    python -m scripts.demo.url_to_listing https://example-farm.com --from-file saved.html   # offline

What it does
  1. Reads the home page (and, for sales channels, up to 4 same-site pages) the same polite way the
     pipeline does: robots.txt respected, identifying user agent, 1.5 s between requests.
  2. Derives a listing from facts only: name, phone, address, hours, socials, a contact email (only if
     it is on the business's own page), sales channels with a short pointer to the page that says so,
     and product groups. No descriptions or other prose are copied.
  3. Saves a snapshot in .cache/demo/ (never committed). On the next run it diffs the new listing
     against the snapshot and reports what is new, changed or gone. A vanished field is a review item,
     never a deletion, as in the real pipeline.

This is a prototype for demonstration, not a source in sources.json; nothing here writes to data/.
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse
from typing import Dict, List, Optional

from scripts import products
from scripts.scrape import contact_policy as cp
from scripts.scrape import hours as hoursmod
from scripts.scrape import site_channels as sc

CACHE = os.path.join(cp.REPO, ".cache", "demo")
TIME_RANGE = re.compile(hoursmod._RANGE, re.I)
ADDR_RE = re.compile(r"(\d{1,6}\s+[A-Za-z0-9 .'#-]{3,60}?),?\s+([A-Z][A-Za-z .'-]{2,30}),?\s+(?:Colorado|CO)\.?,?\s+(\d{5})")
PHONE_RE = re.compile(r"(?<!\d)\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-](\d{4})(?!\d)")
SOCIAL = {"facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[A-Za-z0-9_.\-/]+", re.I),
          "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+/?", re.I)}
SOCIAL_SKIP = re.compile(r"/(?:sharer|share|plugins|tr|dialog|login|p|reel|explore)\b", re.I)
HOURS_HINT = re.compile(r"\bhours\b|open (?:daily|every|mon|tue|wed|thu|fri|sat|sun)", re.I)

# Fields that make up the listing and are compared between runs.
FIELDS = ["name", "phone", "email", "address", "hours_text", "facebook", "instagram",
          "sales_channels", "product_groups"]


def _meta(page: str, key: str) -> str:
    for m in re.finditer(r"<meta\b[^>]*>", page, re.I):
        tag = m.group(0)
        if re.search(rf'(?:property|name)=["\']{re.escape(key)}["\']', tag, re.I):
            c = re.search(r'content=["\']([^"\']*)["\']', tag, re.I)
            if c:
                return htmllib.unescape(c.group(1)).strip()
    return ""


def _jsonld(page: str) -> List[dict]:
    out: List[dict] = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.I | re.S):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                out.append(d)
                stack.extend(v for v in d.get("@graph", []) if isinstance(v, dict))
    return out


def _is_business(d: dict) -> bool:
    t = d.get("@type", "")
    t = " ".join(t) if isinstance(t, list) else str(t)
    return bool(re.search(r"LocalBusiness|Farm|Store|Restaurant|Organization|FoodEstablishment|Winery|Brewery", t))


def _fmt_phone(m: "re.Match") -> str:
    return f"({m.group(1)}) {m.group(2)}-{m.group(3)}"


def _own_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")


def _name_from(page: str, ld: List[dict], url: str) -> str:
    for d in ld:
        if _is_business(d) and d.get("name"):
            return str(d["name"]).strip()
    og = _meta(page, "og:site_name")
    if og:
        return og
    t = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    if t:
        title = re.sub(r"\s+", " ", htmllib.unescape(t.group(1))).strip()
        return re.split(r"\s+[|–—-]\s+", title)[0].strip()
    return _own_domain(url)


def _address_from(text: str, ld: List[dict]) -> str:
    for d in ld:
        a = d.get("address")
        if isinstance(a, dict) and a.get("streetAddress"):
            parts = [a.get("streetAddress"), a.get("addressLocality"), a.get("addressRegion"), a.get("postalCode")]
            return ", ".join(str(p).strip() for p in parts if p)
    m = ADDR_RE.search(text)
    return f"{m.group(1).strip()}, {m.group(2).strip()}, CO {m.group(3)}" if m else ""


def _hours_from(text: str, ld: List[dict]):
    """-> (hours_text, parsed). hours_text is the business's own short statement, kept verbatim."""
    for d in ld:
        spec = d.get("openingHours")
        if spec:
            raw = "; ".join(spec) if isinstance(spec, list) else str(spec)
            p = hoursmod.parse(raw)
            if p.slots:
                return raw, p
    for m in HOURS_HINT.finditer(text):
        snippet = text[m.start(): m.start() + 160]
        p = hoursmod.parse(snippet)
        if p.slots:
            # keep only the run of time ranges (each within 40 chars of the last), not the prose after it
            end = 0
            for t in TIME_RANGE.finditer(snippet):
                if t.start() - end > 40 and end:
                    break
                end = t.end()
            cut = snippet[:end].strip(" ,;:")
            return cut, hoursmod.parse(cut)
    return "", None


def _socials(page: str, own: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for key, rx in SOCIAL.items():
        for m in rx.finditer(page):
            u = m.group(0).rstrip("/")
            if not SOCIAL_SKIP.search(u) and len(u.split("/")) > 3:
                found[key] = u + ("/" if key == "instagram" else "")
                break
    return found


def _email_from(page: str, own: str) -> str:
    """An address printed on the business's own page counts as published (see docs/PIPELINE.md).
    Prefer one at the site's own domain; a free-mail address is taken only if it is the sole one."""
    found = sorted(cp.emails_in(page))
    for e in found:
        if e.split("@")[1].lower().replace("www.", "") == own:
            return e
    return found[0] if len(found) == 1 else ""


def derive_listing(url: str, home_html: str, fetch=cp._get, allowed=cp._allowed,
                   sleep=time.sleep, offline: bool = False) -> dict:
    text = sc.to_text(home_html).replace("–", "-").replace("—", "-")
    ld = _jsonld(home_html)
    own = _own_domain(url)
    hours_text, parsed = _hours_from(text, ld)
    phone = ""
    for d in ld:
        if _is_business(d) and d.get("telephone"):
            pm = PHONE_RE.search(str(d["telephone"]))
            phone = _fmt_phone(pm) if pm else str(d["telephone"])
            break
    if not phone:
        tel = re.search(r'href=["\']tel:([^"\']+)', home_html, re.I)
        pm = PHONE_RE.search(urllib.parse.unquote(tel.group(1))) if tel else PHONE_RE.search(text)
        phone = _fmt_phone(pm) if pm else ""

    channels: Dict[str, tuple] = {}
    status = "ok"
    if offline:
        for ch, (conf, phrase) in sc.find_evidence(text).items():
            channels[ch] = (conf, url, phrase)
    else:
        status, _, channels = sc.classify_site(url, fetch=fetch, allowed=allowed, sleep=sleep)

    social = _socials(home_html, own)
    listing = {
        "name": _name_from(home_html, ld, url),
        "website": url,
        "phone": phone,
        "email": _email_from(home_html, own),
        "address": _address_from(text, ld),
        "hours_text": hours_text,
        "hours": [{"day": s.day, "opens": s.opens, "closes": s.closes} for s in parsed.slots] if parsed else [],
        "hours_status": parsed.status if parsed else "none",
        "facebook": social.get("facebook", ""),
        "instagram": social.get("instagram", ""),
        "sales_channels": sorted(channels),
        "channel_evidence": {ch: {"page": u, "phrase": ph, "confidence": conf}
                             for ch, (conf, u, ph) in sorted(channels.items())},
        "product_groups": products.from_text(text),
        "status": "unverified",
        "read_status": status,
    }
    return listing


def page_hash(home_html: str) -> str:
    return hashlib.sha256(sc.to_text(home_html).encode("utf-8")).hexdigest()[:16]


def diff(old: dict, new: dict) -> List[dict]:
    """Field-level changes. A field that vanished is flagged for review, not removed."""
    changes = []
    for f in FIELDS:
        a, b = old.get(f), new.get(f)
        if a == b:
            continue
        if a in ("", [], None):
            kind = "new"
        elif b in ("", [], None):
            kind = "gone (review)"
        else:
            kind = "changed"
        if isinstance(a, list) and isinstance(b, list) and kind == "changed":
            added, removed = sorted(set(b) - set(a)), sorted(set(a) - set(b))
            changes.append({"field": f, "kind": kind, "added": added, "removed": removed})
        else:
            changes.append({"field": f, "kind": kind, "old": a, "new": b})
    return changes


def snapshot_path(url: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", (_own_domain(url) + urllib.parse.urlparse(url).path).lower()).strip("-")
    return os.path.join(CACHE, key + ".json")


def run(url: str, home_html: str, offline: bool = False, save: bool = True, **kw) -> dict:
    listing = derive_listing(url, home_html, offline=offline, **kw)
    path = snapshot_path(url)
    prev = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            prev = json.load(fh)
    result = {"listing": listing, "page_hash": page_hash(home_html), "first_run": prev is None,
              "checked": time.strftime("%Y-%m-%d %H:%M:%S")}
    if prev:
        result["changes"] = diff(prev["listing"], listing)
        result["page_changed"] = prev["page_hash"] != result["page_hash"]
        result["previous_checked"] = prev.get("checked")
    if save:
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"listing": listing, "page_hash": result["page_hash"], "checked": result["checked"]},
                      fh, indent=2, ensure_ascii=False)
    return result


def render_text(r: dict) -> str:
    L = r["listing"]
    out = [f"{L['name']}", f"  {L['website']}", ""]
    for label, key in [("Phone", "phone"), ("Email", "email"), ("Address", "address"), ("Hours", "hours_text"),
                       ("Facebook", "facebook"), ("Instagram", "instagram")]:
        out.append(f"  {label:<10}{L[key] or '-'}")
    out.append(f"  {'Products':<10}{', '.join(L['product_groups']) or '-'}")
    out.append(f"  {'Sells via':<10}{', '.join(L['sales_channels']) or '-'}")
    for ch, ev in L["channel_evidence"].items():
        out.append(f"    {ch}: \"{ev['phrase']}\"  <- {ev['page']}")
    out.append("")
    if r["first_run"]:
        out.append("First look at this site: snapshot saved. Run again later to see what changed.")
    else:
        out.append(f"Compared with the snapshot from {r['previous_checked']}:")
        if not r["changes"]:
            out.append("  No listing fields changed" + (" (page text did change)." if r["page_changed"] else "."))
        for c in r["changes"]:
            if "added" in c:
                out.append(f"  ~ {c['field']}: +{c['added']} -{c['removed']}")
            else:
                out.append(f"  {'+' if c['kind'] == 'new' else '~'} {c['field']} [{c['kind']}]: {c['old']!r} -> {c['new']!r}")
    return "\n".join(out)


def render_html(r: dict) -> str:
    e = htmllib.escape
    L = r["listing"]
    rows = "".join(f"<tr><th>{e(k)}</th><td>{v}</td></tr>" for k, v in [
        ("Phone", e(L["phone"] or "-")), ("Email", e(L["email"] or "-")), ("Address", e(L["address"] or "-")),
        ("Hours", e(L["hours_text"] or "-")),
        ("Products", e(", ".join(L["product_groups"]) or "-")),
        ("Sells via", e(", ".join(L["sales_channels"]) or "-")),
        ("Facebook", f'<a href="{e(L["facebook"])}">{e(L["facebook"])}</a>' if L["facebook"] else "-"),
        ("Instagram", f'<a href="{e(L["instagram"])}">{e(L["instagram"])}</a>' if L["instagram"] else "-")])
    ev = "".join(f"<li><b>{e(c)}</b> &ldquo;{e(v['phrase'])}&rdquo; "
                 f'<a href="{e(v["page"])}">source</a></li>' for c, v in L["channel_evidence"].items())
    if r["first_run"]:
        chg = "<p>First look at this site. Snapshot saved; run again to see changes.</p>"
    elif not r["changes"]:
        chg = "<p>No listing fields changed since " + e(r["previous_checked"]) + ".</p>"
    else:
        chg = "<ul>" + "".join(
            f"<li><b>{e(c['field'])}</b> ({e(c['kind'])}): " +
            (f"+{e(str(c['added']))} &minus;{e(str(c['removed']))}" if "added" in c
             else f"{e(str(c['old']))} &rarr; {e(str(c['new']))}") + "</li>" for c in r["changes"]) + "</ul>"
    return f"""<!doctype html><meta charset="utf-8"><title>{e(L['name'])} - demo listing</title>
<style>body{{font:16px/1.5 system-ui;max-width:640px;margin:2rem auto;padding:0 1rem;color:#222}}
th{{text-align:left;padding-right:1rem;color:#666;font-weight:600;vertical-align:top}}
.tag{{display:inline-block;background:#fff3cd;padding:2px 8px;border-radius:4px;font-size:13px}}
.chg{{background:#eef6ee;border-left:4px solid #4a8;padding:.5rem 1rem;margin-top:1.5rem}}</style>
<h1>{e(L['name'])}</h1><p><a href="{e(L['website'])}">{e(L['website'])}</a> <span class="tag">unverified, auto-derived</span></p>
<table>{rows}</table><h3>Where the sales channels come from</h3><ul>{ev or '<li>none found</li>'}</ul>
<div class="chg"><h3>Changes since last check</h3>{chg}</div>
<p style="color:#888;font-size:13px">Demo output. Facts only; nothing copied from the site beyond short pointers.</p>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--from-file", help="read this saved HTML instead of fetching (offline demo)")
    ap.add_argument("--html", help="also write a listing card to this file")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--no-save", action="store_true", help="do not update the snapshot")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    url = a.url if "//" in a.url else "https://" + a.url
    if a.from_file:
        with open(a.from_file, encoding="utf-8") as fh:
            page = fh.read()
    else:
        if not cp._allowed(url):
            sys.exit("robots.txt disallows reading this page.")
        page = cp._get(url)
        if page is None:
            sys.exit("Could not read the page.")
    r = run(url, page, offline=bool(a.from_file), save=not a.no_save)
    print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else render_text(r))
    if a.html:
        with open(a.html, "w", encoding="utf-8") as fh:
            fh.write(render_html(r))
        print(f"\nWrote {a.html}")


if __name__ == "__main__":
    main()
