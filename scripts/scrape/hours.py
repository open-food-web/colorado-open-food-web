"""Turn free-text opening hours into one structured row per day.

    parse("Mon: 8 am - 6 pm; Sat-Sun 10am-2pm")
    -> Parsed(status="parsed", slots=[Slot("mon","08:00","18:00"), Slot("sat","10:00","14:00"), Slot("sun","10:00","14:00")])

Rules: only what the text states outright becomes a slot; nothing is guessed. A time range with no am/pm
on its opening time borrows the closing time's ("10-2pm"); a range with no am/pm at all is not read.
`status` says how much was understood:

  parsed       every day and time in the text became a slot
  partial      some did; the original text is kept for the rest
  appointment  "by appointment" or similar, no times to read
  text_only    nothing could be read as day plus time
  none         no text

The original text is always kept next to the structured rows, so nothing is lost when a case is not understood.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAY_NAMES = {
    "mon": "mon", "monday": "mon", "tue": "tue", "tues": "tue", "tuesday": "tue", "wed": "wed", "weds": "wed",
    "wednesday": "wed", "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu", "fri": "fri",
    "friday": "fri", "sat": "sat", "saturday": "sat", "sun": "sun", "sunday": "sun",
}
_DAY = r"(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:s|nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
_SEP_RANGE = r"\s*(?:-|to|through|thru)\s*"
_SEP_LIST = r"\s*(?:,|/|&|\band\b)\s*"
_DAYS = rf"(?:{_DAY}(?:{_SEP_RANGE}{_DAY})?(?:{_SEP_LIST}{_DAY}(?:{_SEP_RANGE}{_DAY})?)*|daily|every\s*day|7\s*days(?:\s*a\s*week)?)"
_T = r"(?:\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?|[ap](?![a-z]))?|noon|midnight)"
_RANGE = rf"(?P<t1>{_T})\s*(?:-|to|until|till)\s*(?P<t2>{_T})"
_TZ = r"(?:\s*(?:MST|MDT|MT|CT|PT|ET))?"
_DAYS_FIRST = re.compile(rf"(?P<days>{_DAYS})\s*[:,]?\s*(?:open\s*)?{_RANGE}", re.I)
_TIME_FIRST = re.compile(rf"{_RANGE}{_TZ}\s*(?:on\s*)?(?P<days>{_DAYS})", re.I)
_MERIDIEM = re.compile(r"(a\.?m\.?|p\.?m\.?|[ap])\s*$", re.I)
_MORE = re.compile(rf"\s*(?:,|&|and)\s*{_RANGE}", re.I)
_CLOSED = re.compile(rf"(?P<days>{_DAYS})\s*[:,]?\s*closed", re.I)
_ANY_TIME = re.compile(r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)", re.I)
_ANY_DAY = re.compile(rf"\b{_DAY}\b|\bdaily\b", re.I)
_APPT = re.compile(r"by appointment|appointment only|call (?:ahead|first)|contact before", re.I)
_ALWAYS = re.compile(r"\b24\s*/\s*7\b|24\s*hours|open 24", re.I)


@dataclass
class Slot:
    day: str
    opens: str
    closes: str
    closes_next_day: bool = False
    inferred: bool = False   # am/pm was not written and was read from the usual shape of opening hours


@dataclass
class Parsed:
    status: str
    slots: List[Slot] = field(default_factory=list)


def _clock(tok: str, borrow: str = "") -> str | None:
    tok = tok.strip().lower()
    if tok == "noon":
        return "12:00"
    if tok == "midnight":
        return "00:00"
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?|[ap])?$", tok)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or borrow or "").replace(".", "").lower()
    if not ap or h > 12 or mi > 59 or h == 0:
        return None
    ap = ap[:1] + "m" if ap else ap
    if ap.startswith("p") and h != 12:
        h += 12
    if ap.startswith("a") and h == 12:
        h = 0
    return "%02d:%02d" % (h, mi)


def _expand_days(expr: str) -> List[str]:
    e = expr.lower().strip()
    if e in ("daily", "every day", "everyday") or e.startswith("7 days"):
        return list(DAY_ORDER)
    days: List[str] = []
    for part in re.split(_SEP_LIST, e, flags=re.I):
        rng = re.split(_SEP_RANGE, part.strip(), flags=re.I)
        rng = [r for r in rng if r]
        if len(rng) == 2 and rng[0] in _DAY_NAMES and rng[1] in _DAY_NAMES:
            a, b = DAY_ORDER.index(_DAY_NAMES[rng[0]]), DAY_ORDER.index(_DAY_NAMES[rng[1]])
            days += [DAY_ORDER[i % 7] for i in range(a, a + ((b - a) % 7) + 1)]
        elif len(rng) == 1 and rng[0] in _DAY_NAMES:
            days.append(_DAY_NAMES[rng[0]])
    seen = []
    for d in days:
        if d not in seen:
            seen.append(d)
    return seen


def _times(t1: str, t2: str):
    ap2 = _MERIDIEM.search(t2.strip())
    borrow = ap2.group(1).lower().replace(".", "") if ap2 else ""
    o = _clock(t1) or None
    if o is None and not _MERIDIEM.search(t1.strip()) and borrow:
        # "10-2pm": the opening time borrows the closing am/pm, unless that would put it after closing
        h1 = int(re.match(r"\d{1,2}", t1.strip()).group()) if re.match(r"\d{1,2}", t1.strip()) else 99
        h2 = int(re.match(r"\d{1,2}", t2.strip()).group()) if re.match(r"\d{1,2}", t2.strip()) else 0
        use = borrow if (h1 % 12) <= (h2 % 12) or borrow == "am" else "am"
        o = _clock(t1, use)
    c = _clock(t2)
    inferred = False
    if o is None or c is None:
        n1 = re.match(r"(\d{1,2})(?::(\d{2}))?\s*$", t1.strip())
        n2 = re.match(r"(\d{1,2})(?::(\d{2}))?\s*$", t2.strip())
        if not (n1 and n2):
            return None
        h1, h2 = int(n1.group(1)), int(n2.group(1))
        if not (1 <= h1 <= 12 and 1 <= h2 <= 12):
            return None
        open_pm = h1 == 12 or h1 <= 5
        close_pm = open_pm or h2 == 12 or h2 <= h1
        o = _clock(t1, "pm" if open_pm else "am")
        c = _clock(t2, "pm" if close_pm else "am")
        inferred = True
        if o is None or c is None:
            return None
    return o, c, c <= o, inferred


def parse(text: str | None) -> Parsed:
    raw = (text or "").strip()
    if not raw:
        return Parsed("none")
    s = raw.replace("�", "-").replace("–", "-").replace("—", "-").replace("‑", "-")
    s = re.sub(r"\s+", " ", s)
    if _ALWAYS.search(s):
        return Parsed("parsed", [Slot(d, "00:00", "24:00") for d in DAY_ORDER])

    slots: List[Slot] = []
    consumed = []
    for pat in (_DAYS_FIRST, _TIME_FIRST):
        for m in pat.finditer(s):
            if any(a < m.end() and m.start() < b for a, b in consumed):
                continue
            tm = _times(m.group("t1"), m.group("t2"))
            days = _expand_days(m.group("days"))
            if not tm or not days:
                continue
            end = m.end()
            ranges = [tm]
            while True:                       # "7:30am - 12pm, 1pm - 4:30pm": more blocks on the same days
                more = _MORE.match(s, end)
                t2 = _times(more.group("t1"), more.group("t2")) if more else None
                if not t2:
                    break
                ranges.append(t2)
                end = more.end()
            consumed.append((m.start(), end))
            for r in ranges:
                for d in days:
                    slots.append(Slot(d, r[0], r[1], r[2], r[3]))
    for m in _CLOSED.finditer(s):
        if not any(a < m.end() and m.start() < b for a, b in consumed):
            consumed.append((m.start(), m.end()))      # "Sun closed": nothing to record
    if not slots:
        return Parsed("appointment" if _APPT.search(s) else "text_only")
    # what is left over?
    rest = s
    for a, b in sorted(consumed, reverse=True):
        rest = rest[:a] + " " + rest[b:]
    leftover = bool(_ANY_TIME.search(rest) or re.search(rf"\b{_DAY}\b", rest, re.I))
    uniq = {}
    for sl in slots:
        uniq[(sl.day, sl.opens, sl.closes)] = sl
    ordered = sorted(uniq.values(), key=lambda x: (DAY_ORDER.index(x.day), x.opens))
    return Parsed("partial" if leftover else "parsed", ordered)
