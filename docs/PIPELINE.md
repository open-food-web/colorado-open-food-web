# The update pipeline

How the Food Web keeps its data fresh. Sources are pulled on a schedule, each pull is reviewed as a
pull request, and the tables are rebuilt from the approved snapshots. See `UPDATE_ENGINE.md` in the
Colorado Farm Trail repo for the original design; this is the version that runs here.

```
 scheduled workflow ──> refresh_sources.py <source> ──> snapshots/<source>.json  (facts; notes as a hash)
   (one per source)                              └──> snapshots/changes/<source>.csv  (what is new, changed, removed)
                                  PR opened with both ──> a person merges = approves
 build.py  (snapshots + inputs/)  ──> .cache/build/*.csv  (never committed)  ──> build_tables.py ──> data/
```

## Where things live

Two repos, so the public one never holds other people's text:

| Repo | Visibility | Holds |
|---|---|---|
| `open-food-web/colorado-open-food-web` (this one) | public after the facts-only export | Code, schema, docs, `sources.json`, `snapshots/` (facts, notes as hash), `inputs/` (our own decisions and research), the tables in `data/`, the feedback and intake design |
| `open-food-web/colorado-open-food-web-sources` | **private** | Raw source material: saved vendor lists, source descriptions, Colorado Proud Finder profiles, CSA research with quoted evidence, Chaffee Provides pages, old compiled CSVs |

Scripts that read or write the private material find it through `FOODWEB_SOURCES` (a path to a
checkout of the sources repo), defaulting to a sibling folder named `colorado-open-food-web-sources`.

| Script | What it does | Reads | Writes |
|---|---|---|---|
| `scripts/scrape/refresh_sources.py` | Pull sources on schedule | the network | `snapshots/` |
| `scripts/scrape/build.py` | Merge snapshots and inputs | `snapshots/`, `inputs/` | `.cache/build/` |
| `scripts/build_tables.py` | Split into schema tables | `.cache/build/` | `data/` |
| `scripts/check_links.py` | Link health | sources repo `data-compiled/` | same |
| `scripts/build_places.py` | Census place and ZIP lookup | Census gazetteer | `inputs/places/` |
| `scripts/phase3/build_prospects.py` | Prospect list from market vendor lists | sources repo | sources repo |
| `scripts/csa/build_csa.py` | Validate CSA research, build the CSA dataset | sources repo | sources repo |
| `scripts/supply_network/*` | Supply-network edges, stockist scrapes, rechecks | `inputs/supply-network/` | same |
| `scripts/legacy/fetch_farm_data.py` | Phase 1 Colorado Proud pull (reference for the full-layer source) | the network | n/a |
| `intake/create_business_form.gs` | Google Apps Script for the public "add my business" form | n/a | n/a |

Partner corrections and additions are described in [FEEDBACK.md](FEEDBACK.md).

## Sources

Configured in [`sources.json`](../sources.json). A test keeps that file, the fetchers and the
workflow schedules in step.

| Source | Cadence | What is pulled | Requests per run |
|---|---|---|---|
| `colorado_proud` | weekly | Colorado Proud Farm Fresh Directory (ArcGIS feature service), farmers markets only | 1 |
| `usda_api` | weekly | USDA Local Food Portal keyed API, five directories (needs `USDA_API_KEY`) | 5, more if the grid fallback runs |
| `usda_datashare` | weekly | USDA Local Food Portal data-share feed, no key, gap filler | 5 |
| `cfma` | **monthly** | CFMA member markets, MarketWurks public API | 2 |
| `colorado_proud_finder` | **monthly** | Colorado Proud member directory: 6 listing pages plus profiles not seen before (1.5 s between requests) | 6 + new profiles |
| `chaffee_provides` | **retired** | Not pulled. The Chaffee prototype site now reads from the Food Web, so pulling from it would be circular. The last snapshot (37 records) is frozen and still built in. Corrections go in `inputs/overrides.csv` | 0 |

All requests identify themselves as `Mozilla/5.0 (compatible; ColoradoOpenFoodWeb/0.1; +https://github.com/open-food-web/colorado-open-food-web)`.
USDA's portal returns 403 to a bare custom agent, so the browser-compatible form is used; it still
names the project.

## What is committed, and what is not

- **Committed:** `snapshots/` (every fact field in the clear; the source's description text replaced by
  a hash, so a change in the text is detectable without keeping the text), `snapshots/changes/`,
  `inputs/` (our own decisions and research: overrides, dedup decisions, curated records,
  enrichment results without their notes, the geocode cache, the frozen Phase 1 Farm Fresh file),
  and the tables in `data/`.
- **Not committed:** `.cache/` (the Colorado Proud Finder profile cache, build intermediates with
  descriptions, reports). Third-party prose never enters the repo.

## Contact emails: published only if the business lists them

Sources hand us many email addresses, and some belong to people rather than businesses. The pipeline
publishes an address only if it appears on the business's own website.

- `scripts/scrape/contact_policy.py` checks each (email, website) pair once: the home page plus up to four
  contact-style pages on the same site, respecting robots.txt, looking for the exact address (including
  `mailto:` links, HTML entities, Cloudflare-protected addresses and "name [at] domain [dot] com" spellings).
- Results are in `inputs/email_verification.csv`. A **verified** address is stored in the clear with the page
  where it was found (it is public there). Anything else is stored only as a hash, so it is not re-checked
  but never appears in the repository. A verified address is re-confirmed after 180 days; one not found,
  after 45.
- `refresh_sources.py` runs the check on new addresses before saving a snapshot and leaves out any that are
  not confirmed. Records with no website cannot be verified, so they publish no email.
- A test (`test_no_committed_file_holds_an_unverified_email`) fails if any tracked file contains an address
  that is not verified. To fix it: `python scripts/verify_emails.py --from-build`, then `--scrub`.
- Project and partner-neutral addresses (GitHub noreply, `example.*`, the Farm Trail brand address) are exempt.

## Safety rules in the code

- A source that fails keeps its previous snapshot.
- **A pull that returns nothing, or under half the previous record count, is treated as failed** and
  keeps the previous snapshot (`ALLOW_SHRINK=1` overrides when a drop is real). Found during the
  October 2026 review: a blocked request produced "zero records" and replaced a good snapshot.
- A vanished listing is a review item in the change report, never a deletion.
- Nothing is applied until a person merges the PR.

## Review of the pipeline, 2026-10-15

First full run since the pipeline was built on 2026-10-03. Findings:

| Source | Result |
|---|---|
| Colorado Proud | Unchanged (48 records). |
| Colorado Proud Finder | 1,561 members, 923 in scope. 3 new (Carey's Cottage, JC Ranch and Livestock, Peak & Petal), 1 changed (Wildcraft Markets renamed and its coordinates removed). |
| USDA keyed API | 325 records, 5 changed (a Facebook link each). **Blocked at first**: a custom user agent got 403 and the old code saved the empty result over the snapshot. Fixed with the browser-compatible agent and the shrink guard above. |
| USDA data share | 106 records, unchanged. |
| CFMA | **API moved.** MarketWurks now serves the public data at `/public/api/<org>/vendor-profiles` and `/public/api/<org>/signup-form`; the old `/api/vendors/activeWithFields` returns 404. Response shapes are unchanged, so only the paths changed. 38 records now, 1 new (Montrose Farmers Market). The other 23 differences are Instagram link normalization, plus one corrupted Facebook link (`https://fhttps://…`) that is now empty. |
| Chaffee Provides | Retired (see above). |

Other findings:

- The Colorado Proud pull covers farmers markets only. The other ~500 Farm Fresh records come from a
  frozen Phase 1 file (`inputs/farm_fresh_legacy.csv`), so the largest part of the Colorado Proud data
  is not refreshed by any automated pull. **To do:** pull the full layer and carry the hand fixes in
  `inputs/overrides.csv`.
- Nine overrides report "record missing" on a build (for example Studt Farms, Adam's Apple Orchard).
  They were written against records the current build does not produce. **To do:** check whether the
  records were merged or renamed, and fix or retire the overrides.
- 31 records are flagged "Possible Dup Of" for review.
- The build reproduces the Farm Trail's output exactly (1,365 records, one product list differs).

## Running it by hand

```bash
python scripts/scrape/refresh_sources.py            # every active source
python scripts/scrape/refresh_sources.py cfma       # one source
python scripts/scrape/build.py                      # offline: snapshots + inputs -> .cache/build/
python -m pytest scripts/tests
```

`USDA_API_KEY` is read from the environment or a git-ignored `.env`. In GitHub it is an Actions secret.

## Still to do

- Add the `USDA_API_KEY` secret and allow Actions to open pull requests (repository settings).
- Statewide `build_tables.py` run (it is county-scoped today) as an automatic step after a merge.
- A source for the full Colorado Proud layer, and clearing the stale overrides.
- Ask CFMA about the MarketWurks endpoint before pulling more often than monthly.
