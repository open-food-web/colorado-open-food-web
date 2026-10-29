# App exports (format version 1)

Apps never read the canonical tables. The Food Web publishes **one** statewide export per release,
`open-food-web.json`, as an asset of the tagged GitHub Release (see `RELEASES.md`). An app pins a release,
keeps a copy, and applies its own scope on its side (county, producer types, shop kinds, which pins to show).
This document is the contract between the two. `scripts/make_release.py` builds the file with
`scripts/export_app.py`; the first consumer is the Chaffee Provides site, whose `scripts/sync_data.py`
slices it down to Chaffee County.

```
python scripts/export_app.py --tables data/colorado --out release/open-food-web.json     --release v2026.10.7 --statewide --all-outlet-kinds --unconfirmed-home-pins hide
```

The release file is statewide (all 64 counties), carries outlets of every kind, and has no app scope
applied. **Always build it with `--unconfirmed-home-pins hide`**: otherwise every producer whose sales
channels are not confirmed gets a home-base pin, and across the state many of those homes are private
residences. Each home-base location carries `pin_unconfirmed_home`, true when the home would be pinned under
`show`, so an app that has a reason to show those pins (a county partner who knows its producers) can opt in
per record without the Food Web publishing them as pins.

`export_app.py` can still build a county or app slice (`--county-fips`, `--config`) for tests and
one-off checks, but apps do not get their own releases.
`exports/open-food-web.config.json` is a proposal for the maintainer: farms, ranches, orchards, makers
and wineries, plus grocery, farm store, garden center and apothecary outlets, with a reason on every exclusion.
It is for a statewide homepage app to apply, not a filter on the release.

## Why an export

- The canonical tables hold fields that must not leave the Food Web. The export is where the public
  release rules (see `SCHEMA.md`) are applied once, so no app has to remember them.
- The app can stay a plain static site: it copies the file, commits it, and publishes. Rolling back a
  bad update is reverting one commit.
- The diff between two exports is the monthly change report.

## File layout

```
{
  "export":  { ... },          // metadata
  "vocab":   { ... },          // labels the app can show
  "producers":     [ ... ],
  "markets":       [ ... ],
  "access_points": [ ... ],
  "outlets":       [ ... ],     // only when the app's config sets include_outlet_kinds
  "removed_ids":   [ ... ]     // IDs only, so the app can drop old links
}
```

### `export`

| Field | Notes |
|---|---|
| `app` | Name of the file (`open-food-web` for the release). An app that slices the release writes its own name |
| `format_version` | Integer. **Apps must check it and refuse a version they do not know** |
| `release` | Release label, e.g. `2026-11` |
| `generated` | Date the file was built |
| `source` | `Colorado Open Food Web` |
| `county_fips` | Counties the export covers (all 64 for a statewide export) |
| `attribution` | Text the app must show, once, on its About page or footer |
| `counts` | `producers`, `markets`, `access_points`, `market_links`, `pins` (a quick sanity check). `pins` counts producers, markets and access points only. With outlets: `outlets` and `outlet_pins` as well. `excluded_no_county` and `excluded_outside_area` count in-scope records left out per type (`producers`, `markets`, `access_points`, and `outlets` when exported): no county on any location or service area, or only in a county the export does not cover. Exported plus excluded always equals the in-scope total; the build stops if it does not |

A producer also has `service_county_fips` (counties it serves, from its areas of operation), so an app can
include a producer that serves its county but is based elsewhere.

### `vocab`

`vocab.counties` maps each covered county's FIPS code to its name (additive; `format_version` stays 1). Other keys: `sales_channels`, `months`, `kinds`, `product_groups`, and `outlet_kinds` / `outlet_groups` when outlets are exported.

### `producers[]`

| Field | Type | Notes |
|---|---|---|
| `id`, `slug`, `name` | string | IDs are permanent; slugs may change |
| `producer_type` | string | What the business is: `farm`, `ranch`, `orchard`, `maker`, `bakery`, `winery`, `education`. Labels are in `vocab.producer_types` |
| `products` | list | From the Food Web vocabularies. (`categories` was removed in format 2: use `producer_type`, `sales_channels` and `product_groups`. `dropin_visits`, `dropin_hours` and `visit_basis.dropin` were removed in format 3: places are described by their sales channels and named visits, not by whether people may drop in) |
| `product_groups` | list | What people search by: honey, beef and meat, eggs, veggies... Labels are in `vocab.product_groups` |
| `channel_details` | object | Text for a sales channel, keyed by channel: its hours or a short plain note (it may contain a link written `[words](https://...)`). Only channels that have text appear. Farm stand and u-pick hours are taken from the listing when no one has written text. The on-farm ways to find a producer are sales channels (`farm_stand`, `farm_visit`, `u_pick`, `tour`, `stay`, `volunteer`); the Food Web does not label a place by whether people may drop in |
| `farm_pickup` | bool/null | Can a customer collect an order at the farm, by arrangement?  |
| `visit_basis` | object | `{pickup}`: `set` (a person's answer), `listing` (inferred from the listing, e.g. a farm stand or tours) or null |
| `visit_note` | string/null | One plain sentence about visiting or pickup |
| `months_open` | list | Month names. Empty = unknown |
| `hours_text` | string/null | Free text, always kept |
| `hours` | list | Structured: `{day, opens, closes, closes_next_day?, inferred?}`, `day` is `mon`..`sun`, times are 24-hour `HH:MM`. Empty when not readable |
| `hours_status` | string | `parsed`, `partial`, `appointment`, `text_only`, `none`. Show `hours_text` unless `parsed` |
| `sells_at` | list | Markets the producer sells at: `{market_id, name, county_fips, year, season_label, basis, source_url}` |
| `website`, `phone`, `email`, `facebook`, `instagram` | string/null | Public business contact only |
| `sales_channels` | list | `farm_stand`, `farm_visit` (a plain visit to the farm), `u_pick`, `tour`, `stay`, `volunteer`, `csa`, `farmers_market`, `pickup`, `delivery`, `online`, `wholesale`, `retail_partners`, `agritourism`, `food_access` (grown for food access programs, not sold to the public), `none` (confirmed no public sales). Empty = not confirmed yet. Labels are in `vocab.sales_channels` |
| `certified_organic`, `accepts_snap`, `ada_accessible`, `call_first` | bool/null | Null = unknown, never false |
| `status` | string | `active`, `seasonal_closed`, `unverified` |
| `claimed` | bool | The producer has confirmed the record |
| `last_verified` | date/null | |
| `locations` | list | See below. May be empty (an online-only producer) |
| `sources` | list | `{source, label, url}` for the "where this came from" line |
| `confirmed_by` | list | Who stands behind which details: `{by, fields, url, date}`. `by` is a partner such as Guidestone Colorado, or the business's own website or Facebook page. Shown on the listing as "Phone confirmed by Guidestone Colorado, Oct 13, 2026" |

### `locations[]` (producers), `location` (markets and access points)

| Field | Notes |
|---|---|
| `id` | Location ID |
| `role` | `home_base`, `farm_stand`, `csa_dropoff`, `pickup` for producers; `market_site`; `access_site` |
| `name`, `address`, `city`, `zip`, `county_fips` | `address` and `zip` are null when withheld |
| `lat`, `lon` | Where to draw the pin. For a hidden address this is the nearest **town centre**, not the real spot |
| `precision` | `exact`, `approximate` (no street address, or the coordinates are a town centre), `town` (address withheld), `none` |
| `pin` | **Draw a pin here.** The app does not decide this |
| `pin_basis` | `confirmed` or `unconfirmed` (see below). An app may style unconfirmed pins, e.g. "call first" |
| `days`, `hours_text`, `season_start`, `season_end`, `status` | When the producer is at this location (producer locations only) |
| `confirm_url` | The business's own page that confirms it sells here, so an app can link to it (producer locations only; null when none) |
| `channels` | The sales channels this place serves, from `sales_channels` (for example a pickup point for `online` orders, or a stop at a `farmers_market`). Empty when nothing is stated. The link between a place and a way to buy is stated here, not inferred from the place's role |

### `markets[]` and `access_points[]`

Same shape as producers where the fields apply (`hours`, `hours_status`), with one `location` each. Markets also carry `vendors`: the IDs of exported producers that sell there. `access_points[].kind` is
`community_fridge` for now; pantries and meal sites will use the same list. Markets and access points
are always pinned.

### `outlets[]` (optional)

Shops, grocers and dining places, exported only for an app whose config lists `include_outlet_kinds`
(for example `["apothecary", "farm_store"]`). An app that does not ask gets no `outlets` key, and
`pins` never includes outlet pins, so a site written before outlets existed still passes its checks.

| Field | Notes |
|---|---|
| `id`, `slug`, `name`, `brand` | Outlet identity; `brand` is null unless a chain or group |
| `kind` | `grocery`, `farm_store`, `garden_center`, `apothecary`, `other_retail`, or a dining kind; labels in `vocab.outlet_kinds` |
| `group` | `shops` or `dining`, derived from `kind`; labels in `vocab.outlet_groups` ("Shops & Grocers", "Restaurants & Caterers") |
| `website`, `phone`, `facebook`, `instagram`, `hours`, `status`, `last_verified` | As for producers where they apply |
| `location` | Same shape as a market's `location` (role `outlet_site`). Pinned unless the address is hidden |
| `sources`, `confirmed_by` | As for producers |

An outlet carries no products or descriptions; the Food Web keeps outlets thin.

## Rules the export applies

1. **Hidden addresses.** `hide_address` withholds `address` and `zip`, and rounds the location to the nearest
   town in `data/towns.csv`; a home with a hidden address is listed by its town and is never pinned (`pin` false), because a town is not a place. A PO box is never published as an address.
2. **Opt-outs.** Fields in a producer's `opted_out_fields` are blanked. A `removed` producer is not in
   `producers`; its ID is in `removed_ids`.
3. **Closed records leave.** `closed` and `removed` records are not exported.
4. **Who is included.** A record is in an export if any of its locations is in the export's counties, if
   its service area includes one, or if a listed source (`--include-source`) lists it.
5. **When a home base gets a pin.** A `home_base` is pinned when `sales_channels` includes `farm_stand` or
   `u_pick` (`pin_basis: confirmed`). Pickup points, farm stands and CSA drop-offs are always pinned. If
   the channels are not confirmed yet, the home base is pinned with `pin_basis: unconfirmed` (set
   `--unconfirmed-home-pins hide` to turn this off). A producer that sells only by pickup or delivery
   has no home-base pin once its channels are set, so its pins are the pickup points.
6. **App scope choices.** (`exclude_producer_types` leaves out a whole producer type, for example `["bakery"]`, until the partner decides.) An app's own decisions about what to show (for example, Guidestone leaving a vacation rental off its site) live in the app's own repo (Chaffee Provides: `scripts/scope.json`, with a reason on each exclusion). The Food Web keeps the record; only the app leaves it out.
7. **Order is stable.** Lists are sorted by name so a release diff shows only real changes.

## Changing the format

- Adding a field is not a breaking change: apps ignore fields they do not know.
- **Format 2** (Oct 2026) removed `categories` from producers and replaced the scope keys `include_categories` / `exclude_categories`
  with `include_producer_types` / `exclude_producer_types`, and renamed the producer `kind` field to `producer_type` (and `vocab.kinds` to `vocab.producer_types`). Outlets, markets and access points keep `kind`. No app was live, so there was no overlap period.
- Renaming or removing a field, or changing what a value means, bumps `format_version`. The Food Web
  keeps building the old version until the app has moved.
- The app's sync script should fail loudly, not silently, when `format_version` is unknown or `counts`
  do not match what is in the file.

## Open questions

1. (Settled) The release is published as a GitHub Release asset, `open-food-web.json`, with its sha256 in
   `MANIFEST.json`. Open: how an app's repo is notified of a new release.
2. (Settled) Structured `hours` and `sells_at` were added as non-breaking fields; `hours_text` stays.
3. (Settled) Outlets of every kind are in the release; an app picks the kinds it shows.
