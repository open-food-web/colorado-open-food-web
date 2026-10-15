"""Scrape a producer's published stockist table into supply-network links.

Many small Colorado producers list their stockists in a WordPress TablePress table
(<table class="tablepress">). This reads every such table on a page and writes one
row per stockist to source-data/supply-network/scraped/<source>.csv.

    python scripts/supply_network/stockists.py bee_squared
"""
import os
import csv
import html
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(os.environ.get("FOODWEB_SOURCES") or (Path(__file__).resolve().parents[2].parent / "colorado-open-food-web-sources"))
OUT_DIR = SRC_ROOT / "source-data" / "supply-network" / "scraped"

# source key -> (supplier name as in nodes.csv, stockist page URL)
SOURCES = {
    "bee_squared": ("Bee Squared Apiaries",
                    "https://bethsbees.com/local-sources-of-bee-squared-products/"),
}

UA = {"User-Agent": "Mozilla/5.0 (colorado-farm-trail supply-network research)"}


class TablePress(HTMLParser):
    """Collects rows of cell text (and the first link per cell) from tablepress tables."""

    def __init__(self):
        super().__init__()
        self.depth = 0          # >0 while inside a tablepress table
        self.rows, self.row, self.cell, self.href = [], None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and "tablepress" in (a.get("class") or ""):
            self.depth += 1
        elif self.depth and tag == "tr":
            self.row = []
        elif self.depth and tag in ("td", "th"):
            self.cell, self.href = [], None
        elif self.depth and tag == "a" and self.cell is not None and not self.href:
            self.href = a.get("href")

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
        elif self.depth and tag in ("td", "th") and self.row is not None:
            self.row.append((" ".join("".join(self.cell).split()), self.href))
            self.cell = None
        elif self.depth and tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")  # some pages mix in Windows smart quotes


def scrape(key):
    supplier, url = SOURCES[key]
    p = TablePress()
    p.feed(fetch(url))
    header = [c[0].lower() for c in p.rows[0]]
    city_i = next(i for i, h in enumerate(header) if "city" in h)
    name_i = next(i for i, h in enumerate(header) if "location" in h or "store" in h or "name" in h)
    site_i = next((i for i, h in enumerate(header) if "web" in h), None)
    out, seen = [], set()
    for row in p.rows[1:]:
        city, name = row[city_i][0], html.unescape(row[name_i][0]).replace("�", "'")
        site = (row[site_i][1] or row[site_i][0]) if site_i is not None else ""
        site = re.sub(r"[?&](srsltid|SEO_id|y_source)=[^&]*", "", site).rstrip("/") + "/" if site else ""
        if not name or (name, city) in seen:
            continue
        seen.add((name, city))
        out.append({"supplier": supplier, "buyer": name, "buyer_city": city,
                    "buyer_website": site, "source": url, "scraped": date.today().isoformat()})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{key}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{key}: {len(out)} stockists -> {path.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    for k in sys.argv[1:] or SOURCES:
        scrape(k)
