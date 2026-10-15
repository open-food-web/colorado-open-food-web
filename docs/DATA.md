> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# Data Source

All farm data comes from the **Colorado Proud Farm Fresh Directory**, published by
the Colorado Department of Agriculture. It is used here purely as a **source /
attribution** — Colorado Farm Trail is an independent project (see `branding.md`).

## How the data was found

The public page — https://coloradoproud.com/find-farm-fresh-favorites/ — looked like
a WordPress store-locator, but the map is actually an **ArcGIS Experience app**
embedded in an iframe. Tracing it:

1. Page embeds an ArcGIS Experience app
   (`experience.arcgis.com/experience/c178ee51c0d747b687e58db7c9c94d32/`).
2. That app reads a Web Map item **"Farm Fresh Directory"**
   (`230a9b6cb77e4dd3931442c2ed05b746` on `COOIT.maps.arcgis.com`).
3. The web map's operational layer is a public **ArcGIS Feature Service** — the
   actual data behind the map and its table view.

## The endpoint

```
https://services3.arcgis.com/DgjqnJA1rgO92Soi/arcgis/rest/services/Farm_Fresh_Directory/FeatureServer/0
```

Query all records (attributes + lat/long) as JSON:

```
.../FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=json
```

- **163 records**, **36 counties**, **47 raw fields** each, plus point geometry
  (latitude/longitude).
- `maxRecordCount` is 2000, so a single query returns everything.

## The CSV exports (in `data/`)

| File | What |
|---|---|
| `colorado_proud_farm_fresh_directory_raw.csv` | All 47 fields, alias headers, + Latitude/Longitude. The unabridged export. |
| `farm_fresh_directory_mymaps.csv` | Cleaned, **import-ready for Google My Maps**: 23 tidy columns |

### The cleaned My Maps file

- **23 columns**: Business Name, **Category**, Address, City, County, State, Zip,
  Phone, Call first?, Website, Email, Facebook, Instagram, Hours, Months Open,
  Products, Certified Organic, SNAP, ADA Accessible, Notes, **Where to Get It**,
  **Latitude, Longitude**.
- **`Category`** is derived from the raw, multi-valued `Operation type` field
  (pipe-delimited, e.g. `U-pick|On-Farm/Ranch sales`). Each value maps exactly to a
  clean bucket, and **a listing keeps every bucket it qualifies for**, comma-joined
  in priority order (`U-Pick, On-Farm / Ranch Sales`). The **first is the primary**:
  it sets the pin's color and icon (and is what My Maps groups by if you style on
  this column). The site's type filter matches a listing under *any* of its
  categories. `Centennial Farm/Ranch` (a heritage designation) and `Community
  Gardens` aren't buckets; a Centennial ranch with nothing else listed counts as
  On-Farm / Ranch Sales. `Sells to Schools` is kept in the data but has no filter.
  **`Wholesale Grower`** is ours, not a Colorado Proud type: hand-added for farms that
  sell mainly to stores and restaurants rather than to visitors (e.g. Jones Farms
  Organics). A farm with a stand as well lists it as a secondary category.
- **`Where to Get It`** (hand-curated, blank for Colorado Proud rows) lists the
  stores, markets and restaurants that carry a wholesale grower's products,
  **semicolon-separated** (entries may contain commas), e.g.
  `Whole Foods Market, Boulder; Rootstalk, Breckenridge`. The map popup shows it as a
  "Where to get it" list. `fetch_farm_data.py` writes the column blank, so re-running
  it drops curated values — copy them back from git.

  | Category | Primary | Listed under (any) |
  |---|---|---|
  | On-Farm / Ranch Sales | 22 | 63 |
  | Farmers' Market | 47 | 48 |
  | Agritourism | 10 | 39 |
  | Roadside Market | 17 | 34 |
  | CSA Farm | 23 | 30 |
  | Garden Center / Greenhouse | 8 | 21 |
  | U-Pick | 14 | 16 |
  | Sells to Schools | 0 | 15 |
  | Other | 12 | 12 |
  | Winery | 8 | 8 |
  | Restaurant | 2 | 5 |
  | Wholesale Grower | 2 | 2 |

- `Products`, `Hours`, and `Months Open` were consolidated from ~15 scattered raw
  columns into single readable cells (pipes → commas).
- **Latitude/Longitude are dedicated columns** so Google My Maps places pins exactly,
  with no geocoding.

## Status: closed businesses are kept

The raw CSV (`source-data/phase2/co_farmers_markets_all_raw.csv`) has a `Status` column,
`Open` or `Closed`. Closed farms, ranches and businesses stay in it (only ones that would have
qualified, that we know existed and have shut down) so they are never researched or added again; the My Maps file
and the map leave them out. Everything else is assumed open until found otherwise. How to mark
one: `scripts/scrape/README.md`, "Closed businesses stay in the dataset".

## Deduplication & data-quality notes

The all-Colorado farmers-market dataset (`data/co_farmers_markets_all_raw.csv`)
merges two source feeds (`colorado_proud` + `usda`), which introduces
near-duplicates. These are flagged in the **`Possible Dup Of`** column and resolved
under the rules in **[`DEDUP_STANDARDS.md`](DEDUP_STANDARDS.md)** — the short version:
**location is the deciding signal** (we're making a map), and same-location
seasonal (winter/summer) markets get merged with the seasonality captured in
`Hours` / `Months Open` / `Notes`.

### The deduped file

`data/co_farmers_markets_all_deduped.csv` is the resolved output: **139 → 133
records**. The 6 duplicates below were dropped into their canonical twin, the
Backyard winter season was folded into its summer record (extended `Months Open` +
a `Notes` line), and the `Possible Dup Of` working column was cleared (decisions now
live in `DEDUP_STANDARDS.md`). The raw file is left **untouched** as the source of
record; regenerate the deduped file from it rather than editing it by hand.

**6 merges applied (dropped → canonical):**

- Backyard Market in Black Forest **- Winter** → *The Backyard Market in Black Forest*
- **Delta Farmers Market** → *The Delta Farmers Market & Bazaar*
- **Evergreen Farmers Market** (Bergen Pkwy) → *Evergreen Farmers Market THE ORIGINAL*
- **Fort Morgan Farmers' Market** → *Fort Morgan Farmers Market at The Block*
- **Aspen Grove Lifestyle Center Farmers' Market** → *Aspen Grove Farmers Market*
- **Highland United Neighbors Farmers' Market** → *Highland Farmers' Market*

### Market consolidations to reflect

- **Farmers' Market at Highlands Square** (row: 3489 W. 32nd Ave) was **folded into
  The Highlands Farmers Market** (`thehighlandsfarmersmarket.com`), a different
  entity operating at the same 32nd & Lowell location (Sundays 9am–1pm, May–Oct).
  The dead `highlandssquarefarmersmarket.com` domain is the evidence of that
  consolidation — the standalone Highlands Square market no longer exists under its
  own name. The record should be re-pointed to The Highlands Farmers Market
  identity/URL rather than kept as a separate "Highlands Square" market.
- Note this is **distinct** from **Highland Farmers' Market** (1576 Boulder St,
  `denverhighland.org`) — a different entity ~1.2 mi away in lower Highland. Same
  neighborhood name, different market and location; do not conflate the two.

## Refreshing the data

```
python scripts/fetch_farm_data.py
```

Re-pulls from the feature service and rebuilds both CSVs in `data/`. Re-import the
`farm_fresh_directory_mymaps.csv` into Google My Maps if the source directory has
changed. (The directory is community-submitted and grows over the season, so an
occasional refresh keeps the map current.)

## Importing into Google My Maps

1. mymaps.google.com → **Create a new map** → **Import** → upload
   `farm_fresh_directory_mymaps.csv`.
2. Position by **Latitude** + **Longitude** (not the address).
3. Title markers by **Business Name**.
4. Style: set *"Group places by"* → **Category** for color-coded pins.

Current live map ID (`mid`): `15fDxNgQN1yxO7xc2FR27Kq6NND3GjvE`
