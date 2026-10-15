# Follow-ups

Things deliberately left for later, with enough detail to pick them up.

## Facebook verification: circle back

Status as of 2026-10-15: **about 60 of 210 Facebook pages checked**; the rest are queued.

An email can be published if it appears on the business's own website, or on the business's own
Facebook page (status `verified_facebook` in `inputs/email_verification.csv`). The website pass ran
first (about 330 of 618 pairs verified). The Facebook pass covers the pairs the website pass could not
confirm, for businesses with a Facebook link.

**Queue:** `inputs/facebook_queue.csv` (business, city, Facebook link, status). It holds no email
addresses, by design: an address we could not verify must not be stored here. So the follow-up pass reads
the email *from the Facebook page* and adopts it once the page is confirmed to be the business.

| Queue status | Count | Meaning / what to do |
|---|---|---|
| `queued` | 150 | Not checked yet. This is the work to resume |
| `none` | 37 | Page loads but lists no email. Nothing to do unless the page gains one |
| `unavail` | 12 | Facebook says the content is not available: dead or changed link. Find the current page or drop the link from the data |
| `different_email_listed` | 7 | The page lists an address that differs from ours. Confirm the page is the right business, then adopt the page's address (it is verified by definition) |
| `badlink` | 2 | Our "Facebook" field is not a Facebook page (a website, or the Facebook home page). Fix the data |
| `wrong_page` | 1 | Our link points at someone else's page (Inti Farms points to Linktree's page). Fix the data |

**How the pass was run** (repeat the same way): a read-only look at each public page in a signed-in Chrome,
one page at a time with about 6 seconds between pages, 10 pages per batch, reading only the page's
Intro/Details block for email addresses. It stops at any checkpoint, CAPTCHA or "temporarily blocked"
page and never signs in or interacts with anything. Logged-out, Facebook starts showing a login wall after
roughly 15 pages. Yield was about 10 percent clean matches, plus useful finds: wrong emails and dead links.

**To resume:** work through `queued` rows, record each result, and re-run
`python scripts/verify_emails.py --from-build` then `--scrub`.

## Other email gaps (after the website and Facebook passes)

| Group | Count | Idea |
|---|---|---|
| No website to check against | about 130 | Facebook (above), or the producer confirming their own record |
| Website loaded, address not found | about 120 | Some are JavaScript pages, contact forms or images that the check cannot read; re-check those in a real browser |
| Site unreachable | about 36 | Retry; the check re-tries these after 45 days automatically |
| Blocked by robots.txt | 5 | Respect it; leave unverified |

## Pipeline

Open items are listed at the end of [PIPELINE.md](PIPELINE.md): pull the full Colorado Proud layer, clear
nine stale overrides, make `build_tables.py` statewide, and ask CFMA about the MarketWurks endpoint.
