"""Small, dependency-free normalization + validation helpers shared by all sources."""
from __future__ import annotations

import re

# Colorado bounding box (generous), used to sanity-check coordinates.
CO_LAT = (36.9, 41.1)
CO_LON = (-109.2, -101.9)


# Mojibake: UTF-8 text that some source decoded as Windows-1252, so "it's" (curly
# apostrophe) arrives as "itâ€™s" and "Cañon" as "CaÃ±on". A run is a UTF-8 lead byte
# (Â-ô) followed by 1-3 continuation bytes as they look in cp1252.
_CP1252_HIGH = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"
_MOJIBAKE = re.compile("[Â-ô][-¿" + _CP1252_HIGH + "]{1,3}")


def _unmangle(m: "re.Match") -> str:
    run = m.group(0)
    try:
        raw = b"".join(c.encode("cp1252") if c in _CP1252_HIGH else bytes([ord(c)]) for c in run)
        return raw.decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError, ValueError):
        return run  # not mojibake after all (e.g. a real "Ã" followed by "©")


def fix_mojibake(s: str) -> str:
    """Repair UTF-8-read-as-cp1252 runs; leaves clean text untouched."""
    return _MOJIBAKE.sub(_unmangle, s) if s and _MOJIBAKE.search(s) else s


def pipes(s: str) -> str:
    """Turn a pipe-delimited source value into a clean comma-joined string."""
    return ", ".join(p.strip() for p in (s or "").split("|") if p.strip())


def phone(s: str) -> str:
    """Normalize a US phone to (XXX) XXX-XXXX. Returns '' if not 10 digits."""
    digits = re.sub(r"\D", "", s or "")
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"


def zipcode(s: str) -> str:
    """Return a 5-digit zip, or '' if not recoverable."""
    m = re.search(r"\b(\d{5})(?:-\d{4})?\b", s or "")
    return m.group(1) if m else ""


# ---- URLs ---------------------------------------------------------------------
# Shared with the live Phase 1 build (scripts/build_map_data.py imports website_url
# and social_url from here), so both pipelines apply the same rules.

# A plausible social handle: letters/digits and . _ - only (no spaces, no "&", etc.)
# Instagram handles may contain dots (e.g. "abundant.spaces"), so dots are allowed.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# Scheme-less values that already start with one of these are URLs missing "https://".
_SOCIAL_DOMAINS = ("facebook.com/", "www.facebook.com/", "m.facebook.com/", "fb.com/",
                   "instagram.com/", "www.instagram.com/")
FACEBOOK_BASE = "https://facebook.com/"
INSTAGRAM_BASE = "https://instagram.com/"


def _has_scheme(v):
    vl = v.lower()
    return vl.startswith("http://") or vl.startswith("https://")


def _normalize_scheme(v):
    """Lowercase just the scheme (e.g. HTTPS://Foo -> https://Foo); host case is left alone."""
    for scheme in ("https://", "http://"):
        if v[:len(scheme)].lower() == scheme:
            return scheme + v[len(scheme):]
    return v


def website_url(value):
    """Normalize a website cell into a usable URL, or None.

    Most cells are bare domains missing the scheme (e.g. "bergharvest.com") --
    those become https://. Names, "none", or anything with spaces -> None.
    """
    v = (value or "").strip()
    if not v or v.lower() == "none":
        return None
    if _has_scheme(v):
        return _normalize_scheme(v)
    if any(c.isspace() for c in v) or "." not in v:
        return None  # a business name, not a domain
    return "https://" + v


def social_url(value, base):
    """Normalize a social field (full URL or bare @handle) into a URL, or None.

    Bare cells that are actually business names (spaces, "&", apostrophes) can't
    form a valid link and return None rather than a broken URL.
    """
    v = (value or "").strip()
    if not v:
        return None
    if any(c.isspace() for c in v):
        return None  # a business name, not a link
    if _has_scheme(v):
        return _normalize_scheme(v)
    # Scheme-less but already a social URL, e.g. "facebook.com/x", "www.instagram.com/x".
    if v.lower().startswith(_SOCIAL_DOMAINS):
        return "https://" + v
    # A bare handle, e.g. "@growinggardensboulder", "berg.harvest", "abundant.spaces".
    handle = v.lstrip("@").strip("/")
    if not handle or "/" in handle or not _HANDLE_RE.match(handle):
        return None
    return base + handle


def _first(s: str, fn) -> str:
    """Apply fn to the first ','/';'-separated piece that yields a URL. Scraped cells
    sometimes list several ('www.yakmeat.us  , www.yaksale.com')."""
    for part in re.split(r"[,;]\s", s or ""):
        url = fn(part)
        if url:
            return url
    return ""


def clean_url(s: str) -> str:
    """Website value -> URL with an http(s) scheme, or '' for junk/names.
    Does not validate reachability."""
    return _first(s, website_url)


def facebook_url(s: str) -> str:
    """Facebook value (URL, scheme-less URL or handle) -> URL, or '' for page names."""
    return _first(s, lambda v: social_url(v, FACEBOOK_BASE))


def instagram_url(s: str) -> str:
    """Instagram value (URL, scheme-less URL or @handle) -> URL, or '' for page names."""
    return _first(s, lambda v: social_url(v, INSTAGRAM_BASE))


def name_key(name: str) -> str:
    """Collapse a market name to a comparison key: lowercase, strip punctuation and
    common filler words so 'Pueblo Farmers Market' == 'Pueblo Farmers' Market'."""
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    stop = {"farmers", "farmer", "market", "markets", "the", "at", "of", "co",
            "colorado", "downtown", "community", "inc", "llc"}
    toks = [t for t in s.split() if t and t not in stop]
    return " ".join(sorted(toks)) if toks else re.sub(r"\s+", " ", s).strip()


def in_colorado(lat, lon) -> bool:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return CO_LAT[0] <= lat <= CO_LAT[1] and CO_LON[0] <= lon <= CO_LON[1]


def titlecase(s: str) -> str:
    """Title-case an ALL-CAPS source value ('1522 CALIFORNIA ST' -> '1522 California St')
    without mangling numbers. Leaves already-mixed-case strings alone."""
    s = (s or "").strip()
    if not s or s != s.upper():   # only touch strings that are all-caps
        return s
    return " ".join(w.capitalize() for w in s.split())


def yesno(s: str) -> str:
    """Normalize assorted truthy/falsy source values to 'Yes'/'No'/''."""
    v = (s or "").strip().lower()
    if v in ("yes", "y", "true", "1", "accepted", "available"):
        return "Yes"
    if v in ("no", "n", "false", "0", "not accepted", "unavailable"):
        return "No"
    return ""
