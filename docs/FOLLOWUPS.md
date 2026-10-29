# Follow-ups

Things deliberately left for later, with enough detail to pick them up.

## Facebook verification: circle back

Status as of 2026-10-15: **all 209 Facebook pages in the queue have been read once**; none are left `queued`.

An email can be published if it appears on the business's own website, or on the business's own
Facebook page (status `verified_facebook` in `inputs/email_verification.csv`). The website pass ran
first (about 330 of 618 pairs verified). The Facebook pass covers the pairs the website pass could not
confirm, for businesses with a Facebook link.

**Queue:** `inputs/facebook_queue.csv` (business, city, Facebook link, status). It holds no email
addresses, by design: an address we could not verify must not be stored here. The email is read
*from the Facebook page* and adopted once the page is confirmed to be the business (`--confirm`, plus an
`Email` row in `inputs/overrides.csv` with the note `via:facebook <page>`).

**Other facts seen on the pages** (phone, street address, hours, website, closures, who runs the page) are in
`inputs/facebook_findings.csv`, one row per page, as short factual notes with no emails and no copied text.
Only fields our record left blank were filled from them (some phones and websites); where a page and our
record disagree (many phones and addresses) nothing was changed, so the file is a worklist for a person.
Notable: Fresh Start Family Farms says on its page that it has moved out of Colorado; ArborScape Inc is a tree
service, not a food business; Go Fruita, the Town of Frederick and the Town of Mountain Village pages list a
staff or town address for markets they run, which was not adopted (it is not the market's own page).

| Queue status | Count | Meaning / what to do |
|---|---|---|
| `match` | 53 | The page lists an email for the business: adopted and verified (10 equalled the address we already had, 43 were new) |
| `none` | 107 | Page loads but lists no email. Nothing to do unless the page gains one |
| `unavail` | 29 | Facebook says the content is not available (dead, private or changed link; read while signed in to Chrome, so some may be restricted rather than gone). Find the current page or drop the link from the data |
| `different_email_listed` | 8 | The page lists an address that differs from the one we had. Page confirmed as the business and its address adopted (both kept where our own was already verified on the business's website) |
| `wrong_page` | 7 | Our link pointed at someone else's page or a personal profile. Facebook link cleared (Inti Farms' Linktree override removed) |
| `badlink` | 5 | Our "Facebook" field held a website, a photo link or the Facebook home page. Facebook link cleared |

**How the pass was run** (repeat the same way): a read-only look at each public page in a signed-in Chrome,
one page at a time with about 6 seconds between pages, 10 pages per batch, reading only the page's
Intro/Details block for email addresses. It stops at any checkpoint, CAPTCHA or "temporarily blocked"
page and never signs in or interacts with anything. Logged-out, Facebook starts showing a login wall after
roughly 15 pages. Yield was about 10 percent clean matches, plus useful finds: wrong emails and dead links.

**To repeat:** record each result, then re-run `python scripts/verify_emails.py --from-build` then `--scrub`,
`scripts/scrape/build.py` and `scripts/build_tables.py`. Next: the 29 `unavail` links, and a recheck of `none` rows in a few months.

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

## Events (later)

Dated events, such as the farm dinners Old Elm Farm hosts, are not on-farm channels: they have a date, a booking link and
often a price, and they belong in their own table (`events`: producer_id, title, starts, ends, url, source_url,
observed_on), shown on the producer's page and on an events view. Until then a producer that hosts events and
cannot be visited has only the `agritourism` channel and the events are noted in `visit_note`. Old Elm Farm is the first
example (maintainer, 2026-10-16).
