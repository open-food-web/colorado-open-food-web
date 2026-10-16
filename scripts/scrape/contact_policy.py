"""Which email addresses may be published: only those the business itself lists on its own website.

A directory listing is not enough (the business may never have chosen to publish it, and many sole
proprietors' addresses are personal). Each (email, website) pair is checked once, passively: fetch the
home page and a few contact-style pages on the business's own site and look for the exact address,
including common obfuscations. Results are kept in inputs/email_verification.csv, so a pair is not
checked again until it is stale. An address that cannot be confirmed is not kept in committed files.

Verified addresses are stored in the clear (they are public on the business's site). Anything not
verified is stored only as a hash, enough to avoid re-checking it, never the address.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import html as htmllib
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Optional, Tuple

from .useragent import USER_AGENT

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
VERIFY_CSV = os.path.join(REPO, "inputs", "email_verification.csv")
FIELDS = ["email", "email_hash", "host", "status", "found_url", "checked_on"]

VERIFIED = "verified"
VERIFIED_SOCIAL = "verified_facebook"   # listed on the business's own Facebook page
VERIFIED_INSTAGRAM = "verified_instagram"   # listed on the business's own Instagram page
CONFIRMED = (VERIFIED, VERIFIED_SOCIAL, VERIFIED_INSTAGRAM)
SOCIAL_STATUS = {"facebook.com": VERIFIED_SOCIAL, "instagram.com": VERIFIED_INSTAGRAM}
RECHECK_VERIFIED_DAYS = 180     # a verified address is re-confirmed twice a year
RECHECK_OTHER_DAYS = 45         # one that was not found gets another look sooner
MAX_PAGES = 5
MAX_BYTES = 600_000
TIMEOUT = 15

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
# Not business contacts: project, partner-neutral and placeholder addresses allowed anywhere.
ALWAYS_OK = re.compile(r"(@users\.noreply\.github\.com$|@example\.(com|org|test)$|^noreply@|^coloradofarmtrail@gmail\.com$|@github\.com$)", re.I)
CONTACT_LINK = re.compile(r"contact|about|reach|connect|find-?us|visit|location|hours|order|shop|farm-?stand", re.I)


def split_emails(cell: str) -> List[str]:
    """A source cell may hold several addresses ("a@example.org*b@example.org"); each is judged on its own."""
    return list(dict.fromkeys(e.lower().rstrip(".") for e in EMAIL_RE.findall(cell or "")))


def _today() -> str:
    return _dt.date.today().isoformat()


def ehash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]


def host_of(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if "//" not in u:
        u = "http://" + u
    h = urllib.parse.urlparse(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


# ---- the verification table --------------------------------------------------------

class Table:
    def __init__(self, path: str = VERIFY_CSV):
        self.path = path
        self.rows: Dict[Tuple[str, str], dict] = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    self.rows[(r["email_hash"], r["host"])] = r

    def get(self, email: str, website: str) -> Optional[dict]:
        return self.rows.get((ehash(email), host_of(website)))

    def put(self, email: str, website: str, status: str, found_url: str = "") -> None:
        self.rows[(ehash(email), host_of(website))] = {
            "email": email.strip().lower() if status in CONFIRMED else "",
            "email_hash": ehash(email), "host": host_of(website), "status": status,
            "found_url": found_url if status in CONFIRMED else "", "checked_on": _today()}

    def confirm_on_page(self, email: str, website: str, page_url: str) -> str:
        """A person has seen `email` on the business's own Facebook or Instagram page (neither can be read by a script).
        Records it, with that page, as confirmed. Returns the status. Any other page is refused: only the business's
        own website (checked by a script) or its Facebook or Instagram page counts."""
        host = (urllib.parse.urlparse(page_url).netloc or "").lower()
        host = host[4:] if host.startswith("www.") else host
        status = SOCIAL_STATUS.get(host)
        if not status or not urllib.parse.urlparse(page_url).path.strip("/"):
            raise ValueError("expected the business's own page on facebook.com or instagram.com, got %r" % page_url)
        self.put(email, website, status, page_url)
        return status

    def is_verified(self, email: str, website: str) -> bool:
        r = self.get(email, website)
        return bool(r and r["status"] in CONFIRMED)

    def verified_emails(self) -> set:
        return {r["email"] for r in self.rows.values() if r["status"] in CONFIRMED and r["email"]}

    def stale(self, email: str, website: str, today: Optional[_dt.date] = None) -> bool:
        r = self.get(email, website)
        if not r:
            return True
        today = today or _dt.date.today()
        age = (today - _dt.date.fromisoformat(r["checked_on"])).days
        return age > (RECHECK_VERIFIED_DAYS if r["status"] in CONFIRMED else RECHECK_OTHER_DAYS)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            for k in sorted(self.rows, key=lambda k: (self.rows[k]["host"], self.rows[k]["email_hash"])):
                w.writerow(self.rows[k])


# ---- finding an address in a page --------------------------------------------------

def _cf_decode(hexstr: str) -> str:
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except ValueError:
        return ""


def emails_in(page: str) -> set:
    """Every address a page shows, including mailto links, HTML entities, Cloudflare-protected
    addresses and the usual 'name [at] domain [dot] com' spellings."""
    out = set()
    for m in re.finditer(r'data-cfemail="([0-9a-fA-F]+)"', page):
        out.add(_cf_decode(m.group(1)).lower())
    for m in re.finditer(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)", page):
        out.add(_cf_decode(m.group(1)).lower())
    text = htmllib.unescape(page)
    text = urllib.parse.unquote(text)
    text = re.sub(r"<[^>]+>", " ", text) + " " + text
    t2 = re.sub(r"\s*[\[(\{]\s*at\s*[\])\}]\s*", "@", text, flags=re.I)
    t2 = re.sub(r"\s*[\[(\{]\s*dot\s*[\])\}]\s*", ".", t2, flags=re.I)
    t2 = re.sub(r"\b(\S+)\s+at\s+(\S+)\s+dot\s+(\w+)\b", r"\1@\2.\3", t2, flags=re.I)
    for src in (text, t2):
        out.update(e.lower().rstrip(".") for e in EMAIL_RE.findall(src))
    out.discard("")
    return out


# ---- fetching ---------------------------------------------------------------------

_robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}


def _allowed(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                rp.parse(r.read(100_000).decode("utf-8", "replace").splitlines())
            _robots[base] = rp
        except Exception:
            _robots[base] = None     # no readable robots.txt: nothing is disallowed
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def _get(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype and ctype:
                return None
            return r.read(MAX_BYTES).decode("utf-8", "replace")
    except Exception:
        return None


def _candidates(home_url: str, home_html: str) -> List[str]:
    base = urllib.parse.urlparse(home_url)
    seen, out = {home_url.rstrip("/")}, []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', home_html, re.I | re.S):
        href, label = m.group(1).strip(), re.sub(r"<[^>]+>", " ", m.group(2))
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        u = urllib.parse.urljoin(home_url, href)
        p = urllib.parse.urlparse(u)
        if p.netloc.replace("www.", "") != base.netloc.replace("www.", ""):
            continue
        if CONTACT_LINK.search(p.path) or CONTACT_LINK.search(label):
            key = u.split("#")[0].rstrip("/")
            if key not in seen:
                seen.add(key)
                out.append(u.split("#")[0])
    for path in ("/contact", "/contact-us", "/about"):
        u = f"{base.scheme}://{base.netloc}{path}"
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def check_pair(email: str, website: str) -> Tuple[str, str]:
    """-> (status, found_url). status: verified | not_found | unreachable | robots_blocked | no_website."""
    email = email.strip().lower()
    w = (website or "").strip()
    if not w:
        return "no_website", ""
    if "//" not in w:
        w = "http://" + w
    if not _allowed(w):
        return "robots_blocked", ""
    html = _get(w)
    if html is None and w.startswith("http://"):
        html = _get("https://" + w[len("http://"):])
        if html is not None:
            w = "https://" + w[len("http://"):]
    if html is None:
        return "unreachable", ""
    if email in emails_in(html):
        return VERIFIED, w
    for i, u in enumerate(_candidates(w, html)[: MAX_PAGES - 1]):
        if not _allowed(u):
            continue
        time.sleep(0.5)
        page = _get(u)
        if page and email in emails_in(page):
            return VERIFIED, u
    return "not_found", ""


def verify_many(pairs: Iterable[Tuple[str, str]], table: Table, workers: int = 6, log=print) -> None:
    pairs = list(dict.fromkeys((e, w.strip()) for cell, w in pairs for e in split_emails(cell)))
    todo = [(e, w) for e, w in pairs if table.stale(e, w)]
    log(f"email verification: {len(pairs)} pairs, {len(todo)} to check")
    if not todo:
        return
    done = 0

    def work(p):
        e, w = p
        return p, check_pair(e, w)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (e, w), (status, url) in ex.map(work, todo):
            table.put(e, w, status, url)
            done += 1
            if done % 50 == 0:
                log(f"  {done}/{len(todo)} checked")
                table.save()
    table.save()


# ---- applying the policy ------------------------------------------------------------

def publishable(email: str, website: str, table: Table) -> bool:
    return bool(email) and (ALWAYS_OK.search(email) is not None or table.is_verified(email, website))


def apply(records, table: Optional[Table] = None, verify: bool = True, workers: int = 6, log=print) -> int:
    """Check any email not yet checked, then blank every email that is not verified.
    Works on Market records (.email, .website). -> number of emails blanked."""
    table = table or Table()
    if verify:
        verify_many(((r.email, r.website) for r in records if r.email), table, workers, log)
    blanked = 0
    for r in records:
        if not r.email:
            continue
        kept = [e for e in split_emails(r.email) if publishable(e, r.website, table)]
        new = "; ".join(kept)
        if new != r.email:
            blanked += len(split_emails(r.email)) - len(kept)
            r.email = new
    return blanked
