> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# Link checking — dead / moved Website · Facebook · Instagram

The directory carries three link fields per record — `Website`, `Facebook`,
`Instagram`. Links rot: domains lapse, pages move, social handles get renamed.
This doc covers the tooling that exists today and the **backlog item** to automate
a low-weight weekly check.

## Tooling that exists

- **`scripts/build_map_data.py`** — normalizes links as it builds `data/markets.json`:
  - Adds a missing scheme (`bergharvest.com` → `https://bergharvest.com`).
  - Turns bare handles into URLs (`@growinggardensboulder`, `abundant.spaces`).
  - Drops values that can't form a valid link (business *names* in a link field,
    `none`, whitespace-mangled strings).
- **`scripts/check_links.py`** — checks every normalized link over the network and
  classifies each as **OK / UNCERTAIN / BROKEN**:
  - `python scripts/check_links.py` — report only; writes
    `data-compiled/link_check_report.csv`, changes nothing.
  - `python scripts/check_links.py --apply` — blanks **BROKEN** cells in
    `data-compiled/farm_fresh_directory_mymaps.csv`. Re-run
    `build_map_data.py` afterward to refresh the map data.
  - It only marks a link **BROKEN** when it can *confirm* it: HTTP 404/410, a dead
    domain (DNS failure), a refused connection, a TLS handshake failure
    (`SSLError` — e.g. `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`, which a browser can't
    click through), or an unusable/malformed value. Anything ambiguous (403, 429,
    timeout, 5xx) is **UNCERTAIN** and kept. Cert *trust* warnings (expired/wrong-host
    certs) are deliberately not flagged — verification is disabled so the content is
    still reachable with a click-through.

## One-time sweep already run *(2026-07-20)*

- Normalized ~105 scheme-less website links (were broken as relative hrefs on the map).
- Removed ~48 unusable/dead links: business names sitting in link fields, `none`,
  a couple of double-prefixed URLs, and network-confirmed dead domains
  (`entwisefarm.com` 404, `growgirlogirlorganics.com`, `Gvrfarmersmarket.com`).
- Removed 2 more websites confirmed dead by a browser (`ERR_SSL_VERSION_OR_CIPHER_MISMATCH`:
  `devriesproduce.com`, `threesistersfarmanddairy.com`).
- Result: `data/markets.json` has 138 website / 89 Facebook / 96 Instagram links,
  all well-formed.

## Phase 2 sweep *(2026-10-14)*

- Ran `check_links.py` on the Phase 2 dataset (2,209 link cells): 1,272 OK, 838 uncertain,
  79 broken, 20 suspect.
- Fixes go in `source-data/phase2/overrides.csv` (not `--apply`), so they survive pipeline
  rebuilds: 74 `clear` rows (62 dead websites, 7 hijacked or parked domains, 5 bad social
  cells) and 12 `set` rows (malformed social values repaired, e.g. `https://https://...`
  and bare handles). Handles repaired from bare text are unverified, since Facebook and
  Instagram block checks.
- `data-compiled/phase2/link_review.csv` lists 13 suspect redirects for a human decision
  (rebrands, acquisitions, hosted-store redirects).

## Known limitation — Facebook & Instagram can't be reliably validated

Facebook and Instagram **block automated requests** (HTTP 400/403/429 or a login
wall) regardless of whether the page exists. So an automated checker:

- **can** catch a clearly-dead social link (HTTP 404 on a nonexistent path, or a
  malformed value), and
- **cannot** confirm a *live* social page is still the right one, or catch a page
  that was quietly renamed/deleted behind the login wall.

Treat social results as advisory. Website links are checked reliably.

---

## Backlog: low-weight automated weekly check *(not built)*

Goal: catch newly-dead/moved links without babysitting, and **without** auto-editing
data (false-positive risk is real, especially for social).

**Proposed shape — GitHub Actions, weekly cron, report-only:**

- Schedule: `cron` once a week (e.g. Monday early AM), plus manual `workflow_dispatch`.
- Steps: check out repo → `python scripts/check_links.py` (report mode, **no `--apply`**)
  → upload `link_check_report.csv` as a run artifact.
- Surface results for a human: if any **BROKEN** links are found, open (or update) a
  single GitHub issue titled e.g. "Weekly link check — N broken" with the BROKEN +
  UNCERTAIN rows in the body. Keep it to one rolling issue, not one per run.
- Keep it cheap: stdlib-only script already; the whole run is a few hundred HEAD
  requests and finishes in ~2–4 min on a free runner.
- **Do not auto-remove.** A maintainer reviews the issue and runs
  `check_links.py --apply` + `build_map_data.py` locally (or via a follow-up PR)
  when the removals look right. Reassess auto-apply once we trust the signal.

**Design decisions to make when building it:**

- Where the canonical data lives by then (this runs against
  `data-compiled/farm_fresh_directory_mymaps.csv` today; the Phase-2 files under
  `data-compiled/phase2/` are separate and not yet live).
- Whether to also flag **moved** links (3xx redirect chains that land on a parked
  page or a different domain) — currently a redirect to 200 counts as OK.
- Notification channel (GitHub issue is the low-effort default; email/Slack later).

See also: [`DATA.md`](DATA.md) for the field schema.
