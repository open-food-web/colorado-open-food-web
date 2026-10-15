# Colorado Open Food Web

A free, open, community-maintained dataset of how Colorado's food connects: producers, markets and
outlets (restaurants, grocers, farm stores), the places they are at, and the counties they reach.
Read `docs/CHARTER.md` (what and why) and `docs/SCHEMA.md` (tables and fields) before changing anything.

## Decisions already made

- **Name:** Colorado Open Food Web. "Web" means the ecological food web (who feeds whom) and a dataset
  built by linking sources already on the web. A national spin-off would be "Open Food Web", with
  Colorado as the base model. Do not build multi-state features until the Colorado dataset works.
- **Record types (v1):** producers, markets (their own type, not producers), outlets (thin; dated,
  sourced supplier links), access points (community fridges for now), and locations (the physical
  places they are at, linked through `producer_locations`). Hubs, food banks and organizations are
  v2. Field-level detail is in `docs/SCHEMA.md`, which is the authority; if this file disagrees, the
  schema wins.
- **Release rules:** facts only. No copied descriptions or other third-party prose, no third-party
  photos (store only `google_place_id`), no personal information beyond what a business publishes
  for customers, honor `hide_address`. Records link to their sources instead of copying them.
  Emails are published only if the business lists the address on its own website (checked by
  `scripts/scrape/contact_policy.py`; see `docs/PIPELINE.md`). Never commit an unverified email.
- **Fields have classes** (`fact`, `controlled`, `owned`, `source_prose`, `personal`). The public
  export drops `source_prose` and `personal`.
- **License:** CC BY 4.0 for data and docs, MIT for code. Source-by-source terms review is still
  pending; do not publish anything from a source with unclear terms. Revisit share-alike (ODbL)
  before the first public data release.
- **Canonical format:** plain CSV tables in `data/`; JSON, GeoJSON and SQLite are built from them.
- **Colorado first, but neutral structure:** state is a field, counties use FIPS codes, IDs are
  namespaced (`co-p-`, `co-m-`, `co-o-`, `co-loc-`, `co-ploc-`).

## Where things are

- GitHub: `open-food-web/colorado-open-food-web` (private for now). Org `open-food-web` is owned by
  the `dbrown-code` account (renamed from `dbrown-creator` on 2026-10-15).
- The Colorado Farm Trail (`dbrown-code/colorado-farm-trail`, local `../colorado-farm-trail`) is the
  first app built on this data. The source-update pipeline now lives here (`scripts/scrape/`,
  `sources.json`, `snapshots/`, `inputs/`, scheduled workflows in `.github/workflows/`); see
  `docs/PIPELINE.md`. The Farm Trail keeps its old pipeline and raw scraped data as a legacy archive,
  to be reduced to app code only. Raw scraped third-party content must not go into this repo.
- Sources are pulled on their own schedules (CFMA and the Colorado Proud member crawl monthly, the
  rest weekly). **Chaffee Provides is retired as a source**: the Chaffee prototype site reads from
  the Food Web, so pulling from it would be circular. Its last snapshot is frozen; corrections go in
  `inputs/overrides.csv`.

## Git

- Push as `dbrown-code`. The remote URL carries the user (`https://dbrown-code@github.com/...`);
  the `david-n-brown` login has no write access. The gh CLI keyring entry may still be named
  `dbrown-creator`; `gh auth switch -u dbrown-creator` selects it. Other sessions also work in this
  repo, so use your own branch or worktree and check `git status` before committing.
- Work on short-lived branches and open a PR; the maintainer reviews and merges. Do not push to `main`
  directly once the repo is in use.
- Stage explicit paths. End commits with the Claude `Co-Authored-By` trailer and PR bodies with the
  Claude Code line.

## Pending

1. Source terms: Colorado Proud, CFMA/MarketWurks and Chaffee Provides state no data license; USDA's
   data.gov listing is CC BY but the API terms are unverified.
2. Full CC BY 4.0 `LICENSE` text (needs the maintainer's OK to download from creativecommons.org).
3. Governance document (decision-making, partner voice, removals), modeled partly on the Open Food
   Network handbook.
4. Facts-only export: `scripts/build_tables.py` is county-scoped today (Chaffee). Make it statewide,
   with prose and personal-field filters, and run it after a snapshot PR merges.
   Also: pull the full Colorado Proud layer (about 500 records still come from a frozen Phase 1
   file) and clear nine stale overrides (see `docs/PIPELINE.md`).
5. Partner outreach: regional projects like Chaffee Provides, after the README and two worked examples
   (Farm Trail, CSA finder) are ready.
6. Domain: `coloradofoodweb.org` looked unregistered in a rough DNS check; confirm at a registrar.
   `openfoodweb.org` is taken by an unrelated site.
