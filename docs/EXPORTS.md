# App exports (format version 1)

Apps never read the canonical tables. The Food Web builds one public JSON file per app, and the app
keeps a copy of it. This document is the contract between the two. Build it with
`scripts/export_app.py`; the first consumer is the Chaffee Provides site (`exports/chaffee-provides.json`).

```
python scripts/export_app.py --tables data/colorado --out exports/chaffee-provides.json \
    --release 2026-11 --county-fips 08015 --include-source chaffee_provides
```

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
  "removed_ids":   [ ... ]     // IDs only, so the app can drop old links
}
```

### `export`

| Field | Notes |
|---|---|
| `app` | Name of the app (taken from the file name) |
| `format_version` | Integer. **Apps must check it and refuse a version they do not know** |
| `release` | Release label, e.g. `2026-11` |
| `generated` | Date the file was built |
| `source` | `Colorado Open Food Web` |
| `county_fips` | Counties the export covers |
| `attribution` | Text the app must show, once, on its About page or footer |
| `counts` | `producers`, `markets`, `access_points`, `pins` (a quick sanity check) |

### `producers[]`

| Field | Type | Notes |
|---|---|---|
| `id`, `slug`, `name` | string | IDs are permanent; slugs may change |
| `kind` | string | `farm`, `ranch`, `orchard`, `maker`, `winery` |
| `categories`, `products` | list | From the Food Web vocabularies |
| `months_open` | list | Month names. Empty = unknown |
| `hours_text` | string/null | Free text |
| `website`, `phone`, `email`, `facebook`, `instagram` | string/null | Public business contact only |
| `sales_channels` | list | `farm_stand`, `u_pick`, `csa`, `farmers_market`, `pickup`, `delivery`, `online`, `wholesale`, `retail_partners`. Empty = not confirmed yet |
| `certified_organic`, `accepts_snap`, `ada_accessible`, `call_first` | bool/null | Null = unknown, never false |
| `status` | string | `active`, `seasonal_closed`, `unverified` |
| `claimed` | bool | The producer has confirmed the record |
| `last_verified` | date/null | |
| `locations` | list | See below. May be empty (an online-only producer) |
| `sources` | list | `{source, label, url}` for the "where this came from" line |

### `locations[]` (producers), `location` (markets and access points)

| Field | Notes |
|---|---|
| `id` | Location ID |
| `role` | `home_base`, `farm_stand`, `csa_dropoff`, `pickup` for producers; `market_site`; `access_site` |
| `name`, `address`, `city`, `zip`, `county_fips` | `address` and `zip` are null when withheld |
| `lat`, `lon` | Where to draw the pin. For a hidden address this is the nearest **town centre**, not the real spot |
| `precision` | `exact`, `approximate` (no street address, coordinates not exact), `town` (address withheld), `none` |
| `pin` | **Draw a pin here.** The app does not decide this |
| `pin_basis` | `confirmed` or `unconfirmed` (see below). An app may style unconfirmed pins, e.g. "call first" |
| `days`, `hours_text`, `season_start`, `season_end`, `status` | When the producer is at this location (producer locations only) |

### `markets[]` and `access_points[]`

Same shape as producers where the fields apply, with one `location` each. `access_points[].kind` is
`community_fridge` for now; pantries and meal sites will use the same list. Markets and access points
are always pinned.

## Rules the export applies

1. **Hidden addresses.** `hide_address` withholds `address` and `zip`, and moves the pin to the nearest
   town in `data/towns.csv`. A PO box is never published as an address.
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
6. **Order is stable.** Lists are sorted by name so a release diff shows only real changes.

## Changing the format

- Adding a field is not a breaking change: apps ignore fields they do not know.
- Renaming or removing a field, or changing what a value means, bumps `format_version`. The Food Web
  keeps building the old version until the app has moved.
- The app's sync script should fail loudly, not silently, when `format_version` is unknown or `counts`
  do not match what is in the file.

## Open questions

1. Where releases are published (a GitHub Release asset, or a committed `exports/` folder) and how the
   app's repo is notified.
2. Whether `hours_text` should become structured hours in version 2.
3. Whether outlets (restaurants, stores) get their own list when an app wants them. They are not exported now.
