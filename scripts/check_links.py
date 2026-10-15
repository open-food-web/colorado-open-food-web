#!/usr/bin/env python3
"""Check Website / Facebook / Instagram links in the farm directory for dead URLs.

Two jobs:
  * Report which links are broken (default).
  * Optionally strip *definitively* broken links from the CSV (--apply).

Because Facebook/Instagram block bots (403/429/login walls), a link is only
treated as BROKEN when we can confirm it: HTTP 404/410, a dead domain (DNS
failure), or a refused/reset connection. Everything ambiguous (timeouts, 403,
429, 5xx) is kept and reported as UNCERTAIN so we never strip a valid link.

A third class, SUSPECT, catches links that load but no longer lead to the business:
a website that redirects to a different domain (hijacked, sold, or simply moved) or
serves a parked / for-sale / security-warning page. SUSPECT is for human review and
is never removed by --apply (a legitimate move to a new domain looks the same).

Usage (from repo root):
  python scripts/check_links.py           # check + write report, change nothing
  python scripts/check_links.py --apply   # also blank out BROKEN links in the CSV
  python scripts/check_links.py --csv data-compiled/phase2/co_farmers_markets_all_mymaps.csv       --report data-compiled/phase2/link_check_report.csv   # check another CSV

Stdlib only -- no third-party dependencies.
"""

import os
import argparse
import csv
import socket
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_map_data import social_url, website_url  # noqa: E402  (shared normalization)

REPO = Path(__file__).resolve().parent.parent
SRC_ROOT = Path(os.environ.get("FOODWEB_SOURCES") or (Path(__file__).resolve().parents[1].parent / "colorado-open-food-web-sources"))
CSV_PATH = SRC_ROOT / "data-compiled" / "farm_fresh_directory_mymaps.csv"
REPORT_PATH = SRC_ROOT / "data-compiled" / "link_check_report.csv"

LINK_COLS = ("Website", "Facebook", "Instagram")
SOCIAL_BASE = {"Facebook": "https://facebook.com/", "Instagram": "https://instagram.com/"}
SOCIAL_HOSTS = ("facebook.com", "fb.com", "instagram.com")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 15
WORKERS = 16

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE  # ignore cert issues -> fewer false "dead" calls


# Page text that means "this isn't the business's site any more".
PARKED_MARKERS = (
    "domain is for sale", "this domain may be for sale", "buy this domain",
    "domain for sale", "is parked free", "domain parking", "parked domain",
    "sedoparking", "hugedomains", "dan.com", "afternic", "potential threat detected",
    "this site can't be reached", "account suspended", "website is no longer available",
)


def _base_domain(host):
    """'www.shop.example.com' -> 'example.com' (good enough for redirect checks)."""
    host = (host or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def suspect_reason(url, final_url, body):
    """Why a page that loaded is probably not the business any more, or None."""
    a, b = _base_domain(urlsplit(url).netloc), _base_domain(urlsplit(final_url or url).netloc)
    if b and a != b:
        return f"redirects to {b}"
    text = (body or "").lower()
    for marker in PARKED_MARKERS:
        if marker in text:
            return f"page says '{marker}'"
    return None


def is_social(url):
    u = url.lower()
    return any(h in u for h in SOCIAL_HOSTS)


def _request(url, method):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL)


def check_url(url):
    """Return (status, detail). status in {OK, SUSPECT, BROKEN, UNCERTAIN}."""
    # Syntactically invalid URLs can never load -> broken, no need to hit the network.
    if any(ch.isspace() for ch in url):
        return "BROKEN", "malformed (whitespace)"
    parts = urlsplit(url)
    if not parts.netloc or "." not in parts.netloc:
        return "BROKEN", "malformed (no host)"

    social = is_social(url)
    for attempt in (1, 2):  # one retry to smooth over transient hiccups
        try:
            if social:
                try:
                    resp = _request(url, "HEAD")
                except urllib.error.HTTPError as e:
                    # Some servers reject HEAD (405) -> retry with GET.
                    if e.code in (403, 405, 400, 429):
                        resp = _request(url, "GET")
                    else:
                        raise
                code = getattr(resp, "status", resp.getcode())
                return "OK", f"{code}"
            # Websites: GET, so we can see where it really lands and what it says.
            resp = _request(url, "GET")
            code = getattr(resp, "status", resp.getcode())
            try:
                body = resp.read(65536).decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                body = ""
            why = suspect_reason(url, resp.geturl(), body)
            return ("SUSPECT", why) if why else ("OK", f"{code}")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return "BROKEN", f"HTTP {e.code}"
            # 403/401/429/5xx -> could be bot-block or transient; keep it.
            if attempt == 2:
                return "UNCERTAIN", f"HTTP {e.code}"
        except urllib.error.URLError as e:
            reason = e.reason
            name = type(reason).__name__ if not isinstance(reason, str) else reason
            # A TLS handshake failure -> unreachable in a real browser (we already
            # disabled cert verification, so this is a protocol/cipher failure such as
            # ERR_SSL_VERSION_OR_CIPHER_MISMATCH, not a fixable cert-trust warning).
            if isinstance(reason, ssl.SSLError):
                return "BROKEN", "SSLError"
            # Dead domain / refused connection -> broken (but not for social hosts,
            # whose domains always resolve; a dead social page shows up as 404).
            if not social and isinstance(reason, (socket.gaierror, ConnectionRefusedError,
                                                  ConnectionResetError)):
                return "BROKEN", f"{name}"
            if attempt == 2:
                return "UNCERTAIN", f"{name}"
        except (socket.timeout, TimeoutError):
            if attempt == 2:
                return "UNCERTAIN", "timeout"
        except Exception as e:  # noqa: BLE001 - defensive; never crash the sweep
            if attempt == 2:
                return "UNCERTAIN", type(e).__name__
    return "UNCERTAIN", "unknown"


def main():
    global CSV_PATH, REPORT_PATH
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Blank out BROKEN links in the CSV (default: report only).")
    ap.add_argument("--csv", type=Path, default=CSV_PATH, help="CSV to check (default: live map file)")
    ap.add_argument("--report", type=Path, default=REPORT_PATH, help="Where to write the report CSV")
    args = ap.parse_args()
    CSV_PATH, REPORT_PATH = args.csv.resolve(), args.report.resolve()

    if not CSV_PATH.exists():
        sys.exit(f"ERROR: {CSV_PATH} not found")

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Normalize each link cell exactly as the map does (build_map_data), so we
    # validate the URL the site actually uses -- not the raw cell.
    # target = (row_index, col, raw_value, normalized_link_or_None)
    targets = []
    for i, row in enumerate(rows):
        for col in LINK_COLS:
            raw = (row.get(col) or "").strip()
            if not raw:
                continue
            link = website_url(raw) if col == "Website" else social_url(raw, SOCIAL_BASE[col])
            targets.append((i, col, raw, link))

    # Network-check the unique normalized URLs (dedupe so we hit each once).
    unique = sorted({t[3] for t in targets if t[3]})
    print(f"Checking {len(unique)} unique URLs across {len(rows)} records "
          f"({len(targets)} link cells)...\n")
    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for url, res in zip(unique, pool.map(check_url, unique)):
            results[url] = res

    # Classify every cell: unfixable normalization (name/none) -> BROKEN.
    classified = []  # (status, detail, i, col, raw, link)
    for i, col, raw, link in targets:
        if link is None:
            status, detail = "BROKEN", "not a usable URL"
        else:
            status, detail = results[link]
        classified.append((status, detail, i, col, raw, link))

    order = {"BROKEN": 0, "SUSPECT": 1, "UNCERTAIN": 2, "OK": 3}
    classified.sort(key=lambda t: (order[t[0]], t[3], t[4].lower()))
    broken = [c for c in classified if c[0] == "BROKEN"]
    uncertain = [c for c in classified if c[0] == "UNCERTAIN"]
    suspect = [c for c in classified if c[0] == "SUSPECT"]
    ok = [c for c in classified if c[0] == "OK"]

    with REPORT_PATH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Status", "Detail", "Column", "Raw value", "Normalized URL", "Business Name"])
        for status, detail, i, col, raw, link in classified:
            w.writerow([status, detail, col, raw, link or "", rows[i]["Business Name"]])

    print(f"  OK:        {len(ok)}")
    print(f"  SUSPECT:   {len(suspect)}  (loads, but redirects elsewhere / parked -- review)")
    print(f"  UNCERTAIN: {len(uncertain)}  (kept -- bot-block / timeout / 5xx)")
    print(f"  BROKEN:    {len(broken)}  (confirmed dead / not a usable URL)")
    print(f"\nFull report -> {REPORT_PATH.relative_to(REPO)}")

    def show(group, header):
        if not group:
            return
        print("\n" + header)
        for status, detail, i, col, raw, link in group:
            print(f"  [{detail:>22}] {col:9} {rows[i]['Business Name'][:34]:34} {raw!r}")

    show(broken, "Confirmed broken (will be removed with --apply):")
    show(suspect, "Suspect -- review each (NOT removed; a legitimate domain move looks the same):")
    show(uncertain, "Uncertain (review manually, NOT removed):")

    if args.apply and broken:
        for _s, _d, i, col, raw, _link in broken:
            if (rows[i].get(col) or "").strip() == raw:
                rows[i][col] = ""
        with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"\n--apply: blanked {len(broken)} broken link cell(s) in {CSV_PATH.name}.")
        print("Now regenerate the map data:  python scripts/build_map_data.py")
    elif args.apply:
        print("\n--apply: nothing to remove.")
    else:
        print("\n(report only -- rerun with --apply to strip the BROKEN links)")


if __name__ == "__main__":
    main()
