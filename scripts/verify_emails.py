#!/usr/bin/env python3
"""Verify that each published email is listed on the business's own website, and scrub the rest.

  python scripts/verify_emails.py --from-build [--limit N] [--workers 6]
      Check every (email, website) pair in the last build (.cache/build/co_farmers_markets_all_raw.csv)
      that has not been checked recently. Results go to inputs/email_verification.csv.

  python scripts/verify_emails.py --scrub
      One-time clean-up of committed files: blank every email that is not verified. Also run by the
      guard test's error message if an unverified address slips into the repo.

See scripts/scrape/contact_policy.py for what counts as verified.
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scrape import contact_policy as cp  # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, ".."))
SCRUB_DIRS = ["inputs", "snapshots", "data", "exports", "scripts/tests"]
SCRUB_EXT = (".csv", ".json", ".md")


def pairs_from_build(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [(r["Email"], r["Website"]) for r in csv.DictReader(fh) if r["Email"].strip()]


def tracked_files():
    for d in SCRUB_DIRS:
        for root, dirs, files in os.walk(os.path.join(REPO, d)):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".cache")]
            for f in files:
                if f.endswith(SCRUB_EXT) and f != "email_verification.csv":
                    yield os.path.join(root, f)


def scrub(table):
    ok = table.verified_emails()
    changed = removed = 0
    for p in tracked_files():
        s = open(p, encoding="utf-8", newline="").read()
        n = 0

        def fix(m):
            nonlocal n
            e = m.group(0)
            if e.lower().rstrip(".") in ok or cp.ALWAYS_OK.search(e):
                return e
            n += 1
            return ""

        t = cp.EMAIL_RE.sub(fix, s)
        if n:
            open(p, "w", encoding="utf-8", newline="").write(t)
            changed += 1
            removed += n
    print(f"scrubbed {removed} unverified addresses in {changed} files")
    drop_emptied_overrides()


def drop_emptied_overrides():
    """An override that set an email to an address we then removed has no value left: delete the row."""
    p = os.path.join(REPO, "inputs", "overrides.csv")
    with open(p, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        fields, rows = rd.fieldnames, list(rd)
    keep = [r for r in rows if not (r["mode"] in ("set", "prepend") and not r["value"].strip())]
    if len(keep) != len(rows):
        with open(p, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(keep)
        print(f"dropped {len(rows) - len(keep)} email overrides whose address was removed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-build", nargs="?", const=os.path.join(REPO, ".cache", "build", "co_farmers_markets_all_raw.csv"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--scrub", action="store_true")
    ap.add_argument("--confirm", metavar="EMAIL", help="record an address a person saw on the business's own Facebook or Instagram page (needs --page)")
    ap.add_argument("--page", help="that page's URL, for --confirm")
    ap.add_argument("--website", default="", help="the business's website, if it has one, for --confirm")
    a = ap.parse_args()
    table = cp.Table()
    if a.confirm:
        if not a.page:
            ap.error("--confirm needs --page (the business's own Facebook or Instagram page)")
        print("confirmed:", a.confirm, "->", table.confirm_on_page(a.confirm, a.website, a.page))
        table.save()
    if a.from_build:
        pairs = pairs_from_build(a.from_build)
        if a.limit:
            pairs = pairs[: a.limit]
        cp.verify_many(pairs, table, a.workers, log=lambda m: print(m, flush=True))
        c = {}
        for r in table.rows.values():
            c[r["status"]] = c.get(r["status"], 0) + 1
        print("table:", c)
    if a.scrub:
        scrub(table)


if __name__ == "__main__":
    main()
