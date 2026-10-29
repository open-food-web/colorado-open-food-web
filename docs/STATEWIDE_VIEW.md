# A Chaffee Provides style view for all of Colorado

Scope and plan for an Open Food Web homepage that gives every Colorado producer the page Chaffee
Provides gives Chaffee County's. Numbers come from `scripts/readiness.py` on the tables as of
2026-10-15 (full output: [`reports/readiness-2026-10-15.md`](../reports/readiness-2026-10-15.md)).
Rerun it after each snapshot PR to watch the gaps close:

```
python scripts/readiness.py                    # whole state
python scripts/readiness.py --county 08015     # Chaffee, the benchmark
```

## Summary

- **Ready today: 188 of 1,227 producers (15%)**, near 149 (12%), gap 890 (73%). Chaffee, the benchmark,
  is 57% ready (13 of 23). Boulder is 24%, Larimer 13%, Weld 15%, Mesa 18%, Denver 11%.
- **One gap dominates: sales channel.** 929 producers (76%) have no confirmed channel, and the channel
  decides the pin, the "ways to get it" list and whether the farm welcomes visitors. Everything else is
  at least 79% filled (town 96%, contact 93%, product group 79%).
- **Cheapest big win:** a producer listed in a live farmers market's vendor list sells at a farmers
  market. 120 producers have a market link but no channel. Deriving `farmers_market` from the links
  moves ready from 188 to 263 (21%) for about an hour of work.
- **Three things must be fixed before a statewide export is correct**, not just complete:
  1. `data/towns.csv` has only the five Chaffee towns. Withheld addresses snap to the nearest town in that
     file, so statewide, Common Name Farm (Lafayette, Boulder County) and the other hidden-address records outside Chaffee would be
     pinned in Chaffee County (19 hidden-address locations are in the trial export; the two truly in Chaffee are right by luck). (Checked by running `export_app.py` over all 65 counties.)
  2. 62 producers have no county on any location, so a county export drops them (1,165 of 1,227
     exported). 31 of the 62 have coordinates and could be placed.
  3. Source terms (CLAUDE.md pending item 1) are unresolved. Nothing here ships publicly until they are.
- **Realistic path:** an honest statewide launch is possible after about 6-8 working sessions by showing
  only what is confirmed (a "verified channels" default) and listing the rest by town without a pin.
  Getting statewide completeness near Chaffee's needs a further 15-25 sessions, mostly reading
  businesses' own sites, and cannot be fully automated.

Effort key: **S** under 2 hours (one session), **M** 2-6 hours (1-2 sessions), **L** a day or more
(3+ sessions or outside dependencies). A "session" is one working session with review.

## What the Chaffee design needs, and where Colorado stands

Producers counted: 1,227 live (closed and removed records excluded). Percentages are shares of that.

| # | Element on the Chaffee page | Field(s) | Have | Statewide gap | Notes |
|---|---|---|---|---|---|
| 1 | Town on every card, town filter | home `city` | 1,184 (96%) | 43 | County is a second need for the statewide filter: 1,139 (93%); 88 missing |
| 2 | Product group chips and filter | `product_groups` | 964 (79%) | 263 | 86 of those have free-text `products` that the group mapper (`scripts/products.py`) may place |
| 3 | "What they offer" text | `products` | 982 (80%) | 245 | Facts only; no copied descriptions |
| 4 | Ways to get it (farm stand, u-pick, CSA, market, pickup, online, wholesale, stores) | `sales_channels` | 298 (24%) | **929** | Blank means unknown, never "none" |
| 5 | Pin on the map | home pin for `farm_stand`/`u_pick`; any pickup point | 128 confirmed (10%) | see below | 821 more would get a lighter *unconfirmed* pin because no channel is set |
| 6 | A place to find them (pin, market link, or online/delivery) | derived | 348 (28%) | 879 | Of the 298 with a channel, 70 have none of these (67 are CSA, wholesale, pickup, store-only) |
| 8 | Farm-pickup answer | `farm_pickup` | 304 (25%) | 923 | Only 6 set by a person; the rest implied |
| 9 | Hours | structured `hours` | 145 (12%) | 1,082 | `hours_text` exists for more; 1,047 producers have `hours_status` none |
| 10 | Contact (phone, website, social, email) | any of five | 1,136 (93%) | 91 | Phone 83%, website 57%, social 66%, email 23% (verified-only) |
| 11 | "Confirmed by" line | `field_sources` partner or own site | 19 (2%) | 1,208 | The line is what makes Chaffee trustworthy; it is rare statewide |
| 12 | "Checked on <date>" pill | `last_verified` | 0 (0%) | 1,227 | No producer has the field set, so the pill never shows |
| 13 | Farmers market links ("At the farmers market", market page, vendors list) | `market_vendors` | 229 producers (19%); markets: 153, 102 with hours, 39 with vendors linked | 24 | Chaffee's page builds the market stop from a pickup-role location; statewide should use `sells_at` (see below) |
| 14 | Stores that carry a producer | `outlet_suppliers` | table not built | all | `inputs/supply-network/edges.csv` has ~397 supplier-to-buyer links by business name, traced from published sources, to convert |
| 15 | Shops and grocers (outlets) | `outlets` | 160 (67 grocery, 10 farm stores, 8 garden centres, 1 apothecary, 73 restaurants/caterers); 147 with coordinates, 7 without a county | outlets are thin; no hours (0) | Opt-in per app via `include_outlet_kinds` |
| 16 | Photos | `google_place_id` only | 0 stored | all | Plan on hold ([PLACES_API_PLAN.md](PLACES_API_PLAN.md)); Farm Trail launches with a placeholder and a Google Maps link |
| 17 | Descriptions | not in the Food Web | none by design | n/a | Chaffee keeps submitted descriptions in its own repo. Statewide has none: facts-only rule |
| 18 | Hidden address handling | `hide_address` | 27 locations | towns file | See blocker 1 |
| 19 | Claimed / producer-confirmed | `claimed` | 0 | all | No producer has claimed a record yet |

**Tiers.** "Ready" means town, product group, channel, a place to find them, and contact all present.
Statewide: ready 188, near 149, gap 890. Of the 149 near, the single missing item is the channel for 75,
a place for 34, contact for 19, a product group for 14 and a town for 7. By kind: farms 141 of 674 ready,
ranches 28 of 223, makers 13 of 287, wineries 3 of 39. Makers (a Colorado Proud-heavy group) are the
weakest because the sources rarely say how to buy.

**Scenarios** (all counted with the readiness script's own rules):

| If we... | Ready | Near | Gap |
|---|---|---|---|
| change nothing | 188 | 149 | 890 |
| derive `farmers_market` from live market vendor links | 263 | 115 | 849 |
| also set a channel for every producer with a website (upper bound, place unchanged) | 263 | 444 | 520 |

The last row says what a channel pass buys: most of the 487 producers with a website would become
"near", and the pin/place rule then decides how many reach "ready". A channel of `farm_stand` or `u_pick`
gives a pin at once; `csa`, `wholesale` and `online` do not.

## How to close each gap

Ordered by value for effort. "Auto" means the existing pipeline or a script can do it with a human
review of the PR; "Person" means a maintainer or partner has to decide or confirm.

| Order | Work | Closes | Effort | Auto or person | Notes and risks |
|---|---|---|---|---|---|
| 1 | **Statewide `data/towns.csv`** from the Census gazetteer (`scripts/build_places.py` already reads it) | Blocker 1 (wrong pins for hidden addresses) | S | Auto | Must land before any statewide export. Add a test that every hidden-address pin lands in its own county |
| 2 | **Fill the 88 missing counties** by looking each home base up by coordinates (31) or by city and ZIP where there is one (57) | Blocker 2; the county filter | S | Auto, spot-check | Use the Census geocoder results already cached in `inputs/geocode_cache.json` first |
| 3 | **Derive `farmers_market`** from live `market_vendors` rows; stamp `field_sources` with the vendor-list URL | 120 channels (+75 ready) | S | Auto | A vendor list on the market's own site is the evidence, so it is a fact. Only live markets; a closed market gives no channel |
| 4 | **Run the product-group mapper** over the 86 producers with product text but no group | 86 groups | S | Auto | Then 177 remain with no products at all (see 9) |
| 5 | **Source-terms review** for Colorado Proud, CFMA/MarketWurks, USDA (pending item 1) | Gate for any public statewide release | M (waiting on others) | Person | Do not publish from a source with unclear terms. Decide ODbL vs CC BY at the same time. The page can be built and reviewed privately meanwhile |
| 6 | **Statewide export config and flag**: `--statewide` (all 65 county codes), `exports/open-food-web.config.json`, a statewide scope decision (are agritourism, bakeries, restaurants, caterers in?), `--unconfirmed-home-pins hide` | A correct statewide JSON | S-M | Person decides scope; code is small | See "What changes in the export". Chaffee's choices (no agritourism, bakeries, restaurants, caterers) were that partner's, not the state's |
| 7 | **Facts-only export filter** on the tables themselves (pending item 4): drop `source_prose` and `personal` fields, run automatically after a snapshot PR merges | Release rule compliance | M | Auto | `export_app.py` already builds only fact fields; this adds the same guarantee for the CSV/JSON/SQLite release |
| 8 | **Sales channels from each business's own site**: extend `scripts/scrape` with a classifier for farm stand, u-pick, CSA, online ordering, pickup and delivery on the producer's website, recording the page in `field_sources` with `producer_site` | Up to 487 producers with a website; the main gap | L: about 3-4 sessions to build and tune, then 1-2 sessions of review per 100 producers | Auto find, person approves | Highest value and highest risk: a wrong "farm stand" puts a pin on a private home. Record only what the page states, never infer "none", and keep the evidence URL. Respect robots.txt as `contact_policy.py` does. Emails still follow the verified-only policy |
| 9 | **Facebook-only and no-web producers** (183 + 259) | Channels and products for the rest | L, repeating | Person | Facebook cannot be scripted. The signed-in read-only method in [FOLLOWUPS.md](FOLLOWUPS.md) yields roughly 10% usable per page. Better: let businesses claim and confirm their own record ([BUSINESS_SUBMISSIONS.md](BUSINESS_SUBMISSIONS.md)) and regional partners confirm (Chaffee Provides model, [PARTNERS.md](PARTNERS.md)) |
| 10 | **Places to find CSA and wholesale-only producers** (67 with a channel but no place) | Moves "near" to "ready" | M | Mixed | The CSA research in `scripts/csa` already collects pickup points with quoted evidence in the sources repo; load the confirmed ones as `pickup` locations. Wholesale-only producers legitimately have no place for the public: show them in the directory, not the map |
| 11 | **`outlet_suppliers` table** from `inputs/supply-network/edges.csv` (about 397 links): match names to `producer_id` and `outlet_id`, keep `source_url`, `observed_on`, `basis`, flag `unconfirmed` links | "Stores that carry this producer" | M (1-2 sessions) | Auto match, person reviews ambiguous names | Most perishable data we hold; show the evidence date and mark older mentions. Many edges are restaurants, which the Chaffee site does not show |
| 12 | **Outlet gaps**: counties for 7, hours for all (0 today), website/phone checks | Shops and grocers sections | M | Auto from own sites | Outlets stay thin: no products or descriptions |
| 13 | **Stamp `last_verified`** whenever the pipeline or a person checks the business's own site | "Checked on" pill, trust | S | Auto | Today 0 producers have it. Define it as "a person or the pipeline confirmed at least one field from the business's own page on this date" |
| 14 | **Hours**: parse `hours_text` where it exists; read hours from own sites for pinned places only | Hours on the page | M | Auto (parse), person (review) | 12% structured. Only pinned places need them to be useful |
| 15 | **Market vendor lists** for the 114 markets with no vendors linked | Vendors on each market page; more market links | M per batch of ~20 markets | Auto fetch, person review | `inputs/market_vendor_lists.csv` and `scripts/phase3` exist. Match basis is recorded (`match_basis`) |
| 16 | **On-farm channels with their text, and farm-pickup answers** | Channel details | M, ongoing | Person | Set in `inputs/producer_types.csv`. Not needed for launch: an unknown shows nothing |
| 17 | **Photos** via `google_place_id` | Photo on cards and pages | L (project, key, hard spending cap, terms confirmation) | Person sets up; script does the lookups | Launch with the placeholder and a "See photos on Google Maps" link. Never store photo URLs. Confirm Google's terms for storing the id first |
| 18 | **Claims and the confirmed-by line** | Trust line, `claimed` | L, ongoing | Person | Needs the intake form ([BUSINESS_SUBMISSIONS.md](BUSINESS_SUBMISSIONS.md)) live and a few regional partners |

### Totals

| Package | Items | Effort | Outcome |
|---|---|---|---|
| **A. Unblock** | 1, 2, 3, 4, 6, 13 | about 4-5 sessions (S each) | Correct statewide export; ready about 22%; no wrong pins |
| **B. Launchable statewide page** | A plus 5, 7, 10 | about 6-8 sessions in total, plus the wait on source terms | Public page, with a "confirmed" default view and a plain note that most listings are not yet confirmed |
| **C. Fill the channel gap** | 8, 9, 11, 12, 14, 15 | 15-25 further sessions, spread over months | Ready share plausibly 40-50% for producers with a website. The 259 with no web presence and no claim stay mostly unconfirmed |
| **D. Photos and claims** | 17, 18 | ongoing | Matches Chaffee's look and trust |

These are estimates, not measurements. The first real measurement is item 8's pilot on one county: the
hit rate and review time per producer there replaces the 15-25 figure.

## Risks

- **Source terms.** Colorado Proud, CFMA/MarketWurks and Chaffee Provides state no data license; the
  USDA API terms are unverified. A public statewide page republishes facts from all of them, so
  **do not publish before item 5**. A private preview is fine.
- **Personal data and private homes.** Most producers are farms at their owners' homes. An *unconfirmed*
  home pin tells the world where someone lives without their saying customers are welcome. Recommend
  `--unconfirmed-home-pins hide` for the statewide export: producers without a confirmed farm stand,
  u-pick or pickup point appear in the list with their town, and only on the map when a channel is
  confirmed. Honor `hide_address` (pins snap to a town; blocker 1 must be fixed first). No PO boxes.
- **Emails.** Publish only addresses verified on the business's own website
  (`scripts/scrape/contact_policy.py`). 150 Facebook pages are still queued. A statewide page changes
  nothing about this rule; do not add an email to make a gap look smaller.
- **Facts only.** No copied descriptions, no third-party photos (only `google_place_id`). The Chaffee
  page's "about" paragraph is a Chaffee-repo feature that comes from businesses submitting their own
  text; statewide has none until the claim form collects some with permission.
- **Wrong channels.** A channel classifier (item 8) that guesses is worse than a blank. Blank means
  unknown; only record what a business's own page says, with the URL.
- **Silent over-promising.** At 15% ready, a page that looks as finished as Chaffee's would mislead.
  Show a confirmed/not-yet-confirmed distinction on every card (Chaffee already styles unconfirmed pins
  lighter and says "We haven't confirmed that they sell here yet").
- **Scope disagreement.** Chaffee's exclusions (agritourism, bakeries, restaurants, caterers) belong to
  Guidestone. The Food Web page needs its own scope decision from the maintainer.

## What changes in the export

`scripts/export_app.py` is already statewide-capable; it takes `--county-fips` as a list and reads the
statewide tables in `data/colorado` (those hold 1,227 producers). A trial run
over all 65 county codes works and produces 1,165 producers, 152 markets and about 1,090 pins in about
2.5 MB (about 250 KB gzipped). What needs to change:

1. **Statewide towns file** (blocker 1). `towns` is read from `data/towns.csv` and filtered to the
   requested counties, so hidden addresses snap to the nearest *listed* town.
2. **A `--statewide` convenience** (or `--county-fips all`) so nobody types 65 codes, and a
   `exports/open-food-web.config.json` with its own scope choices and `include_outlet_kinds`
   (outlets are opt-in per app; a statewide config would list `grocery`, `farm_store`, `garden_center`,
   `apothecary`, and decide on dining).
3. **Unconfirmed home pins hidden** by default for this app (flag exists).
4. **County names in the vocab** (`vocab.counties`: FIPS to name, plus a region grouping) so the page
   does not carry its own copy. Additive, so `format_version` stays 1.
5. **Records without a county** (item 2) so no producer silently leaves the export; add an
   `export.counts` check that exported plus excluded equals the total.
6. **Markets for the market stop.** The Chaffee page builds "At the farmers market" from a
   pickup-role location whose name contains "market". For the whole state, use `sells_at` (already in
   the export) so a producer links to the market page without a hand-made pickup location.
7. **File shape for scale** (see product shape): either keep one file, or split per county with an
   index, which `export.counts` and `removed_ids` would then need to describe per file. Not needed yet
   at 2.5 MB.
8. **`build_tables.py`** already runs statewide (the tables prove it); the remaining part of pending
   item 4 is the facts-only filter for the public release and the automatic run after a snapshot PR
   merges (item 7).

## Product shape

A statewide page differs from Chaffee's in a few ways.

| Topic | Chaffee Provides | Statewide Open Food Web |
|---|---|---|
| Geography | One county; the map is framed on a county outline and dims everything else | Start on a state view. **County and region filter** in front of the town filter; the URL carries it (the Chaffee page already keeps state in the URL, so a county view can be bookmarked). Town list is long, so search-as-you-type |
| Map scale | Dozens of pins, no clustering, offsets for stacked pins | 1,000+ pins at state zoom: **cluster** (Leaflet MarkerCluster or a canvas layer), colour by kind as now, fit to the filtered set, and "near me" via the browser location (never stored) |
| Performance | One JSON, ~30 producers | 1,165 producers and about 160 outlets are about 2.5 MB raw and 250 KB gzipped; fine as one static file. Render the list virtually or paginated (50 at a time) and build the search index once. Only revisit if the data passes about 5,000 records |
| Confirmation | Partner (Guidestone) confirmed many facts; "Confirmed by" line shows | **No per-county partner confirmations.** The line shows only what is confirmed (business's own website or Facebook, or a claim). Add a **"Confirmed only" toggle**, on by default for the map and off for the directory, so an honest page can still be useful at 15% ready |
| Empty states | Rare | Common: say so plainly ("We haven't confirmed how to buy from them yet") and give the contact links; offer "Suggest an update" and a claim link on every page |
| Scope | Guidestone's choices (no restaurants, bakeries, agritourism) | The Food Web's own choice, made by the maintainer; start with farms, ranches, orchards, makers and wineries, with markets and shops as on Chaffee |
| Outlets | Shops and grocers; "stores that carry" planned | Same sections, county-filtered. Supplier links are sparse (about 400 across the state, pilot data): show the section only where links exist |
| Photos | Local files, kept in the Chaffee repo | Placeholder and a "See photos on Google Maps" link at launch |
| Descriptions | The business's submitted text | None; "What they offer" is built from product groups and `products` |
| Provider page | Map on top, ways to get it with addresses and links, previous/next arrows | **Reuse as is.** The page already works from one record; the previous/next arrows should follow the active filter |
| Home | The map | A homepage: state map and counts by county, top product chips, "Find food near you", then links to county pages as partners come on board (Chaffee Provides stays a partner site that reads its own export) |

Reuse is the point: `assets/app.js`, `provider.html` and `find-food.html` in the Chaffee repo are the
starting point, with its county outline replaced by a layer toggle for county boundaries (Census
TIGERweb, as for Chaffee, simplified) and the model builder (`makeRec`) kept as is. The one assumption
to remove is the hard-coded "Chaffee County" copy and the `supportedFormat` check, which can stay.

## Suggested first three sessions

1. Statewide `towns.csv`, fill counties for the 88, a test that hidden-address pins land in their county.
2. Derive `farmers_market`; run the product-group mapper; stamp `last_verified`; rerun `readiness.py`
   and commit the new numbers (ready should be about 22% or higher).
3. `--statewide` and the statewide config; build a private preview of the page from the Chaffee site
   code with the "Confirmed only" toggle and clustering, and measure it on a phone.

Meanwhile, the maintainer can start the source-terms review (item 5) and decide the page's scope (item 6).

## Open questions

1. Scope of the statewide page (kinds and categories).
2. Whether the page may show unconfirmed home pins at all (recommendation: no).
3. Which partner counties come next, and whether their sites reuse the same code.
4. Who owns the Google Cloud project for photos.
